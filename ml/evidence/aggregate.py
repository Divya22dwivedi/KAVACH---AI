"""Module 5 — evidence aggregation (rule-based, per docs/ml-methodology.md).

Disposition policy (applied in order):
  1. Any ``critical`` (hash mismatch, broken provenance link) -> QUARANTINE
  2. Any ``high`` (trigger test flag, tampered record) -> QUARANTINE
  3. Any ``medium`` (representation outliers, shift=SUSPICIOUS_SHIFT,
     contributor anomaly) -> REVIEW
  4. Else if any ``low`` -> REVIEW; else ACCEPT.

The dashboard/report surface per-module status (Data / Model / Provenance /
Shift: OK / REVIEW / QUARANTINE). There is no single opaque trust score.

Why confidences are NOT averaged
--------------------------------
Each detection method defines confidence on its own scale and meaning
(per docs/ml-methodology.md: e.g. the representation-outlier confidence is
``min(0.95, percentile/100)`` while the activation-clustering-inspired
method fixes 0.55 for every flag). These numbers are not commensurable:
averaging them would pretend to be a summary statistic while silently
changing its meaning depending on which mix of detectors fired. The report
therefore lists each finding's confidence individually (confidence_notes)
and aggregates only by severity counts and rule outcomes.
"""

from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
MODULES = ("data", "model", "provenance", "shift")


def _module_status(findings: list[dict[str, Any]]) -> str:
    """Worst-finding severity in a module -> OK | REVIEW | QUARANTINE."""
    worst = max(
        (SEVERITY_ORDER[f["severity"]] for f in findings), default=SEVERITY_ORDER["info"]
    )
    if worst >= SEVERITY_ORDER["high"]:
        return "QUARANTINE"
    if worst >= SEVERITY_ORDER["low"]:
        return "REVIEW"
    return "OK"


def aggregate(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate findings into per-module status + recommended disposition.

    Args:
        findings: list of finding dicts (as produced by make_finding).
    Returns:
        dict with keys:
          - per_module: {data|model|provenance|shift: {status, counts}}
          - recommended_disposition: ACCEPT | REVIEW | QUARANTINE
          - severity_counts: {info, low, medium, high, critical}
          - rules_applied: list of human-readable ladder-rule strings
          - total_findings: int
    """
    findings = list(findings or [])

    severity_counts = {sev: 0 for sev in SEVERITY_ORDER}
    for f in findings:
        severity_counts[f["severity"]] += 1

    per_module: dict[str, dict[str, Any]] = {}
    for module in MODULES:
        module_findings = [f for f in findings if f["category"] == module]
        counts = {sev: 0 for sev in SEVERITY_ORDER}
        for f in module_findings:
            counts[f["severity"]] += 1
        per_module[module] = {
            "status": _module_status(module_findings),
            "counts": counts,
        }

    rules_applied: list[str] = []
    if severity_counts["critical"] > 0:
        rules_applied.append(
            f"Rule 1: {severity_counts['critical']} critical finding(s) present "
            "-> QUARANTINE (hash mismatch / broken provenance link severity)."
        )
        recommended = "QUARANTINE"
    elif severity_counts["high"] > 0:
        rules_applied.append(
            "Rule 1: no critical findings present; skipped."
        )
        rules_applied.append(
            f"Rule 2: {severity_counts['high']} high finding(s) present "
            "-> QUARANTINE (trigger test flag / tampered record severity)."
        )
        recommended = "QUARANTINE"
    elif severity_counts["medium"] > 0:
        rules_applied.append("Rule 1: no critical findings present; skipped.")
        rules_applied.append("Rule 2: no high findings present; skipped.")
        rules_applied.append(
            f"Rule 3: {severity_counts['medium']} medium finding(s) present "
            "-> REVIEW (representation outliers / SUSPICIOUS_SHIFT / "
            "contributor anomaly severity)."
        )
        recommended = "REVIEW"
    elif severity_counts["low"] > 0:
        rules_applied.append("Rule 1: no critical findings present; skipped.")
        rules_applied.append("Rule 2: no high findings present; skipped.")
        rules_applied.append("Rule 3: no medium findings present; skipped.")
        rules_applied.append(
            f"Rule 4: {severity_counts['low']} low finding(s) present -> REVIEW."
        )
        recommended = "REVIEW"
    else:
        rules_applied.append("Rule 1: no critical findings present; skipped.")
        rules_applied.append("Rule 2: no high findings present; skipped.")
        rules_applied.append("Rule 3: no medium findings present; skipped.")
        rules_applied.append("Rule 4: no low findings present; skipped.")
        rules_applied.append("No findings at severity low or above -> ACCEPT.")
        recommended = "ACCEPT"

    return {
        "per_module": per_module,
        "recommended_disposition": recommended,
        "severity_counts": severity_counts,
        "rules_applied": rules_applied,
        "total_findings": len(findings),
    }
