"""Finding factory: validated finding dicts for the KavachAI evidence pipeline.

A finding is the atomic unit of evidence. Every required key is validated
at construction time so that downstream aggregation and reporting can never
render an incomplete or malformed record.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

SEVERITIES = ("info", "low", "medium", "high", "critical")
CATEGORIES = ("data", "model", "provenance", "shift")
DISPOSITIONS = ("ACCEPT", "REVIEW", "QUARANTINE")

_ID_PATTERN = re.compile(r"^F-\d{4}$")

REQUIRED_KEYS = (
    "id",
    "category",
    "asset_id",
    "title",
    "detection_method",
    "evidence",
    "confidence",
    "severity",
    "disposition",
    "supported_attack_class",
    "limitations",
    "created_at",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_finding(
    finding_id: str,
    category: str,
    asset_id: str,
    title: str,
    detection_method: str,
    evidence: dict,
    confidence: float,
    severity: str,
    disposition: str,
    supported_attack_class: str | None,
    limitations: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a validated finding dict.

    Raises ValueError on any missing/invalid key. Never fabricates values:
    every argument must be supplied by the caller.
    """
    if not isinstance(finding_id, str) or not _ID_PATTERN.match(finding_id):
        raise ValueError(
            f"finding id must match 'F-NNNN' (e.g. F-0001), got {finding_id!r}"
        )
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {CATEGORIES}, got {category!r}")
    if not asset_id or not isinstance(asset_id, str):
        raise ValueError("asset_id must be a non-empty string")
    if not title or not isinstance(title, str):
        raise ValueError("title must be a non-empty string")
    if not detection_method or not isinstance(detection_method, str):
        raise ValueError("detection_method must be a non-empty string")
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be a dict")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("confidence must be a number")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError(f"confidence must be in [0, 1], got {confidence!r}")
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}, got {severity!r}")
    if disposition not in DISPOSITIONS:
        raise ValueError(
            f"disposition must be one of {DISPOSITIONS}, got {disposition!r}"
        )
    if supported_attack_class is not None and (
        not isinstance(supported_attack_class, str) or not supported_attack_class
    ):
        raise ValueError(
            "supported_attack_class must be a non-empty string or None"
        )
    if not limitations or not isinstance(limitations, str):
        raise ValueError("limitations must be a non-empty string")
    if created_at is None:
        created_at = _utc_now_iso()
    elif not isinstance(created_at, str) or not created_at:
        raise ValueError("created_at must be a non-empty ISO string")

    finding: dict[str, Any] = {
        "id": finding_id,
        "category": category,
        "asset_id": asset_id,
        "title": title,
        "detection_method": detection_method,
        "evidence": dict(evidence),
        "confidence": confidence,
        "severity": severity,
        "disposition": disposition,
        "supported_attack_class": supported_attack_class,
        "limitations": limitations,
        "created_at": created_at,
    }
    missing = [k for k in REQUIRED_KEYS if k not in finding]
    if missing:  # defensive; constructor sets all keys above
        raise ValueError(f"finding is missing required keys: {missing}")
    return finding


def next_id(existing: Iterable[str]) -> str:
    """Return the next finding id (F-NNNN) after the largest existing one."""
    highest = 0
    for item in existing:
        if isinstance(item, str) and _ID_PATTERN.match(item):
            highest = max(highest, int(item[2:]))
    return f"F-{highest + 1:04d}"
