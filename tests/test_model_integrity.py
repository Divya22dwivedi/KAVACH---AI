"""Phase 5 tests: Model Integrity module (bounded prototype).

Trains tiny reference/candidate MLPs on synthetic clean/poisoned data,
registers both, runs Module 2 checks, and asserts MEASURED outcomes:
- trigger flip-rate(candidate) > flip-rate(reference)
- behaviour_compare agreement < 1.0
- hash_verify passes
- .onnx / fake .pt register as metadata-only; white-box checks return
  "unavailable" with the exact mandated note
- foreign/tampered pickles get manifest_ok=0 and are never executed

Fully offline. Run from the repo root:
    .venv/bin/python -m pytest tests/test_model_integrity.py -v -s
"""

import pickle
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from sklearn.neural_network import MLPClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import train_demo_models as demo  # noqa: E402
from attack_generator.generate import (  # noqa: E402
    CLASSES, add_trigger, full_suite, make_clean_dataset,
)
from ml.common.features import extract_features  # noqa: E402
from ml.common.model_io import (  # noqa: E402
    UntrustedModelError, load_kavach_model, save_kavach_model,
)
from ml.model_integrity.checks import UNAVAILABLE_NOTE, run_checks  # noqa: E402
from ml.model_integrity.registry import register_model  # noqa: E402

TINY_N = 300
TINY_MAX_ITER = 100
PROBE_SEED = 2026
PROBE_N = 200


def _meta(trained_on: str) -> dict:
    return {"arch": "MLPClassifier", "hidden_layer_sizes": [64, 32],
            "max_iter": TINY_MAX_ITER, "classes": CLASSES,
            "trained_on": trained_on, "seed": 42}


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    """Train tiny models, register them, run checks. Returns all artifacts."""
    root = tmp_path_factory.mktemp("model_integrity")
    ds_root = root / "datasets"
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    clean = make_clean_dataset(ds_root, seed=42, n=TINY_N, name="clean")
    poisoned = full_suite(ds_root, seed=42, n=TINY_N,
                          k_flip=15, k_trigger=20, k_dup=12, k_ood=15)
    probe = make_clean_dataset(ds_root, seed=PROBE_SEED, n=PROBE_N,
                               name="probe")

    X_clean, y_clean = demo.load_features(clean["dir"])
    X_pois, y_pois = demo.load_features(poisoned["dir"])
    X_probe, y_probe = demo.load_features(probe["dir"])

    ref = MLPClassifier(hidden_layer_sizes=(64, 32),
                        max_iter=TINY_MAX_ITER, random_state=42)
    ref.fit(X_clean, y_clean)
    cand = MLPClassifier(hidden_layer_sizes=(64, 32),
                         max_iter=TINY_MAX_ITER, random_state=42)
    cand.fit(X_pois, y_pois)

    ref_path = models_dir / "tiny_ref.pkl"
    cand_path = models_dir / "tiny_cand.pkl"
    save_kavach_model(ref, ref_path, _meta("clean"))
    save_kavach_model(cand, cand_path, _meta("poisoned_suite"))

    # Honest trigger transform: genuinely measured features of triggered
    # probe images (via the generator's add_trigger + extract_features).
    probe_dir = Path(probe["dir"])
    with open(probe_dir / "labels.csv", newline="") as f:
        import csv
        rows = list(csv.DictReader(f))
    trig_X = np.stack([
        extract_features(add_trigger(
            Image.open(probe_dir / r["rel_path"]).convert("RGB")))
        for r in rows]).astype(np.float32)

    def trigger_fn(X: np.ndarray) -> np.ndarray:
        assert X.shape[0] == trig_X.shape[0], "batch size must match probe"
        return trig_X

    ref_rec = register_model(ref_path, "tiny-ref", "reference")
    cand_rec = register_model(cand_path, "tiny-cand", "candidate")
    ref_obj, _ = load_kavach_model(ref_path)
    cand_obj, _ = load_kavach_model(cand_path)

    results = run_checks(cand_rec, ref_rec, X_probe, y_probe, trigger_fn,
                         ref_obj, cand_obj)
    return {"ref_rec": ref_rec, "cand_rec": cand_rec,
            "results": {r["check_name"]: r for r in results},
            "X_probe": X_probe, "y_probe": y_probe,
            "ref_obj": ref_obj, "cand_obj": cand_obj, "root": root}


# ---------------------------------------------------------------- white-box

def test_hash_verify_passes(pipeline):
    r = pipeline["results"]["hash_verify"]
    print("\nhash_verify:", r["result"])
    assert r["status"] == "pass"
    assert r["result"]["match"] is True


def test_trigger_flip_rate_measured(pipeline):
    r = pipeline["results"]["trigger_test"]
    res = r["result"]
    print(f"\ntrigger_test: candidate_flip_rate={res['candidate_flip_rate']:.4f} "
          f"reference_flip_rate={res['reference_flip_rate']:.4f} "
          f"diff={res['diff']:+.4f} status={r['status']}")
    assert r["status"] in ("pass", "flag")
    assert res["candidate_flip_rate"] > res["reference_flip_rate"], (
        "backdoored candidate must flip to target more often than reference")


def test_behaviour_compare_measured(pipeline):
    r = pipeline["results"]["behaviour_compare"]
    res = r["result"]
    print(f"\nbehaviour_compare: agreement={res['agreement']:.4f} "
          f"disagreements={res['n_disagreements']} status={r['status']}")
    assert 0.0 <= res["agreement"] < 1.0, (
        "poisoned candidate must disagree with reference on some probes")


