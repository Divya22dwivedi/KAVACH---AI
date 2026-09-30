"""Assurance report builder — 17 fixed sections (docs/api-design.md).

Prototype note: this report renders only measured or explicitly supplied
values. Any section with no data contains the literal string
"Not evaluated yet" — values are never invented.

There is intentionally NO single trust score: the report surfaces
per-module status (Data / Model / Provenance / Shift: OK / REVIEW /
QUARANTINE) plus the rule-based recommended disposition and the full
finding list, so a reviewer can see exactly what drove the verdict.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SECTION_KEYS = (
    "executive_summary",
    "dataset_information",
    "model_information",
    "model_hash",
    "dataset_hash",
    "findings",
    "evidence",
    "severity_summary",
    "confidence_notes",
    "provenance_verification",
    "distribution_shift",
    "supported_attack_classes",
    "unsupported_tests",
    "limitations",
    "recommended_disposition",
    "audit_trail",
    "reproducibility",
)

DEFAULT_UNSUPPORTED_TESTS = (
    "Black-box trigger reconstruction was not performed because model "
    "weights/gradients were unavailable.",
    "Trigger reconstruction for uploaded ONNX/PyTorch artifacts was not "
    "performed (metadata-only ingestion).",
)

_MODULE_LABELS = {
    "data": "Data integrity",
    "model": "Model integrity",
    "provenance": "Provenance",
    "shift": "Distribution shift",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_report(
    experiment_id: str,
    *,
    dataset_info: dict[str, Any] | None = None,
    model_info: dict[str, Any] | None = None,
    findings: list[dict[str, Any]] | None = None,
    aggregation: dict[str, Any] | None = None,
    provenance_status: dict[str, Any] | None = None,
    shift_result: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
    limitations_extra: list[str] | None = None,
) -> dict[str, Any]:
    """Build the 17-section assurance report dict.

    Every section key is always present. Sections without data contain the
    string "Not evaluated yet" instead of invented content.
    """
    findings = list(findings or [])
    dataset_info = dict(dataset_info or {})
    model_info = dict(model_info or {})
    limitations_extra = list(limitations_extra or [])

    # -- executive summary ------------------------------------------------
    if aggregation:
        per_module = aggregation.get("per_module", {})
        module_lines = "; ".join(
            f"{_MODULE_LABELS.get(m, m)}: {info.get('status', 'Not evaluated yet')}"
            for m, info in per_module.items()
        )
        disposition = aggregation.get("recommended_disposition", "Not evaluated yet")
        n = aggregation.get("total_findings", len(findings))
        executive_summary = (
            f"Prototype assurance report for experiment '{experiment_id}'. "
            f"{n} finding(s) recorded. Per-module status — {module_lines}. "
            f"Rule-based recommended disposition: {disposition}. "
            "This prototype does not compute a single trust score; review "
            "the per-module statuses and findings below."
        )
    else:
        executive_summary = "Not evaluated yet"

    # -- dataset / model --------------------------------------------------
    dataset_information: Any = dataset_info if dataset_info else "Not evaluated yet"
    model_information: Any = model_info if model_info else "Not evaluated yet"

    model_hash: Any = model_info.get("sha256") or model_info.get("hash") or "Not evaluated yet"
    dataset_hash: Any = (
        dataset_info.get("manifest_hash") or dataset_info.get("sha256") or "Not evaluated yet"
    )

    # -- findings / evidence ----------------------------------------------
    findings_section: Any = findings if findings else "Not evaluated yet"
    if findings:
        evidence_section: Any = [
            {
                "finding_id": f["id"],
                "detection_method": f["detection_method"],
                "evidence": f.get("evidence", {}),
            }
            for f in findings
        ]
    else:
        evidence_section = "Not evaluated yet"

    # -- severity summary --------------------------------------------------
    if aggregation:
        severity_summary: Any = {
            "severity_counts": dict(aggregation.get("severity_counts", {})),
            "total_findings": aggregation.get("total_findings", len(findings)),
            "rules_applied": list(aggregation.get("rules_applied", [])),
        }
    else:
        severity_summary = "Not evaluated yet"

    # -- confidence notes ---------------------------------------------------
    if findings:
        confidence_notes = (
            "Confidence values below are per-method definitions "
            "(see docs/ml-methodology.md) and are NOT averaged across "
            "findings, because confidences from different detection methods "
            "are not commensurable. "
            + " ".join(
                f"{f['id']} ({f['detection_method']}): {f['confidence']:.2f}."
                for f in findings
            )
        )
    else:
        confidence_notes = "Not evaluated yet"

    # -- provenance / shift / evaluation -----------------------------------
    provenance_verification: Any = (
        provenance_status
        if provenance_status
        else "Not evaluated yet"
    )
    distribution_shift: Any = shift_result if shift_result else "Not evaluated yet"

    # -- supported / unsupported tests --------------------------------------
    supported = sorted(
        {f.get("supported_attack_class") for f in findings if f.get("supported_attack_class")}
    )
    supported_attack_classes: Any = supported if supported else "Not evaluated yet"
    unsupported_tests: list[str] = list(DEFAULT_UNSUPPORTED_TESTS)

    # -- limitations ---------------------------------------------------------
    collected: list[str] = []
    seen: set[str] = set()
    for f in findings:
        lim = f.get("limitations")
        if isinstance(lim, str) and lim and lim not in seen:
            seen.add(lim)
            collected.append(f"[{f['id']}] {lim}")
    for lim in limitations_extra:
        if lim and lim not in seen:
            seen.add(lim)
            collected.append(lim)
    collected.append(
        "Prototype limitation: detection coverage is limited to the detectors "
        "implemented in this prototype; absence of findings is not proof of "
        "absence of compromise."
    )
    limitations = collected

    # -- disposition ----------------------------------------------------------
    recommended_disposition: Any = (
        aggregation.get("recommended_disposition", "Not evaluated yet")
        if aggregation
        else "Not evaluated yet"
    )

    # -- audit trail -----------------------------------------------------------
    audit_trail = {
        "experiment_id": experiment_id,
        "report_generated_at": _utc_now_iso(),
        "generator": "KavachAI prototype report engine (Phase 8)",
        "finding_ids": [f["id"] for f in findings] if findings else [],
        "note": (
            "Prototype: only report-generation events are recorded here; "
            "full API audit events live in the backend audit_log table."
        ),
    }

    # -- reproducibility --------------------------------------------------------
    if evaluation:
        reproducibility = {
            "evaluation": evaluation,
            "note": (
                "Detector metrics (precision/recall/F1/FPR, confusion matrix) "
                "are computed only when an attack manifest with ground truth "
                "exists for the scanned dataset."
            ),
        }
    else:
        reproducibility = (
            "Not evaluated yet — evaluation metrics are computed only when an "
            "attack manifest with ground truth exists for the scanned dataset."
        )

    report = {
        "experiment_id": experiment_id,
        "executive_summary": executive_summary,
        "dataset_information": dataset_information,
        "model_information": model_information,
        "model_hash": model_hash,
        "dataset_hash": dataset_hash,
        "findings": findings_section,
        "evidence": evidence_section,
        "severity_summary": severity_summary,
        "confidence_notes": confidence_notes,
        "provenance_verification": provenance_verification,
        "distribution_shift": distribution_shift,
        "supported_attack_classes": supported_attack_classes,
        "unsupported_tests": unsupported_tests,
        "limitations": limitations,
        "recommended_disposition": recommended_disposition,
        "audit_trail": audit_trail,
        "reproducibility": reproducibility,
    }

    assert tuple(report.keys()) == (
        "experiment_id",
        *SECTION_KEYS,
    ), f"report sections mismatch: {sorted(report.keys())}"
    return report
