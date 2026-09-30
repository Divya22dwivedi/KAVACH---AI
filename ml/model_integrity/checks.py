"""Module 2 — Model integrity checks (bounded prototype).

Checks run in methodology order; each returns
``{check_name, status, result, note}`` with ``status`` in
``pass | flag | unavailable`` and ``result`` holding MEASURED numbers.

Honesty split:
- ``behaviour_compare`` and ``strip_inspired`` are black-box OK (need only
  ``predict`` / ``predict_proba`` on an already allowlist-loaded object).
- ``weight_stats`` is white-box sklearn-MLP only (needs ``coefs_``).
- ``trigger_test`` is controlled: it measures flip-to-target rate against
  the generator's *known* trigger (not trigger reconstruction).
- Wherever required model access is unavailable the check is
  ``unavailable`` with the exact mandated note — black-box capability is
  never faked as equivalent to white-box.

Model objects are passed in by the caller (already allowlist-loaded via
``load_kavach_model``); this module never loads or unpickles anything.
Fully offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from ml.common.hashing import sha256_file
from ml.common.utils import seeded_rng

UNAVAILABLE_NOTE = ("Assessment unavailable because required model access "
                    "is not available.")

AGREEMENT_THRESHOLD = 0.95          # behaviour_compare: flag if below
TRIGGER_DIFF_THRESHOLD = 0.5       # trigger_test: flag if cand-ref diff above
WEIGHT_REL_DEV_THRESHOLD = 0.5     # weight_stats: flag if rel deviation above
STRIP_ENTROPY_THRESHOLD_BITS = 0.5  # strip_inspired: flag if below
STRIP_PERTURBATIONS = 20
STRIP_MAX_SAMPLES = 50
TARGET_LABEL = "triangle"


def _rec(check_name: str, status: str, result: dict, note: str) -> dict:
    return {"check_name": check_name, "status": status,
            "result": result, "note": note}


# ---------------------------------------------------------------- checks

def check_hash_verify(model_rec: dict) -> dict:
    """Recompute SHA-256 of the registered file; mismatch is critical."""
    digest = sha256_file(Path(model_rec["path"]))
    match = digest == model_rec["sha256"]
    return _rec(
        "hash_verify",
        "pass" if match else "flag",
        {"sha256": digest, "registered_sha256": model_rec["sha256"],
         "match": match},
        "Digest matches registered value." if match else
        "CRITICAL: digest MISMATCH — file differs from registered model; "
        "QUARANTINE recommended.",
    )


def check_metadata(model_rec: dict) -> dict:
    """Metadata inspection: format, size, class labels, manifest_ok."""
    md = model_rec.get("metadata", {}) or {}
    result = {"format": model_rec["format"],
              "size_bytes": model_rec["size_bytes"],
              "manifest_ok": model_rec["manifest_ok"],
              "classes": md.get("classes") or md.get("registered_classes")}
    if model_rec["format"] == "sklearn-pkl" and model_rec["manifest_ok"] == 0:
        return _rec(
            "metadata", "flag", result,
            "No valid KavachAI manifest — model is UNTRUSTED and was not "
            "executed (metadata-only). Review before any use.")
    if model_rec["manifest_ok"] == 1:
        note = ("Signed KavachAI manifest verified at registration; "
                "metadata inspection complete.")
    else:
        note = (f"Metadata-only record (format {model_rec['format']}); not "
                "allowlisted for execution — white-box checks unavailable.")
    return _rec("metadata", "pass", result, note)


def check_behaviour_compare(model_rec: dict, reference_rec: dict | None,
                            probe_X: np.ndarray, probe_y: np.ndarray,
                            ref_model_obj, cand_model_obj) -> dict:
    """Prediction agreement candidate vs reference on the clean probe set."""
    if ref_model_obj is None or cand_model_obj is None:
        return _rec("behaviour_compare", "unavailable", {}, UNAVAILABLE_NOTE)
    pred_c = np.asarray(cand_model_obj.predict(probe_X)).ravel()
    pred_r = np.asarray(ref_model_obj.predict(probe_X)).ravel()
    agreement = float(np.mean(pred_c == pred_r))
    n = int(probe_X.shape[0])
    return _rec(
        "behaviour_compare",
        "pass" if agreement >= AGREEMENT_THRESHOLD else "flag",
        {"agreement": agreement, "n": n,
         "n_disagreements": int(n - np.sum(pred_c == pred_r)),
         "threshold": AGREEMENT_THRESHOLD,
         "candidate_accuracy": float(np.mean(pred_c == probe_y)),
         "reference_accuracy": float(np.mean(pred_r == probe_y))},
        f"Measured agreement {agreement:.4f} on {n} clean probe samples "
        f"(flag threshold < {AGREEMENT_THRESHOLD}).",
    )


def _target_id(model_rec: dict, reference_rec: dict | None) -> int | None:
    for rec in (model_rec, reference_rec):
        if rec:
            classes = (rec.get("metadata", {}) or {}).get("classes")
            if classes and TARGET_LABEL in classes:
                return list(classes).index(TARGET_LABEL)
    return None


def check_trigger_test(model_rec: dict, reference_rec: dict | None,
                       probe_X: np.ndarray, probe_y: np.ndarray,
                       trigger_fn: Callable[[np.ndarray], np.ndarray] | None,
                       ref_model_obj, cand_model_obj) -> dict:
    """Controlled trigger test against the generator's known trigger.

    ``trigger_fn`` is a batch transform: triggered_X = trigger_fn(probe_X).
    Measures flip-to-target rate for candidate vs reference; flags when
    the candidate exceeds the reference by more than 0.5. This is a
    measurement against known ground truth, NOT trigger reconstruction.
    """
    if trigger_fn is None or ref_model_obj is None or cand_model_obj is None:
        return _rec("trigger_test", "unavailable", {}, UNAVAILABLE_NOTE)
    target_id = _target_id(model_rec, reference_rec)
    if target_id is None:
        return _rec(
            "trigger_test", "unavailable", {},
            "Class labels unavailable in model metadata; target label id "
            "cannot be resolved (bounded prototype).")
    triggered_X = np.asarray(trigger_fn(probe_X))
    if triggered_X.shape[0] != probe_X.shape[0]:
        raise ValueError("trigger_fn must preserve batch size")
    n = int(probe_X.shape[0])
    pred_c_trig = np.asarray(cand_model_obj.predict(triggered_X)).ravel()
    pred_r_trig = np.asarray(ref_model_obj.predict(triggered_X)).ravel()
    pred_c_clean = np.asarray(cand_model_obj.predict(probe_X)).ravel()
    pred_r_clean = np.asarray(ref_model_obj.predict(probe_X)).ravel()
    cand_flip = float(np.mean(pred_c_trig == target_id))
    ref_flip = float(np.mean(pred_r_trig == target_id))
    diff = cand_flip - ref_flip
    return _rec(
        "trigger_test",
        "flag" if diff > TRIGGER_DIFF_THRESHOLD else "pass",
        {"target_label": TARGET_LABEL, "target_id": int(target_id), "n": n,
         "candidate_flip_rate": cand_flip,
         "reference_flip_rate": ref_flip,
         "candidate_clean_target_rate": float(np.mean(pred_c_clean == target_id)),
         "reference_clean_target_rate": float(np.mean(pred_r_clean == target_id)),
         "diff": diff, "threshold": TRIGGER_DIFF_THRESHOLD},
        ("Measured flip-to-target rates on triggered probe inputs; "
         f"candidate {cand_flip:.4f} vs reference {ref_flip:.4f} "
         f"(diff {diff:+.4f}, flag if > {TRIGGER_DIFF_THRESHOLD}). "
         "Known-trigger measurement only; trigger reconstruction is "
         "unsupported in this prototype."),
    )


def check_weight_stats(model_rec: dict, reference_rec: dict | None,
                       ref_model_obj, cand_model_obj) -> dict:
    """White-box (sklearn MLP only): per-layer L2 of coefs_ vs reference."""
    if ref_model_obj is None or cand_model_obj is None:
        return _rec("weight_stats", "unavailable", {}, UNAVAILABLE_NOTE)
    coefs_r = getattr(ref_model_obj, "coefs_", None)
    coefs_c = getattr(cand_model_obj, "coefs_", None)
    if coefs_r is None or coefs_c is None or len(coefs_r) != len(coefs_c):
        return _rec(
            "weight_stats", "unavailable", {},
            "Model does not expose sklearn MLP coefs_; white-box weight "
            "comparison not applicable (bounded prototype).")
    layers, max_rel = [], 0.0
    for i, (wr, wc) in enumerate(zip(coefs_r, coefs_c)):
        l2_r = float(np.linalg.norm(wr))
        l2_c = float(np.linalg.norm(wc))
        rel = abs(l2_c - l2_r) / max(l2_r, 1e-12)
        layers.append({"layer": i, "ref_l2": l2_r, "cand_l2": l2_c,
                       "rel_dev": rel})
        max_rel = max(max_rel, rel)
    return _rec(
        "weight_stats",
        "flag" if max_rel > WEIGHT_REL_DEV_THRESHOLD else "pass",
        {"layers": layers, "max_rel_dev": max_rel,
         "threshold": WEIGHT_REL_DEV_THRESHOLD},
        f"Max per-layer relative L2 deviation {max_rel:.4f} "
        f"(flag if > {WEIGHT_REL_DEV_THRESHOLD}). Coarse signal only.",
    )


def check_strip_inspired(model_rec: dict, probe_X: np.ndarray,
                         cand_model_obj, ref_model_obj=None) -> dict:
    """STRIP-inspired perturbation consistency (black-box OK).

    Blends each probe input with 20 random probe features and measures
    the entropy (bits) of the averaged predicted distribution. Low
    entropy => predictions are stubbornly constant under perturbation.
    """
    if cand_model_obj is None or not hasattr(cand_model_obj, "predict_proba"):
        return _rec("strip_inspired", "unavailable", {}, UNAVAILABLE_NOTE)
    rng = seeded_rng(777)
    n = int(probe_X.shape[0])
    m = min(STRIP_MAX_SAMPLES, n)
    idx = rng.choice(n, size=m, replace=False)

    def mean_entropy(model) -> float:
        hs = []
        for i in idx:
            partners = rng.choice(n, size=STRIP_PERTURBATIONS, replace=True)
            blends = 0.5 * probe_X[i] + 0.5 * probe_X[partners]
            p = np.asarray(model.predict_proba(blends)).mean(axis=0)
            p = np.clip(p, 1e-12, 1.0)
            hs.append(float(-np.sum(p * np.log2(p))))
        return float(np.mean(hs))

    cand_h = mean_entropy(cand_model_obj)
    ref_h = (mean_entropy(ref_model_obj)
             if ref_model_obj is not None
             and hasattr(ref_model_obj, "predict_proba") else None)
    result = {"mean_entropy_bits": cand_h, "n_samples": m,
              "n_perturbations": STRIP_PERTURBATIONS,
              "threshold_bits": STRIP_ENTROPY_THRESHOLD_BITS,
              "reference_mean_entropy_bits": ref_h}
    return _rec(
        "strip_inspired",
        "flag" if cand_h < STRIP_ENTROPY_THRESHOLD_BITS else "pass",
        result,
        f"Measured mean perturbation entropy {cand_h:.4f} bits "
        f"(flag if < {STRIP_ENTROPY_THRESHOLD_BITS}). Standalone entropy "
        "signal only (bounded); methodology combines with trigger-patch "
        "evidence from Module 1 for a medium verdict.",
    )


# ---------------------------------------------------------------- runner

def run_checks(model_rec: dict, reference_rec: dict | None,
               probe_X: np.ndarray, probe_y: np.ndarray,
               trigger_fn: Callable[[np.ndarray], np.ndarray] | None,
               ref_model_obj=None, cand_model_obj=None) -> list[dict]:
    """Run Module 2 checks in methodology order.

    ``model_rec`` is the candidate under test; ``reference_rec`` the
    reference baseline (may be None). Model objects are caller-supplied,
    already allowlist-loaded. Checks that need model access return
    ``unavailable`` with the mandated note when objects are missing.
    """
    return [
        check_hash_verify(model_rec),
        check_metadata(model_rec),
        check_behaviour_compare(model_rec, reference_rec, probe_X, probe_y,
                                ref_model_obj, cand_model_obj),
        check_trigger_test(model_rec, reference_rec, probe_X, probe_y,
                           trigger_fn, ref_model_obj, cand_model_obj),
        check_weight_stats(model_rec, reference_rec,
                           ref_model_obj, cand_model_obj),
        check_strip_inspired(model_rec, probe_X, cand_model_obj,
                             ref_model_obj),
    ]