def test_weight_stats_measured(pipeline):
    r = pipeline["results"]["weight_stats"]
    print(f"\nweight_stats: max_rel_dev={r['result']['max_rel_dev']:.4f} "
          f"status={r['status']}")
    assert r["status"] in ("pass", "flag")
    assert len(r["result"]["layers"]) == 3  # coefs_: in->64, 64->32, 32->out


def test_strip_inspired_measured(pipeline):
    r = pipeline["results"]["strip_inspired"]
    res = r["result"]
    print(f"\nstrip_inspired: candidate_entropy={res['mean_entropy_bits']:.4f} "
          f"bits reference_entropy={res['reference_mean_entropy_bits']} "
          f"status={r['status']}")
    assert r["status"] in ("pass", "flag")
    assert 0.0 <= res["mean_entropy_bits"] <= np.log2(len(CLASSES))


def test_metadata_check_trusted_pkl(pipeline):
    r = pipeline["results"]["metadata"]
    print("\nmetadata:", r["result"], "|", r["note"])
    assert r["status"] == "pass"
    assert r["result"]["manifest_ok"] == 1
    assert r["result"]["format"] == "sklearn-pkl"


# ---------------------------------------------------------------- black-box

def _dummy_onnx(path: Path) -> None:
    from onnx import TensorProto, helper
    import onnx
    x = helper.make_tensor_value_info("X", TensorProto.FLOAT, [1, 115])
    y = helper.make_tensor_value_info("Y", TensorProto.FLOAT, [1, 3])
    node = helper.make_node("Relu", ["X"], ["Y"])
    graph = helper.make_graph([node], "tiny", [x], [y])
    model = helper.make_model(graph,
                              opset_imports=[helper.make_opsetid("", 17)])
    onnx.save(model, str(path))


def _fake_pt(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("archive/data.pkl", b"\x00" * 256)
        zf.writestr("archive/data/0", b"\x01" * 128)
        zf.writestr("version", b"3")


def _not_a_zip_pt(path: Path) -> None:
    path.write_bytes(b"this is not a zip archive at all")


def test_blackbox_records_metadata_only(tmp_path):
    onnx_path = tmp_path / "dummy.onnx"
    pt_path = tmp_path / "fake.pt"
    bad_pt = tmp_path / "bad.pt"
    _dummy_onnx(onnx_path)
    _fake_pt(pt_path)
    _not_a_zip_pt(bad_pt)

    onnx_rec = register_model(onnx_path, "dummy-onnx", "candidate")
    pt_rec = register_model(pt_path, "fake-pt", "candidate")
    bad_rec = register_model(bad_pt, "bad-pt", "candidate")

    assert onnx_rec["format"] == "onnx"
    assert onnx_rec["manifest_ok"] == 0
    assert onnx_rec["metadata"]["inputs"] == ["X"]
    assert onnx_rec["metadata"]["outputs"] == ["Y"]
    assert onnx_rec["metadata"]["node_count"] == 1
    assert onnx_rec["metadata"]["opset_import"] == {"": 17}

    assert pt_rec["format"] == "torch-pt"
    assert pt_rec["metadata"]["num_records"] == 3
    names = {r["name"] for r in pt_rec["metadata"]["records"]}
    assert names == {"archive/data.pkl", "archive/data/0", "version"}

    assert bad_rec["metadata"]["parse"] == "unavailable"

    rng = np.random.default_rng(0)
    X = rng.random((10, 115), dtype=np.float32)
    y = rng.integers(0, 3, size=10)
    for rec in (onnx_rec, pt_rec):
        results = {r["check_name"]: r
                   for r in run_checks(rec, None, X, y, None, None, None)}
        # file-level checks still work on metadata-only records
        assert results["hash_verify"]["status"] == "pass"
        assert results["metadata"]["status"] == "pass"
        # every model-access check is honestly unavailable
        for name in ("behaviour_compare", "trigger_test", "weight_stats",
                     "strip_inspired"):
            r = results[name]
            assert r["status"] == "unavailable", name
            assert UNAVAILABLE_NOTE in r["note"], name
            print(f"\n{rec['format']}/{name}: unavailable (exact note OK)")


# ---------------------------------------------------------------- untrusted

def test_untrusted_pickle_not_executed(tmp_path):
    foreign = tmp_path / "foreign.pkl"
    with open(foreign, "wb") as f:
        pickle.dump({"not": "a kavach model", "exec": "never"}, f)
    rec = register_model(foreign, "foreign", "candidate")
    assert rec["format"] == "sklearn-pkl"
    assert rec["manifest_ok"] == 0
    assert rec["metadata"]["executable"] is False
    # and load_kavach_model refuses outright:
    with pytest.raises(UntrustedModelError):
        load_kavach_model(foreign)

    # signed then tampered -> digest mismatch -> not executed
    signed = tmp_path / "signed.pkl"
    save_kavach_model({"a": 1}, signed, {"classes": CLASSES})
    with open(signed, "ab") as f:
        f.write(b"\x00")
    rec2 = register_model(signed, "tampered", "candidate")
    assert rec2["manifest_ok"] == 0
    assert rec2["metadata"]["executable"] is False
    with pytest.raises(UntrustedModelError):
        load_kavach_model(signed)

    # metadata check flags untrusted pickles
    results = {r["check_name"]: r
               for r in run_checks(rec, None, np.zeros((2, 115),
                                                       dtype=np.float32),
                                   np.zeros(2, dtype=np.int64),
                                   None, None, None)}
    assert results["metadata"]["status"] == "flag"
    print("\nuntrusted pickle: manifest_ok=0, execution refused, "
          "metadata check flags")
