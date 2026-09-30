# KavachAI — Database Schema (Phase 1, SQLite DDL)

```sql
PRAGMA journal_mode=WAL;

CREATE TABLE datasets (
  id            TEXT PRIMARY KEY,          -- uuid4 hex
  name          TEXT NOT NULL,
  source_format TEXT NOT NULL,             -- folder | csv | yolo | coco
  created_at    TEXT NOT NULL,             -- ISO-8601 UTC
  sample_count  INTEGER NOT NULL DEFAULT 0,
  manifest_hash TEXT,                      -- sha256 over sorted sample hashes
  synthetic     INTEGER NOT NULL DEFAULT 0,
  params_json   TEXT NOT NULL DEFAULT '{}' -- canonical generation params
);

CREATE TABLE dataset_samples (
  id             TEXT PRIMARY KEY,
  dataset_id     TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  rel_path       TEXT NOT NULL,             -- relative, sanitized; never absolute
  label          TEXT,
  contributor_id TEXT,
  sha256         TEXT NOT NULL,             -- exact bytes
  dhash          TEXT NOT NULL,             -- 64-bit hex
  width          INTEGER, height INTEGER,
  created_at     TEXT NOT NULL
);
CREATE INDEX idx_samples_dataset ON dataset_samples(dataset_id);
CREATE INDEX idx_samples_dhash   ON dataset_samples(dhash);

CREATE TABLE scans (
  id           TEXT PRIMARY KEY,
  dataset_id   TEXT NOT NULL REFERENCES datasets(id),
  experiment_id TEXT NOT NULL,             -- sha256(canonical params)
  started_at   TEXT NOT NULL, finished_at TEXT,
  params_json  TEXT NOT NULL,
  status       TEXT NOT NULL              -- running | complete | failed
);

CREATE TABLE findings (
  id             TEXT PRIMARY KEY,          -- e.g. F-0001 (per-report sequence ok)
  scan_id        TEXT REFERENCES scans(id),
  category       TEXT NOT NULL,             -- data | model | provenance | shift
  asset_id       TEXT NOT NULL,             -- sample/model/record id
  title          TEXT NOT NULL,
  detection_method TEXT NOT NULL,
  evidence_json  TEXT NOT NULL,             -- method outputs, scores, links
  confidence     REAL NOT NULL,             -- 0..1, calibrated per method doc
  severity       TEXT NOT NULL,             -- info | low | medium | high | critical
  disposition    TEXT NOT NULL,             -- ACCEPT | REVIEW | QUARANTINE
  supported_attack_class TEXT,             -- e.g. backdoor.trigger_patch
  limitations    TEXT NOT NULL,
  reviewer_note  TEXT DEFAULT '',
  created_at     TEXT NOT NULL
);
CREATE INDEX idx_findings_scan ON findings(scan_id);
CREATE INDEX idx_findings_cat  ON findings(category);

CREATE TABLE models (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  format      TEXT NOT NULL,               -- sklearn-pkl | onnx | torch-pt
  sha256      TEXT NOT NULL UNIQUE,
  size_bytes  INTEGER NOT NULL,
  metadata_json TEXT NOT NULL,             -- arch, classes, training params
  manifest_ok INTEGER,                     -- 1 if KavachAI-generated & digest matches
  role        TEXT,                        -- reference | candidate | uploaded
  created_at  TEXT NOT NULL
);

CREATE TABLE model_checks (
  id           TEXT PRIMARY KEY,
  model_id     TEXT NOT NULL REFERENCES models(id),
  check_name   TEXT NOT NULL,               -- hash_verify | behaviour_compare |
                                            -- trigger_test | weight_stats | metadata
  result_json  TEXT NOT NULL,               -- measured numbers only
  status       TEXT NOT NULL,               -- pass | flag | unavailable
  note         TEXT NOT NULL,               -- incl. "Assessment unavailable because..."
  created_at   TEXT NOT NULL
);

-- Tamper-evident provenance ledger (hash chain; append-only by convention,
-- enforced in the service layer — no UPDATE endpoint except tamper-demo sandbox)
CREATE TABLE inference_records (
  seq          INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id    TEXT NOT NULL UNIQUE,        -- nonce / record id
  input_hash   TEXT NOT NULL,
  model_hash   TEXT NOT NULL,
  config_hash  TEXT NOT NULL,
  model_version TEXT NOT NULL,
  output_json  TEXT NOT NULL,
  output_hash  TEXT NOT NULL,               -- sha256(canonical output_json)
  created_at   TEXT NOT NULL,
  prev_hash    TEXT NOT NULL,               -- 'GENESIS' for seq=1
  record_hash  TEXT NOT NULL                -- sha256(prev_hash‖input‖model‖config‖output‖ts‖record_id)
);

CREATE TABLE shift_runs (
  id           TEXT PRIMARY KEY,
  dataset_id   TEXT REFERENCES datasets(id),
  reference_id TEXT NOT NULL,               -- dataset id of reference distribution
  verdict      TEXT NOT NULL,               -- NORMAL | EXPECTED_DRIFT | SUSPICIOUS_SHIFT
  metrics_json TEXT NOT NULL,               -- distances, thresholds, quality signals
  created_at   TEXT NOT NULL
);

CREATE TABLE attack_manifests (
  attack_id   TEXT PRIMARY KEY,
  attack_type TEXT NOT NULL,                -- label_flip | trigger_patch |
                                            -- near_duplicate | ood | tampered_record
  dataset_id  TEXT REFERENCES datasets(id),
  affected_samples_json TEXT NOT NULL,
  params_json TEXT NOT NULL,                -- generation parameters (seeded)
  ground_truth_json TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE reports (
  id           TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  report_json  TEXT NOT NULL,               -- full 17-section JSON
  pdf_path     TEXT                         -- rel path under reports/
);

CREATE TABLE audit_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts         TEXT NOT NULL,
  actor      TEXT NOT NULL DEFAULT 'local-operator',
  action     TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}'
);
```
