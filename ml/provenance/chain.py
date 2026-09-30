"""Tamper-evident cryptographic provenance ledger (KavachAI Phase 6).

Module 3 of docs/ml-methodology.md: every inference record is linked into a
SHA-256 hash chain

    record_hash = SHA256(prev_hash ‖ input_hash ‖ model_hash ‖ config_hash ‖
                         output_hash ‖ timestamp ‖ record_id)

where ‖ is plain concatenation of the canonical UTF-8 strings
('GENESIS' is the prev_hash of the first record).

The chain is append-only by convention; the single exception is
``tamper_demo``, a labeled sandbox helper that modifies one stored row so
the test-suite/operator can confirm ``verify_chain`` detects the break.
"""

from __future__ import annotations

import json
import sqlite3

from backend.app import db
from ml.common.hashing import sha256_bytes

#: prev_hash value stored for the first record in a chain.
GENESIS_HASH = "GENESIS"

#: Audit action names written to the audit_log table.
_AUDIT_APPEND = "provenance.record_append"
_AUDIT_TAMPER_DEMO = "provenance.tamper_demo"
_AUDIT_RESET = "provenance.chain_reset"

_TAMPER_NOTE = (
    "synthetic tamper demonstration — record modified in demo sandbox"
)


def _canonical_json(payload) -> str:
    """Canonical JSON encoding (sorted keys, compact separators, UTF-8)."""
    if isinstance(payload, str):
        payload = json.loads(payload)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def compute_record_hash(prev_hash: str, input_hash: str, model_hash: str,
                        config_hash: str, output_hash: str,
                        created_at: str, record_id: str) -> str:
    """SHA-256 hex over the canonical UTF-8 concatenation of the 7 fields."""
    canonical = (prev_hash + input_hash + model_hash + config_hash
                 + output_hash + created_at + record_id)
    return sha256_bytes(canonical.encode("utf-8"))


def _row_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_chain(con: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    """All inference records in sequence order (oldest first)."""
    sql = "SELECT * FROM inference_records ORDER BY seq ASC"
    rows = con.execute(sql + " LIMIT ?" if limit is not None
                      else sql, (limit,) if limit is not None else ())
    return [_row_dict(r) for r in rows.fetchall()]


def _last_record_hash(con: sqlite3.Connection) -> str:
    row = con.execute(
        "SELECT record_hash FROM inference_records "
        "ORDER BY seq DESC LIMIT 1").fetchone()
    return row["record_hash"] if row else GENESIS_HASH


def append_record(con: sqlite3.Connection, *, record_id: str,
                  input_hash: str, model_hash: str, config_hash: str,
                  model_version: str, output_json,
                  created_at: str) -> dict:
    """Append one record to the ledger; returns the stored row as a dict.

    Computes ``output_hash`` = SHA-256 over the canonical JSON encoding of
    ``output_json`` (dict or JSON string accepted), links to the previous
    record (``GENESIS_HASH`` if first), INSERTs the row, and writes an audit
    log entry via ``db.audit``.
    """
    output_json_canon = _canonical_json(output_json)
    output_hash = sha256_bytes(output_json_canon.encode("utf-8"))
    prev_hash = _last_record_hash(con)
    record_hash = compute_record_hash(prev_hash, input_hash, model_hash,
                                      config_hash, output_hash, created_at,
                                      record_id)
    cur = con.execute(
        "INSERT INTO inference_records "
        "(record_id, input_hash, model_hash, config_hash, model_version, "
        " output_json, output_hash, created_at, prev_hash, record_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (record_id, input_hash, model_hash, config_hash, model_version,
         output_json_canon, output_hash, created_at, prev_hash,
         record_hash),
    )
    db.audit(_AUDIT_APPEND, json.dumps(
        {"record_id": record_id, "seq": cur.lastrowid,
         "record_hash": record_hash, "prev_hash": prev_hash}))
    con.commit()
    return _row_dict(con.execute(
        "SELECT * FROM inference_records WHERE seq = ?",
        (cur.lastrowid,)).fetchone())


