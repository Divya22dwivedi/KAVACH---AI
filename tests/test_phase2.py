"""Phase-2 smoke tests: DDL + health endpoint + security helpers."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app import db, security  # noqa: E402
from backend.app.main import app  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db.reset_connection()
    yield tmp_path / "t.db"
    db.reset_connection()


def test_ddl_creates_all_tables(tmp_db):
    db.init_db(tmp_db)
    con = db.get_connection(tmp_db)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {"datasets", "dataset_samples", "scans", "findings", "models",
                "model_checks", "inference_records", "shift_runs",
                "attack_manifests", "reports", "audit_log"}
    assert expected <= tables


def test_health_endpoint(tmp_db):
    db.init_db(tmp_db)
    # point the singleton at the tmp db
    db.reset_connection()
    import backend.app.db as dbmod
    dbmod.DB_PATH = tmp_db
    client = TestClient(app)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["offline"] is True
    db.reset_connection()


def test_filename_sanitization():
    assert security.sanitize_filename("../../etc/passwd") == "passwd"
    with pytest.raises(ValueError):
        security.sanitize_filename("...")
    with pytest.raises(ValueError):
        security.assert_safe_relpath("../evil.png")
    with pytest.raises(ValueError):
        security.assert_safe_relpath("/abs/path.png")
    assert security.assert_safe_relpath("a/b/c.png") == "a/b/c.png"


def test_size_limit():
    with pytest.raises(ValueError):
        security.check_size(security.MAX_UPLOAD_BYTES + 1)
    security.check_size(10)


def test_image_magic_bytes():
    assert security.is_image_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
    assert security.is_image_bytes(b"\xff\xd8\xff" + b"\x00" * 10)
    assert not security.is_image_bytes(b"MZ" + b"\x00" * 10)
