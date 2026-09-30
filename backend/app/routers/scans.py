"""Data-integrity scans: run, status, findings."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from ml.data_integrity.scan import run_scan

from .. import service
from ..schemas import ScanRequest

router = APIRouter(prefix="/api/v1/scans", tags=["scans"])


@router.post("")
def create_scan(req: ScanRequest):
    """Run a real Module 1 scan, persist findings, return scan record."""
    try:
        rows = service.dataset_rows(req.dataset_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    meta = service.new_scan(req.dataset_id, req.experiment_id, req.params)
    scan_id, experiment_id = meta["scan_id"], meta["experiment_id"]
    try:
        findings, _summary = run_scan(rows, scan_id,
                                      params=req.params or None)
        service.persist_scan_findings(scan_id, findings)
        service.finish_scan(scan_id, "done")
        status = "done"
    except Exception as exc:
        service.finish_scan(scan_id, "failed")
        raise HTTPException(500, f"scan failed: {exc}") from exc
    summary = service.scan_summary(scan_id)
    service.audit("scan.run", {"scan_id": scan_id,
                              "dataset_id": req.dataset_id,
                              "total_findings": summary["total_findings"]})
    return {"scan_id": scan_id, "experiment_id": experiment_id,
            "summary": summary, "status": status}


@router.get("/{scan_id}")
def get_scan(scan_id: str):
    try:
        sc = service.get_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"scan_id": sc["id"], "status": sc["status"],
            "summary": service.scan_summary(scan_id),
            "params": json.loads(sc["params_json"])}


@router.get("/{scan_id}/findings")
def scan_findings(scan_id: str):
    try:
        service.get_scan(scan_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    rows = service.con().execute(
        "SELECT * FROM findings WHERE scan_id = ? ORDER BY id",
        (scan_id,)).fetchall()
    return [service.finding_row_to_schema(r) for r in rows]
