"""Phase-6 tests: tamper-evident cryptographic provenance ledger."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import db  # noqa: E402
from ml.provenance import chain  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path):
    db.reset_connection()
    db_path = tmp_path / "p.db"
    db.init_db(db_path)
    yield db.get_connection(db_path)
    db.reset_connection()


def _record(i, **overrides):
    rec = dict(
        record_id=f"REC-{i:04d}",
        input_hash=f"input-hash-{i}",
        model_hash="model-sha256-aaa",
        config_hash="config-sha256-bbb",
        model_version="v1.0",
        output_json={"label": "cat", "score": round(0.90 + i / 100, 4)},
        created_at=f"2026-01-01T00:00:{i:02d}+00:00",
    )
    rec.update(overrides)
    return rec


def _append_n(con, n):
    return [chain.append_record(con, **_record(i)) for i in range(1, n + 1)]


def test_append_and_verify_intact(tmp_db):
    rows = _append_n(tmp_db, 5)
    assert [r["seq"] for r in rows] == [1, 2, 3, 4, 5]
    status = chain.verify_chain(tmp_db)
    assert status["intact"] is True
    assert status["checked"] == 5
    assert status["broken_at"] is None
    assert status["tip_hash"] == rows[-1]["record_hash"]
    # every stored record_hash recomputes cleanly from stored fields
    for r in rows:
        assert chain.compute_record_hash(
            r["prev_hash"], r["input_hash"], r["model_hash"],
            r["config_hash"], r["output_hash"], r["created_at"],
            r["record_id"]) == r["record_hash"]


def test_genesis_prev_hash(tmp_db):
    rows = _append_n(tmp_db, 2)
    assert rows[0]["prev_hash"] == "GENESIS" == chain.GENESIS_HASH
    # second record links to the first record's hash
    assert rows[1]["prev_hash"] == rows[0]["record_hash"]


def test_tamper_demo_mid_chain_detected(tmp_db):
    _append_n(tmp_db, 5)
    before = chain.get_chain(tmp_db)[2]
    assert before["record_id"] == "REC-0003"
    res = chain.tamper_demo(
        tmp_db, "REC-0003", {"label": "dog", "score": 0.99})
    assert res["record_id"] == "REC-0003"
    assert res["before_output_hash"] == before["output_hash"]
    assert res["after_output_hash"] != before["output_hash"]
    assert "demo sandbox" in res["note"]

    status = chain.verify_chain(tmp_db)
    assert status["intact"] is False
    assert status["checked"] == 3
    assert status["broken_at"] == "REC-0003"
    assert status["expected_hash"] != status["actual_hash"]
    # stored row itself is left inconsistent: new output, stale hashes
    row = chain.get_chain(tmp_db)[2]
    assert row["output_json"] != before["output_json"]
    assert row["output_hash"] == before["output_hash"]
    assert row["record_hash"] == before["record_hash"]


def test_tamper_demo_twice_raises(tmp_db):
    _append_n(tmp_db, 2)
    chain.tamper_demo(tmp_db, "REC-0001", {"x": 1})
    with pytest.raises(ValueError):
        chain.tamper_demo(tmp_db, "REC-0002", {"x": 2})
    # still broken at the first tampered record
    status = chain.verify_chain(tmp_db)
    assert status["intact"] is False
    assert status["broken_at"] == "REC-0001"


def test_tamper_demo_tip_detected(tmp_db):
    _append_n(tmp_db, 5)
    chain.tamper_demo(tmp_db, "REC-0005", {"label": "hacked"})
    status = chain.verify_chain(tmp_db)
    assert status["intact"] is False
    assert status["checked"] == 5
    assert status["broken_at"] == "REC-0005"
    assert status["expected_hash"] != status["actual_hash"]


def test_reset_chain_clears(tmp_db):
    _append_n(tmp_db, 3)
    chain.reset_chain(tmp_db)
    assert chain.get_chain(tmp_db) == []
    status = chain.verify_chain(tmp_db)
    assert status["intact"] is True and status["checked"] == 0
    # demo can run again after reset
    rows = _append_n(tmp_db, 1)
    assert rows[0]["seq"] == 1
    assert rows[0]["prev_hash"] == "GENESIS"


def test_audit_entries_written(tmp_db):
    _append_n(tmp_db, 1)
    actions = {r["action"] for r in tmp_db.execute(
        "SELECT action FROM audit_log")}
    assert "provenance.record_append" in actions
