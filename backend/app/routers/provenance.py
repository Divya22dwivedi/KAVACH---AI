"""Provenance: hash-chained (tamper-evident) inference ledger.

Terminology rule: this is a "tamper-evident cryptographic provenance
ledger" — never "blockchain".
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from ml.provenance.chain import (
    GENESIS_HASH,
    get_chain,
    tamper_demo,
    verify_chain,
)

from .. import service

router = APIRouter(prefix="/api/v1/provenance", tags=["provenance"])

_TAMPER_LABEL = "synthetic tamper demonstration"


@router.get("/chain")
def read_chain(limit: int | None = Query(None, ge=1)):
    """Bare JSON array of ledger records (oldest first)."""
    return get_chain(service.con(), limit=limit)


@router.post("/verify")
def verify():
    """Recompute the ledger; returns intact/broken_at/expected/actual."""
    result = verify_chain(service.con())
    service.audit("provenance.verify",
                  {"intact": result["intact"],
                   "broken_at": result["broken_at"]})
    return result


@router.post("/tamper-demo")
def tamper(body: dict):
    """Sandboxed demo: rewrite one record's output without re-chaining.

    Labeled synthetic; verify_chain afterwards reports broken_at.
    """
    record_id = body.get("record_id")
    if not record_id:
        raise HTTPException(400, "record_id is required")
    c = service.con()
    row = c.execute(
        "SELECT output_json FROM inference_records WHERE record_id = ?",
        (record_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"record {record_id!r} not found")
    try:
        tampered = json.loads(row["output_json"])
        if isinstance(tampered, dict):
            tampered["label"] = "SYNTHETIC_TAMPER"
            tampered["synthetic_tamper_demo"] = True
        else:
            tampered = {"synthetic_tamper_demo": True,
                        "original": tampered}
    except Exception as exc:
        raise HTTPException(500, f"cannot parse stored output: {exc}"
                            ) from exc
    try:
        result = tamper_demo(c, record_id, tampered)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return result


@router.post("/anchor")
def anchor():
    """Store the current tip hash locally (external anchoring is future)."""
    tip = verify_chain(service.con())["tip_hash"] or GENESIS_HASH
    service.audit("provenance.anchor", {"tip_hash": tip})
    return {"tip_hash": tip, "anchored_at": service.utcnow_iso(),
            "note": "local anchor record; external anchoring not implemented "
                    "in this prototype"}
