"""Reference-distribution fitting for Module 4 (prototype).

Reference stats:
  * mean (115-dim) and inverse covariance from the feature matrix.
  * Covariance is Ledoit-Wolf shrunk (``sklearn.covariance.LedoitWolf``);
    the Mahalanobis metric uses its ``precision_`` (inverse covariance).
  * q95 / q99 quantiles of the reference-set Mahalanobis distances — these
    are the *measured* anomaly thresholds (never hand-tuned).
  * Quality signals: brightness mean/var, blur mean, resolution histogram.

Persistence: npz via :func:`save_reference` / :func:`load_reference`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np
from PIL import Image
from sklearn.covariance import LedoitWolf

from ml.common.features import FEATURE_DIM, extract_features

# Feature-vector column indices (see ml/common/features.py docstring).
_BRIGHTNESS_COL = 112
_CONTRAST_COL = 113
_BLUR_COL = 114


def _resolution_histogram(
    resolutions: Optional[Iterable[tuple[int, int]]],
) -> Dict[str, int]:
    hist: Dict[str, int] = {}
    for w, h in resolutions or []:
        key = f"{int(w)}x{int(h)}"
        hist[key] = hist.get(key, 0) + 1
    return hist


def fit_reference(X: np.ndarray, seed: int,
                  resolutions: Optional[Iterable[tuple[int, int]]] = None
                  ) -> dict:
    """Fit the reference distribution over a feature matrix.

    Args:
        X: ``(n, 115)`` feature matrix (see :func:`extract_features`).
        seed: RNG seed recorded with the reference (documented as part of
            run parameters; the fit itself is deterministic).
        resolutions: optional ``(width, height)`` pairs for the resolution
            histogram quality signal.

    Returns:
        dict with keys ``mean``, ``cov_inv``, ``q95``, ``q99``,
        ``quality`` (``brightness_mean``, ``brightness_var``,
        ``blur_mean``, ``resolution_histogram``), ``n``, ``seed``,
        ``feature_dim``.
    """
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2 or X.shape[1] != FEATURE_DIM:
        raise ValueError(f"expected X with shape (n, {FEATURE_DIM}), "
                         f"got {X.shape}")
    n = X.shape[0]
    if n < 2:
        raise ValueError("need at least 2 samples to fit a reference")

    lw = LedoitWolf().fit(X)
    mean = X.mean(axis=0)
    cov_inv = np.asarray(lw.precision_, dtype=np.float64)

    distances = _mahalanobis(X, mean, cov_inv)
    q95 = float(np.quantile(distances, 0.95))
    q99 = float(np.quantile(distances, 0.99))

    brightness = X[:, _BRIGHTNESS_COL]
    quality = {
        "brightness_mean": float(brightness.mean()),
        "brightness_var": float(brightness.var()),
        "blur_mean": float(X[:, _BLUR_COL].mean()),
        "resolution_histogram": _resolution_histogram(resolutions),
    }
    return {
        "mean": mean,
        "cov_inv": cov_inv,
        "q95": q95,
        "q99": q99,
        "quality": quality,
        "n": int(n),
        "seed": int(seed),
        "feature_dim": int(FEATURE_DIM),
    }


def fit_reference_from_images(images: Iterable[Image.Image],
                              seed: int) -> dict:
    """Convenience wrapper: extract features + resolutions, then fit."""
    imgs = list(images)
    X = np.stack([extract_features(im) for im in imgs])
    resolutions = [im.size for im in imgs]
    return fit_reference(X, seed, resolutions=resolutions)


def _mahalanobis(X: np.ndarray, mean: np.ndarray,
                 cov_inv: np.ndarray) -> np.ndarray:
    diff = X - mean
    d2 = np.einsum("ij,jk,ik->i", diff, cov_inv, diff)
    return np.sqrt(np.clip(d2, 0.0, None))


# ------------------------------------------------------------------ persist

def save_reference(path: str | Path, ref: dict) -> Path:
    """Persist a fitted reference to ``.npz``."""
    path = Path(path)
    res_hist = ref.get("quality", {}).get("resolution_histogram", {}) or {}
    res_labels = np.array(sorted(res_hist), dtype="<U32")
    res_counts = np.array([int(res_hist[k]) for k in sorted(res_hist)],
                          dtype=np.int64)
    np.savez(
        path,
        mean=np.asarray(ref["mean"], dtype=np.float64),
        cov_inv=np.asarray(ref["cov_inv"], dtype=np.float64),
        q95=np.asarray(float(ref["q95"]), dtype=np.float64),
        q99=np.asarray(float(ref["q99"]), dtype=np.float64),
        brightness_mean=np.asarray(
            float(ref["quality"]["brightness_mean"]), dtype=np.float64),
        brightness_var=np.asarray(
            float(ref["quality"]["brightness_var"]), dtype=np.float64),
        blur_mean=np.asarray(float(ref["quality"]["blur_mean"]),
                             dtype=np.float64),
        res_labels=res_labels,
        res_counts=res_counts,
        n=np.asarray(int(ref["n"]), dtype=np.int64),
        seed=np.asarray(int(ref["seed"]), dtype=np.int64),
        feature_dim=np.asarray(int(ref["feature_dim"]), dtype=np.int64),
    )
    return path


def load_reference(path: str | Path) -> dict:
    """Load a reference persisted by :func:`save_reference`."""
    z = np.load(Path(path))
    res_labels = [str(x) for x in z["res_labels"]]
    res_counts = [int(x) for x in z["res_counts"]]
    return {
        "mean": np.asarray(z["mean"], dtype=np.float64),
        "cov_inv": np.asarray(z["cov_inv"], dtype=np.float64),
        "q95": float(z["q95"]),
        "q99": float(z["q99"]),
        "quality": {
            "brightness_mean": float(z["brightness_mean"]),
            "brightness_var": float(z["brightness_var"]),
            "blur_mean": float(z["blur_mean"]),
            "resolution_histogram": dict(zip(res_labels, res_counts)),
        },
        "n": int(z["n"]),
        "seed": int(z["seed"]),
        "feature_dim": int(z["feature_dim"]),
    }
