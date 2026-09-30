"""Phase-7 tests: distribution-shift module (prototype).

Data comes from attack_generator (seeded): clean synthetic shapes for the
reference/held-out sets, brightness-shifted copies, and draw_ood noise.

All assertions are on *measured* values — thresholds from reference
quantiles, verdicts from measured anomaly fractions. No fabricated
thresholds anywhere.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attack_generator.generate import CLASSES, draw_ood, draw_shape  # noqa: E402
from ml.common.features import extract_features  # noqa: E402
from ml.common.utils import seeded_rng  # noqa: E402
from ml.distribution_shift import (  # noqa: E402
    DISCLAIMER,
    assess,
    fit_reference,
    load_reference,
    save_reference,
)

EXPECTED_DISCLAIMER = (
    "Distribution shift indicates deviation from the reference distribution; "
    "it does not by itself establish malicious manipulation."
)

SEED = 123
N_REF, N_HELD, N_OOD = 400, 200, 200


def _features(images):
    return np.stack([extract_features(im) for im in images])


@pytest.fixture(scope="module")
def data():
    """Reference (400) + held-out clean (200) + shifted (200) + OOD (200)."""
    rng = seeded_rng(SEED)
    ref_imgs = [draw_shape(rng, CLASSES[i % len(CLASSES)])
                for i in range(N_REF)]
    held_imgs = [draw_shape(rng, CLASSES[i % len(CLASSES)])
                 for i in range(N_HELD)]
    # Brightness shift x1.35 via in-memory image edit (test (b)).
    bright_imgs = []
    for im in held_imgs:
        arr = np.asarray(im).astype(np.float32) * 1.35
        bright_imgs.append(
            Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB"))
    ood_imgs = [draw_ood(rng) for _ in range(N_OOD)]
    return {
        "X_ref": _features(ref_imgs),
        "X_held": _features(held_imgs),
        "X_bright": _features(bright_imgs),
        "X_ood": _features(ood_imgs),
    }


@pytest.fixture(scope="module")
def reference(data):
    return fit_reference(data["X_ref"], seed=SEED)


def test_held_out_clean_is_normal(reference, data):
    res = assess(reference, data["X_held"])
    frac = res["metrics"]["anomaly_fraction"]
    print(f"\n(a) held-out clean: verdict={res['verdict']} "
          f"anomaly_fraction={frac:.4f}")
    assert res["verdict"] == "NORMAL"
    assert frac < 0.05


def test_brightness_shift_is_drift_or_suspicious(reference, data):
    res = assess(reference, data["X_bright"])
    frac = res["metrics"]["anomaly_fraction"]
    print(f"\n(b) brightness x1.35: verdict={res['verdict']} "
          f"anomaly_fraction={frac:.4f}")
    assert res["verdict"] in ("EXPECTED_DRIFT", "SUSPICIOUS_SHIFT")
    assert res["metrics"]["quality_deltas"]["brightness_mean_delta"] > 0.0


def test_ood_noise_is_suspicious_shift(reference, data):
    res = assess(reference, data["X_ood"])
    frac = res["metrics"]["anomaly_fraction"]
    print(f"\n(c) OOD noise: verdict={res['verdict']} "
          f"anomaly_fraction={frac:.4f}")
    assert res["verdict"] == "SUSPICIOUS_SHIFT"
    assert frac > 0.2


def test_disclaimer_present(reference, data):
    res = assess(reference, data["X_held"])
    assert res["disclaimer"] == EXPECTED_DISCLAIMER
    assert res["disclaimer"] == DISCLAIMER


def test_save_load_roundtrip_preserves_verdict(reference, data, tmp_path):
    path = tmp_path / "ref.npz"
    save_reference(path, reference)
    assert path.exists()
    ref2 = load_reference(path)
    assert ref2["mean"].shape == (115,)
    assert ref2["cov_inv"].shape == (115, 115)
    np.testing.assert_allclose(ref2["mean"], reference["mean"])
    np.testing.assert_allclose(ref2["cov_inv"], reference["cov_inv"])
    assert ref2["q95"] == pytest.approx(reference["q95"])
    assert ref2["q99"] == pytest.approx(reference["q99"])

    r1 = assess(reference, data["X_held"])
    r2 = assess(ref2, data["X_held"])
    assert r2["verdict"] == r1["verdict"]
    assert r2["metrics"]["anomaly_fraction"] == pytest.approx(
        r1["metrics"]["anomaly_fraction"])
    r3 = assess(ref2, data["X_ood"])
    assert r3["verdict"] == "SUSPICIOUS_SHIFT"
