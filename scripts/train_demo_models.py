"""Phase 5 demo: train reference + backdoored candidate MLP models.

- Reference MLPClassifier trained on the CLEAN dataset.
- Candidate MLPClassifier (same arch/seed) trained on the POISONED
  dataset from attack_generator.full_suite (trigger_patch attack plants a
  5x5 white patch -> TARGET_LABEL "triangle").
- Models saved via save_kavach_model (signed manifest) to
  models/kavach_mlp_ref.pkl and models/kavach_mlp_cand.pkl.
- 200 clean held-out probe images -> features saved to models/probe.npz
  (X, y as int label ids, classes list).

Bounded prototype: small synthetic data, tiny MLP. Must complete < 120 s.
Fully offline. Run from the repo root:
    .venv/bin/python scripts/train_demo_models.py
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.neural_network import MLPClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attack_generator.generate import (  # noqa: E402
    CLASSES, full_suite, make_clean_dataset,
)
from ml.common.features import extract_features  # noqa: E402
from ml.common.model_io import save_kavach_model  # noqa: E402

SEED = 42
N = 600
PROBE_SEED = 2026
PROBE_N = 200
TIME_BUDGET_S = 120


def load_features(ds_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """Extract features for every row of a generated dataset's labels.csv."""
    ds_dir = Path(ds_dir)
    xs, ys = [], []
    with open(ds_dir / "labels.csv", newline="") as f:
        for row in csv.DictReader(f):
            img = Image.open(ds_dir / row["rel_path"]).convert("RGB")
            xs.append(extract_features(img))
            ys.append(CLASSES.index(row["label"]))
    return (np.stack(xs).astype(np.float32),
            np.asarray(ys, dtype=np.int64))


def train(X: np.ndarray, y: np.ndarray, seed: int) -> MLPClassifier:
    clf = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300,
                        random_state=seed)
    clf.fit(X, y)
    return clf


def main() -> None:
    t0 = time.time()
    ds_root = ROOT / "datasets" / "generated"
    models_dir = ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] generating clean dataset ...", flush=True)
    clean_info = make_clean_dataset(ds_root, seed=SEED, n=N, name="clean")
    print("[2/5] generating poisoned dataset (full_suite) ...", flush=True)
    poisoned_info = full_suite(ds_root, seed=SEED, n=N)
    print("[3/5] generating probe images ...", flush=True)
    probe_info = make_clean_dataset(ds_root, seed=PROBE_SEED, n=PROBE_N,
                                    name="probe")

    print("[4/5] extracting features + training models ...", flush=True)
    X_clean, y_clean = load_features(clean_info["dir"])
    X_pois, y_pois = load_features(poisoned_info["dir"])
    X_probe, y_probe = load_features(probe_info["dir"])

    ref = train(X_clean, y_clean, SEED)
    cand = train(X_pois, y_pois, SEED)
    ref_acc = float(ref.score(X_clean, y_clean))
    cand_acc = float(cand.score(X_pois, y_pois))
    print(f"      ref train acc={ref_acc:.4f}  cand train acc={cand_acc:.4f}",
          flush=True)

    print("[5/5] saving models + probe set ...", flush=True)
    ref_manifest = save_kavach_model(
        ref, models_dir / "kavach_mlp_ref.pkl",
        {"arch": "MLPClassifier", "hidden_layer_sizes": [64, 32],
         "max_iter": 300, "classes": CLASSES, "trained_on": "clean",
         "seed": SEED})
    cand_manifest = save_kavach_model(
        cand, models_dir / "kavach_mlp_cand.pkl",
        {"arch": "MLPClassifier", "hidden_layer_sizes": [64, 32],
         "max_iter": 300, "classes": CLASSES, "trained_on": "poisoned_suite",
         "seed": SEED})
    np.savez(models_dir / "probe.npz", X=X_probe, y=y_probe,
             classes=np.array(CLASSES))

    elapsed = time.time() - t0
    print(f"saved: {models_dir / 'kavach_mlp_ref.pkl'} "
          f"(sha256 {ref_manifest['sha256'][:12]}...)")
    print(f"saved: {models_dir / 'kavach_mlp_cand.pkl'} "
          f"(sha256 {cand_manifest['sha256'][:12]}...)")
    print(f"saved: {models_dir / 'probe.npz'} "
          f"(X {X_probe.shape}, y {y_probe.shape})")
    print(f"elapsed {elapsed:.1f}s (budget {TIME_BUDGET_S}s)")
    if elapsed >= TIME_BUDGET_S:
        raise SystemExit(f"TIME BUDGET EXCEEDED: {elapsed:.1f}s >= "
                         f"{TIME_BUDGET_S}s")


if __name__ == "__main__":
    main()
