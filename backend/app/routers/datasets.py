"""Datasets: upload (multipart), list, detail, samples, image serving."""

from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response

from ml.data_integrity.ingest import (
    IngestError,
    load_coco,
    load_csv,
    load_folder,
    load_yolo,
)

from .. import security, service

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])

_LOADERS = {
    "folder": lambda root: load_folder(root),
    "csv": None,   # handled specially (needs the csv file path)
    "yolo": lambda root: load_yolo(root),
    "coco": lambda root: load_coco(root),
}


def _ingest_upload(tmp: Path, fmt: str) -> tuple[list[dict], Path]:
    if fmt == "folder":
        rows, _meta = load_folder(tmp)
        return rows, tmp
    if fmt == "csv":
        csvs = sorted(tmp.glob("*.csv"))
        if not csvs:
            raise IngestError("csv format requires a .csv manifest file")
        rows, _meta = load_csv(csvs[0])
        return rows, tmp
    if fmt == "yolo":
        rows, _meta = load_yolo(tmp)
        return rows, tmp
    if fmt == "coco":
        rows, _meta = load_coco(tmp)
        return rows, tmp
    raise ValueError(f"unsupported format: {fmt!r}")


@router.post("/upload")
async def upload_dataset(
    format: str = Form(...),  # noqa: A002 - matches the API contract name
    files: list[UploadFile] = File(...),
):
    """Multipart dataset upload -> ingest -> persist.

    ``files`` may carry relative paths in their filenames (folder uploads);
    every path is traversal-checked and every file magic-byte validated.
    """
    if format not in ("folder", "csv", "yolo", "coco"):
        raise HTTPException(400, f"unsupported format: {format!r}")
    if not files:
        raise HTTPException(400, "no files provided")

    tmp = service.safe_upload_dir("kavach_ds_")
    try:
        total = 0
        names: list[str] = []
        for uf in files:
            raw = await uf.read()
            total += len(raw)
            service.check_upload_size(total)
            security.check_size(len(raw), security.MAX_IMAGE_BYTES)
            rel = security.assert_safe_relpath(uf.filename or "")
            dest = tmp / rel
            if dest.resolve().parent != tmp.resolve() and \
                    tmp.resolve() not in dest.resolve().parents:
                raise ValueError(f"path escapes upload root: {rel!r}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            names.append(rel)

        try:
            rows, root = _ingest_upload(tmp, format)
        except IngestError as exc:
            raise HTTPException(400, f"ingest failed: {exc}") from exc

        dest_dir = service.UPLOADED_DIR / service.new_id("ds")
        dest_dir.mkdir(parents=True, exist_ok=True)
        for p in root.rglob("*"):
            if p.is_file():
                rel = p.relative_to(root)
                d = dest_dir / rel
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes(p.read_bytes())

        new_rows = []
        for r in rows:
            rel = Path(r["abs_path"]).resolve().relative_to(root.resolve())
            new_rows.append({**r, "abs_path": str(dest_dir / rel)})
        ds = service.persist_dataset(
            name=f"upload_{format}_{dest_dir.name[-12:]}",
            source_format=format, root_dir=dest_dir, rows=new_rows,
            synthetic=False,
            params={"uploaded_files": names},
        )
        return {"dataset_id": ds["id"], "sample_count": ds["sample_count"],
                "manifest_hash": ds["manifest_hash"]}
    finally:
        service.cleanup_dir(tmp)


@router.get("")
def list_datasets():
    rows = service.con().execute(
        "SELECT id, name, source_format, created_at, sample_count, "
        "manifest_hash, synthetic FROM datasets ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str):
    ds = service.get_dataset(dataset_id)
    return ds


@router.get("/{dataset_id}/samples")
def dataset_samples(dataset_id: str, flagged_only: bool = False,
                    limit: int = Query(100, ge=1, le=1000),
                    offset: int = Query(0, ge=0)):
    """{"samples": [{sample_id, rel_path, label, contributor_id, sha256,
    dhash}], "total"}."""
    service.get_dataset(dataset_id)  # ValueError if missing
    c = service.con()
    total = c.execute(
        "SELECT COUNT(*) AS n FROM dataset_samples WHERE dataset_id = ?",
        (dataset_id,)).fetchone()["n"]
    flagged: set[str] = set()
    if flagged_only:
        for sc in c.execute("SELECT id FROM scans WHERE dataset_id = ?",
                            (dataset_id,)).fetchall():
            for f in c.execute(
                    "SELECT asset_id, evidence_json FROM findings "
                    "WHERE scan_id = ? AND disposition != 'ACCEPT'",
                    (sc["id"],)).fetchall():
                flagged.add(f["asset_id"])
                try:
                    ev = json.loads(f["evidence_json"] or "{}")
                except Exception:
                    ev = {}
                members = ev.get("members") if isinstance(ev, dict) else None
                if isinstance(members, list):
                    flagged.update(str(m) for m in members)
    rows = c.execute(
        "SELECT rel_path, label, contributor_id, sha256, dhash "
        "FROM dataset_samples WHERE dataset_id = ? "
        "ORDER BY rel_path LIMIT ? OFFSET ?",
        (dataset_id, limit, offset)).fetchall()
    samples = []
    for r in rows:
        sid = Path(r["rel_path"]).stem
        if flagged_only and sid not in flagged:
            continue
        samples.append({
            "sample_id": sid,
            "rel_path": r["rel_path"],
            "label": r["label"],
            "contributor_id": r["contributor_id"],
            "sha256": r["sha256"],
            "dhash": r["dhash"],
        })
    return {"samples": samples, "total": total}


@router.get("/{dataset_id}/image/{sample_id}")
def dataset_image(dataset_id: str, sample_id: str):
    img = service.dataset_sample_image(dataset_id, sample_id)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
