"""Inference: predict through an allowlisted model + provenance ledger."""

from __future__ import annotations

import io
import json

import numpy as np
from fastapi import APIRouter, HTTPException

from ml.common.features import extract_features
from ml.common.utils import canonical_json
from ml.provenance.chain import append_record

from .. import service
from ..schemas import PredictRequest

router = APIRouter(prefix="/api/v1/inference", tags=["inference"])


def _model_version(model_row: dict) -> str:
    return model_row["sha256"][:12]


@router.post("/predict")
def predict(req: PredictRequest):
    """Run inference via an allowlist-loaded model and append a ledger record.

    Returns {"record_id", "output": {"label", "probabilities"}, "record_hash"}.
    """
    try:
        model_row = service.get_model(req.model_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if int(model_row.get("manifest_ok") or 0) != 1:
        raise HTTPException(
            400, "model is not allowlisted for execution (metadata-only "
                 "record); prediction refused")
    model = service.load_model_object(model_row)
    if model is None:
        raise HTTPException(400, "model could not be loaded for execution")

    if req.image_base64:
        img = service.base64_to_image(req.image_base64)
    elif req.sample_id:
        # search every dataset for the sample id
        img = None
        for ds in service.con().execute("SELECT id FROM datasets").fetchall():
            try:
                img = service.dataset_sample_image(ds["id"], req.sample_id)
                break
            except ValueError:
                continue
        if img is None:
            raise HTTPException(404, f"sample {req.sample_id!r} not found")
    else:
        raise HTTPException(400, "provide image_base64 or sample_id")

    X = extract_features(img).reshape(1, -1)
    pred_idx = int(np.asarray(model.predict(X)).ravel()[0])
    md = json.loads(model_row["metadata_json"])
    classes = [str(c) for c in
               (md.get("classes") or md.get("registered_classes") or [])]
    label = classes[pred_idx] if 0 <= pred_idx < len(classes) else str(pred_idx)
    if hasattr(model, "predict_proba"):
        probs = [float(p) for p in
                 np.asarray(model.predict_proba(X)).ravel().tolist()]
    else:
        probs = []

    output = {"label": label, "probabilities": probs}
    input_hash = service.sha256_of_bytes(_png_bytes(img))
    model_hash = model_row["sha256"]
    config_hash = service.sha256_of_bytes(
        canonical_json(req.config or {}).encode("utf-8"))
    rec = append_record(
        service.con(), record_id=service.new_id("rec"),
        input_hash=input_hash, model_hash=model_hash,
        config_hash=config_hash, model_version=_model_version(model_row),
        output_json=output, created_at=service.utcnow_iso())
    service.audit("inference.predict",
                  {"record_id": rec["record_id"], "model_id": req.model_id,
                   "label": label})
    return {"record_id": rec["record_id"], "output": output,
            "record_hash": rec["record_hash"]}


def _png_bytes(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
