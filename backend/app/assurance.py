"""Cross-module evidence synthesis for aggregation and reports.

Builds honest finding records (via ml.evidence.findings.make_finding) from
measured Module 2 checks, Module 4 shift verdicts and Module 3 provenance
verification — then aggregates everything with the documented ladder rule.
Nothing is fabricated: only measured flag statuses become findings.
"""

from __future__ import annotations

import json

from ml.evidence.aggregate import aggregate
from ml.evidence.findings import make_finding
from ml.provenance.chain import verify_chain

from . import service

# check_name -> severity for flagged checks (per docs ladder semantics:
# trigger-test flag and tampered records are high; hash mismatch critical)
_CHECK_SEVERITY = {
    "hash_verify": "critical",
    "trigger_test": "high",
    "behaviour_compare": "medium",
    "weight_stats": "medium",
    "strip_inspired": "medium",
    "metadata": "medium",
}


def _existing_synthesis(scan_id: str) -> bool:
    row = service.con().execute(
        "SELECT COUNT(*) AS n FROM findings WHERE scan_id = ? "
        "AND category IN ('model', 'provenance', 'shift')",
        (scan_id,)).fetchone()
    return int(row["n"]) > 0


def _next_ids(n: int) -> list[str]:
    c = service.con()
    mx = c.execute(
        "SELECT MAX(CAST(SUBSTR(id, 3) AS INTEGER)) AS m FROM findings "
        "WHERE id GLOB 'F-[0-9]*'").fetchone()["m"]
    start = int(mx or 0) + 1
    return [f"F-{start + i:04d}" for i in range(n)]


def _persist(recs: list[dict], scan_id: str | None) -> list[dict]:
    c = service.con()
    out = []
    for rec in recs:
        c.execute(
            "INSERT INTO findings (id, scan_id, category, asset_id, title, "
            "detection_method, evidence_json, confidence, severity, "
            "disposition, supported_attack_class, limitations, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rec["id"], scan_id, rec["category"], rec["asset_id"],
             rec["title"], rec["detection_method"],
             json.dumps(rec["evidence"]), rec["confidence"], rec["severity"],
             rec["disposition"], rec["supported_attack_class"],
             rec["limitations"], rec["created_at"]),
        )
        out.append(rec)
    c.commit()
    return out


def synthesize_module_findings(scan_id: str | None) -> list[dict]:
    """Create + persist model/provenance/shift findings from measured state.

    Idempotent per scan_id: returns [] if synthesis already ran.
    """
    if scan_id and _existing_synthesis(scan_id):
        return []
    recs: list[dict] = []

    # -- Module 2: flagged model checks (latest per model per check) ------
    c = service.con()
    seen: set[tuple[str, str]] = set()
    for chk in c.execute(
            "SELECT mc.*, m.name AS model_name FROM model_checks mc "
            "JOIN models m ON m.id = mc.model_id "
            "ORDER BY mc.created_at DESC").fetchall():
        key = (chk["model_id"], chk["check_name"])
        if key in seen:
            continue
        seen.add(key)
        if chk["status"] != "flag":
            continue
        result = json.loads(chk["result_json"] or "{}")
        recs.append({
            "category": "model",
            "asset_id": chk["model_id"],
            "title": (f"Model integrity check flagged: {chk['check_name']} "
                      f"on model {chk['model_name']}"),
            "detection_method": chk["check_name"],
            "evidence": {"check_result": result,
                         "model_id": chk["model_id"]},
            "confidence": 0.80,
            "severity": _CHECK_SEVERITY.get(chk["check_name"], "medium"),
            "disposition": ("QUARANTINE"
                            if chk["check_name"] in ("hash_verify",
                                                     "trigger_test")
                            else "REVIEW"),
            "supported_attack_class": ("backdoor.trigger_patch"
                                       if chk["check_name"] == "trigger_test"
                                       else None),
            "limitations": chk["note"],
        })

    # -- Module 3: provenance verification --------------------------------
    prov = verify_chain(service.con())
    if not prov["intact"]:
        recs.append({
            "category": "provenance",
            "asset_id": prov["broken_at"] or "ledger",
            "title": ("Provenance ledger integrity failure: chain broken at "
                      f"{prov['broken_at']}"),
            "detection_method": "ledger_hash_verify",
            "evidence": {"broken_at": prov["broken_at"],
                         "expected_hash": prov["expected_hash"],
                         "actual_hash": prov["actual_hash"],
                         "checked": prov["checked"]},
            "confidence": 1.0,
            "severity": "critical",
            "disposition": "QUARANTINE",
            "supported_attack_class": "provenance.tampering",
            "limitations": ("Hash-chain verification is deterministic for "
                            "the stored records; it cannot prove *when* the "
                            "tamper occurred."),
        })

    # -- Module 4: latest shift verdict ------------------------------------
    shift = c.execute(
        "SELECT * FROM shift_runs ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if shift is not None and shift["verdict"] in ("SUSPICIOUS_SHIFT",
                                                 "EXPECTED_DRIFT"):
        metrics = json.loads(shift["metrics_json"])
        recs.append({
            "category": "shift",
            "asset_id": shift["dataset_id"],
            "title": (f"Distribution shift verdict {shift['verdict']} on "
                      f"dataset {shift['dataset_id']}"),
            "detection_method": "mahalanobis_shift",
            "evidence": {"verdict": shift["verdict"], "metrics": metrics,
                         "reference_dataset_id": shift["reference_id"]},
            "confidence": 0.75,
            "severity": ("medium" if shift["verdict"] == "SUSPICIOUS_SHIFT"
                         else "low"),
            "disposition": "REVIEW",
            "supported_attack_class": None,
            "limitations": ("Shift is a statistical signal, not proof of "
                            "malice; benign causes (new camera, season) are "
                            "common."),
        })

    if not recs:
        return []
    ids = _next_ids(len(recs))
    built = [make_finding(
        finding_id=fid,
        category=r["category"],
        asset_id=r["asset_id"],
        title=r["title"],
        detection_method=r["detection_method"],
        evidence=r["evidence"],
        confidence=r["confidence"],
        severity=r["severity"],
        disposition=r["disposition"],
        supported_attack_class=r["supported_attack_class"],
        limitations=r["limitations"],
    ) for fid, r in zip(ids, recs)]
    service.audit("assurance.synthesize",
                  {"scan_id": scan_id, "synthesized": len(built)})
    return _persist(built, scan_id)


def all_findings(scan_id: str) -> list[dict]:
    rows = service.con().execute(
        "SELECT * FROM findings WHERE scan_id = ? ORDER BY id",
        (scan_id,)).fetchall()
    return [service.finding_row_to_schema(r) for r in rows]


def aggregate_all(scan_id: str) -> dict:
    """Aggregate every finding for the scan with the ladder rule."""
    findings = all_findings(scan_id)
    agg_input = [{
        "id": f["id"], "category": f["category"], "severity": f["severity"],
        "disposition": f["disposition"], "confidence": f["confidence"],
        "detection_method": f["detection_method"],
    } for f in findings]
    return aggregate(agg_input)
