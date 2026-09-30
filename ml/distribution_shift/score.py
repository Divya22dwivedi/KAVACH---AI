"""Scoring and batch assessment for Module 4 (prototype).

Per-image score: Mahalanobis distance
    d = sqrt((x - mu)^T Sigma^{-1} (x - mu))

Anomaly vote: d > q99 (threshold measured from the *reference* fit).
Batch verdicts from the measured anomaly fraction (per docs/ml-methodology.md):
    anomaly_fraction < 0.05  -> NORMAL
    0.05 <= f <= 0.20        -> EXPECTED_DRIFT
    f > 0.20                 -> SUSPICIOUS_SHIFT

Quality-signal deltas (brightness/blur means, current minus reference) are
reported for context only; they never drive the verdict.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ml.common.features import FEATURE_DIM
from ml.distribution_shift.disclaimer import DISCLAIMER

VERDICT_NORMAL = "NORMAL"
VERDICT_EXPECTED_DRIFT = "EXPECTED_DRIFT"
VERDICT_SUSPICIOUS_SHIFT = "SUSPICIOUS_SHIFT"

_BRIGHTNESS_COL = 112
_BLUR_COL = 114


def mahalanobis_distances(ref: dict, X: np.ndarray) -> np.ndarray:
    """Mahalanobis distances of rows of X against the fitted reference."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2 or X.shape[1] != FEATURE_DIM:
        raise ValueError(f"expected X with shape (n, {FEATURE_DIM}), "
                         f"got {X.shape}")
    mean = np.asarray(ref["mean"], dtype=np.float64)
    cov_inv = np.asarray(ref["cov_inv"], dtype=np.float64)
    diff = X - mean
    d2 = np.einsum("ij,jk,ik->i", diff, cov_inv, diff)
    return np.sqrt(np.clip(d2, 0.0, None))


def assess(ref: dict, X_current: np.ndarray,
           sample_ids: Optional[list[str]] = None) -> dict:
    """Assess a current batch against the reference distribution.

    Returns dict with:
      * ``verdict``: NORMAL | EXPECTED_DRIFT | SUSPICIOUS_SHIFT
      * ``metrics``: n, anomaly_fraction, q95/q99 reference thresholds,
        observed distance quantiles, mean_distance, quality_deltas
      * ``per_sample``: [{sample_id, distance, anomalous}]
      * ``disclaimer``: mandatory shift-not-malice disclaimer string
    """
    X_current = np.asarray(X_current, dtype=np.float64)
    if X_current.ndim != 2 or X_current.shape[1] != FEATURE_DIM:
        raise ValueError(f"expected X_current with shape (n, {FEATURE_DIM}), "
                         f"got {X_current.shape}")
    n = X_current.shape[0]
    if n == 0:
        raise ValueError("cannot assess an empty batch")

    if sample_ids is None:
        sample_ids = [f"s{i:06d}" for i in range(n)]
    if len(sample_ids) != n:
        raise ValueError("sample_ids length must match batch size")

    distances = mahalanobis_distances(ref, X_current)
    q99 = float(ref["q99"])
    anomalous = distances > q99
    anomaly_fraction = float(anomalous.mean())

    if anomaly_fraction < 0.05:
        verdict = VERDICT_NORMAL
    elif anomaly_fraction <= 0.20:
        verdict = VERDICT_EXPECTED_DRIFT
    else:
        verdict = VERDICT_SUSPICIOUS_SHIFT

    # Quality-signal deltas: current mean minus reference mean
    # (informational only; never drive the verdict).
    ref_quality = ref.get("quality", {})
    quality_deltas = {
        "brightness_mean_delta": float(X_current[:, _BRIGHTNESS_COL].mean()
                                       - ref_quality.get("brightness_mean", 0.0)),
        "blur_mean_delta": float(X_current[:, _BLUR_COL].mean()
                                 - ref_quality.get("blur_mean", 0.0)),
    }

    return {
        "verdict": verdict,
        "metrics": {
            "n": int(n),
            "anomaly_fraction": anomaly_fraction,
            "anomalous_count": int(anomalous.sum()),
            "q95_threshold": float(ref["q95"]),   # measured on reference
            "q99_threshold": float(ref["q99"]),   # measured on reference
            "observed_q95": float(np.quantile(distances, 0.95)),
            "observed_q99": float(np.quantile(distances, 0.99)),
            "mean_distance": float(distances.mean()),
            "quality_deltas": quality_deltas,
        },
        "per_sample": [
            {
                "sample_id": sid,
                "distance": float(d),
                "anomalous": bool(a),
            }
            for sid, d, a in zip(sample_ids, distances, anomalous)
        ],
        "disclaimer": DISCLAIMER,
    }
