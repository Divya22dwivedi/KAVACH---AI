"""Reports: 17-section assurance report (JSON + PDF)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from ml.common.utils import canonical_json
from ml.evidence.pdf import render_report_pdf
from ml.evidence.report import build_report
from ml.provenance.chain import verify_chain

from .. import assurance, service
from ..routers.evaluation import evaluate_scan
from ..schemas import ReportRequest

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def generate_report(experiment_id: str) -> dict:
    """Build, persist and render the assurance report for an experiment.

    Returns {"report_id", "pdf_path"}. Unevaluated sections carry the
    literal "Not evaluated yet" (see ml.evidence.report).
    """
    c = service.con()
    scan = c.execute(
        "SELECT * FROM scans WHERE experiment_id = ? "
        "ORDER BY started_at DESC LIMIT 1", (experiment_id,)).fetchone()
    if scan is None:
        raise ValueError(f"no scan found for experiment {experiment_id!r}")
    scan_id = scan["id"]

    # cross-module synthesis (idempotent per scan) + full aggregation
    assurance.synthesize_module_findings(scan_id)
    findings = assurance.all_findings(scan_id)
    aggregation = assurance.aggregate_all(scan_id)

    ds = service.get_dataset(scan["dataset_id"])
    dataset_info = {
        "dataset_id": ds["id"], "name": ds["name"],
        "sample_count": ds["sample_count"],
        "manifest_hash": ds["manifest_hash"],
        "source_format": ds["source_format"],
        "synthetic": bool(ds["synthetic"]),
    }

    model_row = c.execute(
        "SELECT m.* FROM models m JOIN model_checks mc ON mc.model_id = m.id "
        "ORDER BY mc.created_at DESC LIMIT 1").fetchone()
    if model_row is None:
        model_row = c.execute(
            "SELECT * FROM models ORDER BY created_at DESC LIMIT 1").fetchone()
    model_info = dict(model_row) if model_row else {}
    if model_info:
        model_info["metadata"] = json.loads(model_info.pop("metadata_json"))

    shift = c.execute(
        "SELECT * FROM shift_runs ORDER BY created_at DESC LIMIT 1").fetchone()
    shift_result = ({
        "verdict": shift["verdict"],
        "metrics": json.loads(shift["metrics_json"]),
        "dataset_id": shift["dataset_id"],
        "reference_id": shift["reference_id"],
    } if shift else None)

    provenance_status = verify_chain(service.con())
    try:
        evaluation = evaluate_scan(scan_id)
    except HTTPException:
        evaluation = None

    report = build_report(
        experiment_id,
        dataset_info=dataset_info,
        model_info=model_info,
        findings=findings,
        aggregation=aggregation,
        provenance_status=provenance_status,
        shift_result=shift_result,
        evaluation=evaluation,
        limitations_extra=[
            "Trigger reconstruction (finding unknown triggers) is "
            "unsupported in this prototype; only the generator's known "
            "trigger is tested.",
            "Black-box capability is never presented as equivalent to "
            "white-box analysis.",
        ],
    )
    report_id = service.new_id("rep")
    service.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = service.REPORTS_DIR / f"{report_id}.pdf"
    render_report_pdf(report, pdf_path)
    c.execute(
        "INSERT INTO reports (id, experiment_id, created_at, report_json, "
        "pdf_path) VALUES (?, ?, ?, ?, ?)",
        (report_id, experiment_id, service.utcnow_iso(),
         canonical_json(report), str(pdf_path)),
    )
    c.commit()
    service.audit("report.generate",
                  {"report_id": report_id, "experiment_id": experiment_id,
                   "pdf_path": str(pdf_path)})
    return {"report_id": report_id, "pdf_path": str(pdf_path)}


@router.post("/generate")
def create_report(req: ReportRequest):
    try:
        result = generate_report(req.experiment_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"report_id": result["report_id"]}


@router.get("/{report_id}.json")
def download_json(report_id: str):
    row = service.con().execute(
        "SELECT report_json FROM reports WHERE id = ?",
        (report_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"report {report_id!r} not found")
    return JSONResponse(content=json.loads(row["report_json"]))


@router.get("/{report_id}.pdf")
def download_pdf(report_id: str):
    row = service.con().execute(
        "SELECT pdf_path FROM reports WHERE id = ?",
        (report_id,)).fetchone()
    if row is None or not row["pdf_path"]:
        raise HTTPException(404, f"report {report_id!r} not found")
    return FileResponse(row["pdf_path"], media_type="application/pdf",
                        filename=f"{report_id}.pdf")
