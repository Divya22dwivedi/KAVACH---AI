"""SQLite evidence store. DDL mirrors docs/database-schema.md."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "kavach.db"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS datasets (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  source_format TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  sample_count  INTEGER NOT NULL DEFAULT 0,
  manifest_hash TEXT,
  synthetic     INTEGER NOT NULL DEFAULT 0,
  params_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS dataset_samples (
  id             TEXT PRIMARY KEY,
  dataset_id     TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  rel_path       TEXT NOT NULL,
  label          TEXT,
  contributor_id TEXT,
  sha256         TEXT NOT NULL,
  dhash          TEXT NOT NULL,
  width          INTEGER, height INTEGER,
  created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_dataset ON dataset_samples(dataset_id);
CREATE INDEX IF NOT EXISTS idx_samples_dhash   ON dataset_samples(dhash);

CREATE TABLE IF NOT EXISTS scans (
  id           TEXT PRIMARY KEY,
  dataset_id   TEXT NOT NULL REFERENCES datasets(id),
  experiment_id TEXT NOT NULL,
  started_at   TEXT NOT NULL, finished_at TEXT,
  params_json  TEXT NOT NULL,
  status       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
  id             TEXT PRIMARY KEY,
  scan_id        TEXT REFERENCES scans(id),
  category       TEXT NOT NULL,
  asset_id       TEXT NOT NULL,
  title          TEXT NOT NULL,
  detection_method TEXT NOT NULL,
  evidence_json  TEXT NOT NULL,
  confidence     REAL NOT NULL,
  severity       TEXT NOT NULL,
  disposition    TEXT NOT NULL,
  supported_attack_class TEXT,
  limitations    TEXT NOT NULL,
  reviewer_note  TEXT DEFAULT '',
  created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_scan ON findings(scan_id);
CREATE INDEX IF NOT EXISTS idx_findings_cat  ON findings(category);

CREATE TABLE IF NOT EXISTS models (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  format      TEXT NOT NULL,
  sha256      TEXT NOT NULL UNIQUE,
  size_bytes  INTEGER NOT NULL,
  metadata_json TEXT NOT NULL,
  manifest_ok INTEGER,
  role        TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_checks (
  id           TEXT PRIMARY KEY,
  model_id     TEXT NOT NULL REFERENCES models(id),
  check_name   TEXT NOT NULL,
  result_json  TEXT NOT NULL,
  status       TEXT NOT NULL,
  note         TEXT NOT NULL,
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inference_records (
  seq          INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id    TEXT NOT NULL UNIQUE,
  input_hash   TEXT NOT NULL,
  model_hash   TEXT NOT NULL,
  config_hash  TEXT NOT NULL,
  model_version TEXT NOT NULL,
  output_json  TEXT NOT NULL,
  output_hash  TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  prev_hash    TEXT NOT NULL,
  record_hash  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shift_runs (
  id           TEXT PRIMARY KEY,
  dataset_id   TEXT REFERENCES datasets(id),
  reference_id TEXT NOT NULL,
  verdict      TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attack_manifests (
  attack_id   TEXT PRIMARY KEY,
  attack_type TEXT NOT NULL,
  dataset_id  TEXT REFERENCES datasets(id),
  affected_samples_json TEXT NOT NULL,
  params_json TEXT NOT NULL,
  ground_truth_json TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
  id           TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  report_json  TEXT NOT NULL,
  pdf_path     TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT NOT NULL,
  actor      TEXT NOT NULL DEFAULT 'local-operator',
  action     TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}'
);
"""


def init_db(path: Path | None = None) -> Path:
    """Create/connect the SQLite DB and apply DDL. Returns the DB path."""
    db_path = Path(path) if path else DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(DDL)
        con.commit()
    finally:
        con.close()
    return db_path


def get_connection(path: Path | None = None) -> sqlite3.Connection:
    """Process-wide singleton connection (WAL mode; guarded by a lock)."""
    global _conn
    with _lock:
        if _conn is None:
            db_path = init_db(path)
            _conn = sqlite3.connect(str(db_path), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
        return _conn


def reset_connection() -> None:
    """Close the singleton (used by tests to switch DB files)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def audit(action: str, detail_json: str = "{}",
          actor: str = "local-operator") -> None:
    from datetime import datetime, timezone
    con = get_connection()
    with _lock:
        con.execute(
            "INSERT INTO audit_log (ts, actor, action, detail_json) "
            "VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), actor, action,
             detail_json),
        )
        con.commit()
