"""KavachAI — Module 4: Distribution shift (prototype).

Fits a reference distribution over 115-dim image features
(:mod:`ml.common.features`) and scores new batches by Mahalanobis distance
against it.

Conventions (from docs/ml-methodology.md, Module 4):
  * Thresholds come from *reference-set quantiles* (q95/q99), never
    hand-tuned.
  * Batch verdicts come from the *measured* anomaly fraction:
    < 5% -> NORMAL, 5-20% -> EXPECTED_DRIFT, > 20% -> SUSPICIOUS_SHIFT.
  * Every assessment carries a mandatory disclaimer: a measured shift is
    evidence of *deviation*, not proof of malicious manipulation.

Prototype language: honest, measurement-first, no invented facts.
"""

from ml.distribution_shift.disclaimer import DISCLAIMER
from ml.distribution_shift.reference import (
    fit_reference,
    fit_reference_from_images,
    load_reference,
    save_reference,
)
from ml.distribution_shift.score import (
    VERDICT_EXPECTED_DRIFT,
    VERDICT_NORMAL,
    VERDICT_SUSPICIOUS_SHIFT,
    assess,
    mahalanobis_distances,
)

__all__ = [
    "DISCLAIMER",
    "VERDICT_EXPECTED_DRIFT",
    "VERDICT_NORMAL",
    "VERDICT_SUSPICIOUS_SHIFT",
    "assess",
    "fit_reference",
    "fit_reference_from_images",
    "load_reference",
    "mahalanobis_distances",
    "save_reference",
]
