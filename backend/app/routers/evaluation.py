"""Evaluation: scan findings vs attack-manifest ground truth.

Per-method precision/recall/F1/FPR + confusion, all measured. Methods
without sample-level attribution or without a manifest return
{"status": "Not evaluated yet"} — never invented numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import service

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])

# detection_method -> attack_type mapping (sample-attributable only)
_METHOD_ATTACK = {
    "trigger_patch": "trigger_patch",      # pca outlier + patch heuristic
    "near_duplicate": "near_duplicate",    # exact_sha256 + dhash_graph
    "ood": "ood",                          # pca outlier without patch flag
}


def _sample_sets(scan_id: str) -> dict[str, set[str]]:
    """Predicted positive sample sets per evaluation method."""
    c = service.con()
    trigger, near_dup, rep_no_patch = set(), set(), set()
    for f in c.execute(
            "SELECT asset_id, detection_method, evidence_json FROM findings "
            "WHERE scan_id = ?", (scan_id,)).fetchall():
        dm = f["detection_method"]
        try:
            ev = json.loads(f["evidence_json"] or "{}")
        except Exception:
            ev = {}
        members = ev.get("members") if isinstance(ev, dict) else None
        if dm in ("exact_sha256", "dhash_graph"):
            if isinstance(members, list):
                near_dup.update(str(m) for m in members)
        elif dm == "pca_reconstruction_outlier":
            sid = f["asset_id"]
            if isinstance(ev, dict) and "trigger_patch_heuristic" in ev:
                trigger.add(sid)
            else:
                rep_no_patch.add(sid)
    return {"trigger_patch": trigger, "near_duplicate": near_dup,
            "ood": rep_no_patch}


def _ground_truth(dataset_id: str) -> dict[str, set[str]]:
    c = service.con()
    gt: dict[str, set[str]] = {}
    for m in c.execute(
            "SELECT attack_type, affected_samples_json FROM attack_manifests "
            "WHERE dataset_id = ?", (dataset_id,)).fetchall():
        gt.setdefault(m["attack_type"], set()).update(
            str(s) for s in json.loads(m["affected_samples_json"]))
    return gt


def _prf(tp: int, fp: int, tn: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "fpr": fpr,
            "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn}}


def evaluate_scan(scan_id: str) -> dict:
    """Core evaluation logic (shared with reports + demo)."""
    try:
        sc = service.get_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    gt = _ground_truth(sc["dataset_id"])
    if not gt:
        return {"status": "Not evaluated yet"}
    universe_rows = service.con().execute(
        "SELECT rel_path FROM dataset_samples WHERE dataset_id = ?",
        (sc["dataset_id"],)).fetchall()
    universe = {Path(r["rel_path"]).stem for r in universe_rows}
    pred = _sample_sets(scan_id)
    methods: dict[str, dict] = {}
    for method, attack_type in _METHOD_ATTACK.items():
        actual = gt.get(attack_type, set())
        if not actual:
            methods[method] = {"status": "Not evaluated yet",
                               "reason": f"no {attack_type} manifest for this "
                                         f"dataset"}
            continue
        positives = pred[method] & universe
        tp = len(positives & actual)
        fp = len(positives - actual)
        fn = len(actual - positives)
        tn = len(universe - actual - positives)
        methods[method] = _prf(tp, fp, tn, fn)
    # overall: union over attributable methods
    all_actual = set().union(*[gt.get(a, set())
                               for a in _METHOD_ATTACK.values()])
    all_pred = set().union(*[pred[m] & universe
                             for m in _METHOD_ATTACK]) if universe else set()
    tp = len(all_pred & all_actual)
    fp = len(all_pred - all_actual)
    fn = len(all_actual - all_pred)
    tn = len(universe - all_actual - all_pred)
    methods["overall"] = _prf(tp, fp, tn, fn)
    return {"status": "evaluated", "methods": methods}


@router.get("/{scan_id}")
def get_evaluation(scan_id: str):
    return evaluate_scan(scan_id)
