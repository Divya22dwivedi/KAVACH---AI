"""Distribution shift: fit reference, assess current batch."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from ml.common.features import extract_features
from ml.common.utils import canonical_json
from ml.distribution_shift.reference import (
    fit_reference,
    load_reference,
    save_reference,
)
from ml.distribution_shift.score import assess, mahalanobis_distances

from .. import service
from ..schemas import ShiftRequest

router = APIRouter(prefix="/api/v1/shift", tags=["shift"])


def _ref_path(reference_dataset_id: str):
    service.FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    return service.FEATURES_DIR / f"ref_{reference_dataset_id}.npz"


def _dataset_features(dataset_id: str, limit: int | None = None
                      ) -> tuple[np.ndarray, list[str]]:
    items = service.dataset_images(dataset_id, limit=limit)
    if not items:
        raise ValueError(f"dataset {dataset_id!r} has no readable images")
    X = np.stack([extract_features(im) for _sid, im, _lab in items])
    sids = [sid for sid, _im, _lab in items]
    return X, sids


def _fit_or_load_reference(reference_dataset_id: str) -> dict:
    path = _ref_path(reference_dataset_id)
    if path.is_file():
        return load_reference(path)
    X, _sids = _dataset_features(reference_dataset_id)
    ref = fit_reference(X, seed=7)
    save_reference(path, ref)
    return ref


@router.post("/assess")
def assess_shift(req: ShiftRequest):
    """Assess current dataset vs reference. Persists the shift run."""
    try:
        ref = _fit_or_load_reference(req.reference_dataset_id)
        X_cur, sids = _dataset_features(req.current_dataset_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    result = assess(ref, X_cur, sample_ids=sids)

    # distance histogram (20 bins) for the frontend chart
    distances = mahalanobis_distances(ref, X_cur)
    counts, edges = np.histogram(distances, bins=20)
    histogram = {"bins": [float(e) for e in edges.tolist()],
                 "counts": [int(c) for c in counts.tolist()]}

    metrics = result["metrics"]
    metrics_out = {
        "anomaly_fraction": metrics["anomaly_fraction"],
        "q95_threshold": metrics["q95_threshold"],
        "q99_threshold": metrics["q99_threshold"],
        "mean_distance": metrics["mean_distance"],
        "quality_deltas": metrics["quality_deltas"],
        "distance_histogram": histogram,
    }
    response = {
        "verdict": result["verdict"],
        "metrics": metrics_out,
        "per_sample": result["per_sample"],
        "disclaimer": result["disclaimer"],
    }
    c = service.con()
    c.execute(
        "INSERT INTO shift_runs (id, dataset_id, reference_id, verdict, "
        "metrics_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (service.new_id("shift"), req.current_dataset_id,
         req.reference_dataset_id, result["verdict"],
         canonical_json(metrics_out), service.utcnow_iso()),
    )
    c.commit()
    service.audit("shift.assess",
                  {"reference_dataset_id": req.reference_dataset_id,
                   "current_dataset_id": req.current_dataset_id,
                   "verdict": result["verdict"]})
    return response
