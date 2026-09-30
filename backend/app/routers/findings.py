"""Findings: filterable table + human review overrides."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ml.common.utils import canonical_json

from .. import service
from ..schemas import ReviewPatch

router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


@router.get("")
def list_findings(category: str | None = Query(None),
                  severity: str | None = Query(None),
                  disposition: str | None = Query(None)):
    """Bare JSON array of Finding objects with optional filters."""
    sql = "SELECT * FROM findings WHERE 1=1"
    args: list = []
    for col, val in (("category", category), ("severity", severity),
                     ("disposition", disposition)):
        if val is not None:
            sql += f" AND {col} = ?"
            args.append(val)
    sql += " ORDER BY created_at"
    rows = service.con().execute(sql, args).fetchall()
    return [service.finding_row_to_schema(r) for r in rows]


@router.patch("/{finding_id}")
def review_finding(finding_id: str, patch: ReviewPatch):
    """Human review: override disposition and/or add a reviewer note."""
    c = service.con()
    row = c.execute(
        "SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"finding {finding_id!r} not found")
    updates, args = [], []
    if patch.disposition is not None:
        updates.append("disposition = ?")
        args.append(patch.disposition)
    if patch.reviewer_note is not None:
        updates.append("reviewer_note = ?")
        args.append(patch.reviewer_note)
    if updates:
        c.execute(f"UPDATE findings SET {', '.join(updates)} WHERE id = ?",
                  (*args, finding_id))
        c.commit()
        service.audit("finding.review",
                      {"finding_id": finding_id,
                       "disposition": patch.disposition,
                       "reviewer_note": patch.reviewer_note})
    updated = c.execute(
        "SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    return service.finding_row_to_schema(updated)