def verify_chain(con: sqlite3.Connection) -> dict:
    """Recompute every record from genesis.

    Checks, per record in seq order:
      1. stored ``output_hash`` == SHA-256 over stored ``output_json``;
      2. stored ``prev_hash`` == previous record's ``record_hash``
         (``GENESIS_HASH`` for the first record);
      3. stored ``record_hash`` == ``compute_record_hash`` over the
         stored fields.

    Returns ``{intact, checked, broken_at, expected_hash, actual_hash,
    tip_hash}``. On the first mismatch ``broken_at`` is the failing
    record's id and ``expected_hash``/``actual_hash`` are the recomputed
    vs stored values for that check.
    """
    expected_prev = GENESIS_HASH
    checked = 0
    tip_hash = None
    for row in get_chain(con):
        checked += 1
        rid = row["record_id"]

        # 1. output integrity: stored output_hash must match output_json.
        expected_output_hash = sha256_bytes(
            row["output_json"].encode("utf-8"))
        if expected_output_hash != row["output_hash"]:
            return {"intact": False, "checked": checked, "broken_at": rid,
                    "expected_hash": expected_output_hash,
                    "actual_hash": row["output_hash"],
                    "tip_hash": None}

        # 2. chain continuity: prev_hash must equal the previous link.
        if row["prev_hash"] != expected_prev:
            return {"intact": False, "checked": checked, "broken_at": rid,
                    "expected_hash": expected_prev,
                    "actual_hash": row["prev_hash"], "tip_hash": None}

        # 3. record integrity: recompute record_hash from stored fields.
        expected_record_hash = compute_record_hash(
            row["prev_hash"], row["input_hash"], row["model_hash"],
            row["config_hash"], row["output_hash"], row["created_at"], rid)
        if expected_record_hash != row["record_hash"]:
            return {"intact": False, "checked": checked, "broken_at": rid,
                    "expected_hash": expected_record_hash,
                    "actual_hash": row["record_hash"], "tip_hash": None}

        expected_prev = row["record_hash"]
        tip_hash = row["record_hash"]

    return {"intact": True, "checked": checked, "broken_at": None,
            "expected_hash": None, "actual_hash": None,
            "tip_hash": tip_hash}


def tamper_demo(con: sqlite3.Connection, record_id: str,
                new_output_json) -> dict:
    """DEMO SANDBOX: modify a stored record's output without re-chaining.

    Only the ``output_json`` column is overwritten (canonical form of
    ``new_output_json``); ``output_hash``/``record_hash`` are left stale so
    a subsequent ``verify_chain`` reports ``broken_at == record_id``.

    Raises ``ValueError`` if the chain is already broken (the demo must run
    exactly once per chain; call ``reset_chain`` to start over).
    """
    status = verify_chain(con)
    if not status["intact"]:
        raise ValueError(
            "chain is already broken (broken_at=%r); call reset_chain() "
            "before running the tamper demo again" % status["broken_at"])

    before_output_hash = con.execute(
        "SELECT output_hash FROM inference_records WHERE record_id = ?",
        (record_id,)).fetchone()
    if before_output_hash is None:
        raise ValueError("record_id %r not found in provenance ledger"
                         % record_id)

    new_canon = _canonical_json(new_output_json)
    after_output_hash = sha256_bytes(new_canon.encode("utf-8"))
    con.execute(
        "UPDATE inference_records SET output_json = ? WHERE record_id = ?",
        (new_canon, record_id))
    db.audit(_AUDIT_TAMPER_DEMO, json.dumps(
        {"record_id": record_id,
         "before_output_hash": before_output_hash["output_hash"],
         "after_output_hash": after_output_hash,
         "note": _TAMPER_NOTE}))
    con.commit()
    return {"record_id": record_id,
            "before_output_hash": before_output_hash["output_hash"],
            "after_output_hash": after_output_hash,
            "note": _TAMPER_NOTE}


def reset_chain(con: sqlite3.Connection) -> None:
    """Delete all inference_records (demo setup helper)."""
    con.execute("DELETE FROM inference_records")
    try:
        con.execute(
            "DELETE FROM sqlite_sequence WHERE name='inference_records'")
    except sqlite3.OperationalError:
        pass  # AUTOINCREMENT bookkeeping row may not exist yet
    db.audit(_AUDIT_RESET, json.dumps({"action": "reset_chain"}))
    con.commit()
