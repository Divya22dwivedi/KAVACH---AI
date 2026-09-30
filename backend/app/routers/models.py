"""Models: upload/register, list, integrity checks."""

from __future__ import annotations

import json

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from ml.common.features import extract_features
from ml.common.hashing import sha256_file
from ml.model_integrity import checks as model_checks_mod
from ml.model_integrity.checks import UNAVAILABLE_NOTE, run_checks
from ml.model_integrity.registry import register_model

from .. import security, service
from ..schemas import ModelCheckRequest

router = APIRouter(prefix="/api/v1/models", tags=["models"])

UNTRUSTED_PKL_NOTE = (
    "Untrusted .pkl: no matching KavachAI manifest — metadata-only record, "
    "not executed. Review before any use."
)


def _model_shape(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "format": row["format"],
        "sha256": row["sha256"],
        "size_bytes": row["size_bytes"],
        "metadata": json.loads(row["metadata_json"]),
        "manifest_ok": row["manifest_ok"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


@router.post("/upload")
async def upload_model(file: UploadFile = File(...),
                       role: str = Form("candidate")):
    """Register a model file.

    SECURITY: a user-supplied manifest is never trusted. A ``.pkl`` is
    marked executable (``manifest_ok=1``) only when its SHA-256 matches one
    of the repo-signed KavachAI manifests
    (``models/*.pkl.manifest.json``) shipped with this prototype.
    Anything else is a metadata-only record with a limitation note and is
    never unpickled.
    """
    if role not in ("reference", "candidate"):
        raise HTTPException(400, f"invalid role: {role!r}")
    raw = await file.read()
    service.check_upload_size(len(raw))
    ext = f".{(file.filename or '').rsplit('.', 1)[-1].lower()}"
    if ext not in security.ALLOWED_MODEL_EXTS:
        raise HTTPException(
            400, f"unsupported model format {ext!r}; allowed: "
            f"{sorted(security.ALLOWED_MODEL_EXTS)}")
    name = security.sanitize_filename(file.filename or "model.bin")
    service.UPLOADED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = service.safe_upload_dir("kavach_model_")
    try:
        staged = tmp / name
        staged.write_bytes(raw)
        manifest_dest = tmp / f"{name}.manifest.json"
        if ext == ".pkl":
            # Allowlist: digest must match a repo-signed KavachAI manifest
            # shipped with this prototype. A client-supplied manifest is
            # NEVER trusted (it would let an attacker authorize their own
            # pickle for unpickling).
            digest = sha256_file(staged)
            for mpath in service.MODELS_DIR.glob("*.pkl.manifest.json"):
                try:
                    man = json.loads(mpath.read_text())
                except (OSError, ValueError):
                    continue
                if man.get("sha256") == digest:
                    manifest_dest.write_bytes(mpath.read_bytes())
                    break
        rec = register_model(staged, name, role)
        dest = service.uploaded_model_path(rec["id"], name)
        dest.write_bytes(raw)
        if manifest_dest.is_file():
            (dest.parent / f"{dest.name}.manifest.json").write_bytes(
                manifest_dest.read_bytes())
    finally:
        service.cleanup_dir(tmp)
    row = service.persist_model(rec)
    shape = _model_shape(row)
    if rec["format"] == "sklearn-pkl" and rec["manifest_ok"] == 0:
        shape["metadata"] = {**shape["metadata"],
                             "limitation": UNTRUSTED_PKL_NOTE}
    return shape


@router.get("")
def list_models():
    rows = service.con().execute(
        "SELECT * FROM models ORDER BY created_at DESC").fetchall()
    return [_model_shape(dict(r)) for r in rows]


def _probe_from_dataset(dataset_id: str, classes: list[str], limit: int = 200
                        ) -> tuple[np.ndarray, np.ndarray, list[Image.Image]]:
    """Probe features/labels/images from a dataset's stored samples."""
    items = service.dataset_images(dataset_id, limit=limit)
    if not items:
        raise ValueError(f"dataset {dataset_id!r} has no readable images")
    images = [im for _sid, im, _lab in items]
    X = np.stack([extract_features(im) for im in images])
    y = np.array([classes.index(lab) if lab in classes else -1
                  for _sid, _im, lab in items], dtype=int)
    return X, y, images


def _probe_from_npz() -> tuple[np.ndarray, np.ndarray, list[Image.Image]]:
    d = np.load(str(service.PROBE_NPZ))
    X = np.asarray(d["X"], dtype=np.float64)
    y = np.asarray(d["y"], dtype=int).ravel()
    return X, y, []  # no source images in probe.npz


@router.post("/{model_id}/checks")
def run_model_checks(model_id: str, req: ModelCheckRequest):
    """Run Module 2 checks against the reference + probe set.

    The trigger test applies the generator's known 5x5 white patch in IMAGE
    space (add_trigger) and then extracts features — never in feature space.
    """
    from attack_generator.generate import add_trigger

    try:
        model_row = service.get_model(model_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    ref_row = None
    if req.reference_model_id:
        try:
            ref_row = service.get_model(req.reference_model_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    model_rec = service.model_registry_rec(model_row)
    reference_rec = service.model_registry_rec(ref_row) if ref_row else None
    cand_obj = service.load_model_object(model_row)
    ref_obj = service.load_model_object(ref_row) if ref_row else None

    classes = (model_rec["metadata"].get("classes")
               or (reference_rec or {}).get("metadata", {}).get("classes")
               or [])
    probe_note = ""
    probe_X = probe_y = None
    probe_images: list[Image.Image] = []
    try:
        if req.probe_dataset_id:
            probe_X, probe_y, probe_images = _probe_from_dataset(
                req.probe_dataset_id, [str(c) for c in classes])
            probe_note = f"probe from dataset {req.probe_dataset_id}"
        elif service.PROBE_NPZ.is_file():
            probe_X, probe_y, probe_images = _probe_from_npz()
            probe_note = "probe from models/probe.npz"
    except ValueError as exc:
        probe_note = f"probe unavailable: {exc}"

    if probe_X is None or len(probe_X) == 0:
        results = [model_checks_mod.check_hash_verify(model_rec),
                   model_checks_mod.check_metadata(model_rec)]
        for cname in ("behaviour_compare", "trigger_test", "weight_stats",
                      "strip_inspired"):
            results.append({
                "check_name": cname, "status": "unavailable", "result": {},
                "note": probe_note or UNAVAILABLE_NOTE,
            })
    else:
        if probe_images:
            def trigger_fn(_X, _imgs=probe_images):  # image-space patch
                return np.stack([extract_features(add_trigger(im))
                                 for im in _imgs])
        else:
            trigger_fn = None  # no source images: trigger test unavailable
        results = run_checks(model_rec, reference_rec, probe_X, probe_y,
                             trigger_fn, ref_obj, cand_obj)

    c = service.con()
    for r in results:
        c.execute(
            "INSERT INTO model_checks (id, model_id, check_name, result_json, "
            "status, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (service.new_id("chk"), model_id, r["check_name"],
             json.dumps(r["result"]), r["status"], r["note"],
             service.utcnow_iso()),
        )
    c.commit()
    service.audit("model.checks", {"model_id": model_id,
                                  "reference_model_id": req.reference_model_id,
                                  "probe": probe_note,
                                  "checks": [r["check_name"]
                                             for r in results]})
    return {"model_id": model_id, "checks": results}
