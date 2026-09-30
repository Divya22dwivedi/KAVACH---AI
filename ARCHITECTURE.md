# Architecture

## Component diagram

```
                                  +-------------------+
                                  |   React 18 SPA    |
                                  | pages: Dashboard, |
                                  | Data, Model, Prov |
                                  | enance, Shift,    |
                                  | Findings, Report  |
                                  +---------+---------+
                                            |  REST JSON  /api/v1/*
                    +-----------------------v-----------------------+
                    |  FastAPI 0.142  (backend/app/)                |
                    |  main.py: app, CORS, SPA + asset serving      |
                    |  routers/ : datasets, scans, models,         |
                    |    inference, provenance, shift, findings,    |
                    |    reports, attacks, evaluation, demo         |
                    |  service.py : orchestration                  |
                    |  assurance.py : disposition policy           |
                    |  db.py : SQLite access layer                 |
                    |  security.py : input validation guards       |
                    +--------+----------------------------+--------+
                             |                            |
                             v                            v
                    +-----------------+        +------------------+
                    |  SQLite         |        |  File store      |
                    |  11 tables      |        |  models/ reports/|
                    |  (see below)    |        |  uploads (tmp)   |
                    +-----------------+        +------------------+

  Analysis libraries (ml/) — no framework lock-in:
  +----------------+ +----------------+ +---------------+ +--------------------+
  | data_integrity | | model_integrity| | provenance    | | distribution_shift |
  | ingest, scan   | | registry,      | | chain (hash-  | | reference, score,  |
  |                | | checks         | | linked ledger)| | disclaimer         |
  +----------------+ +----------------+ +---------------+ +--------------------+
        +              +                +                  +
        |              |                |                  |
        v              v                v                  v
  attack_generator/ (synthetic, labelled)     ml/evaluation (ground-truth scoring)
                       +---------------------------+
                       | ml/evidence               |
                       | findings, aggregate,      |
                       | report -> JSON + PDF      |
                       +---------------------------+
```

## Request flows

### Scan a dataset — `POST /api/v1/scans`

1. Router validates payload (security.py: path traversal guards, size limits).
2. `service.py` loads samples from `dataset_samples` (SQLite).
3. `ml/data_integrity/scan.py` runs: trigger-patch heuristic (outlier pixel
   patterns), near-duplicate hashing, contributor statistics, label chi-square.
4. Findings written to `findings` table with `detection_method` and `evidence`
   JSON; disposition proposed by `assurance.py`.
5. Response returns `scan_id`, per-finding ids, and the disposition.

### Model check — `POST /api/v1/models/{model_id}/checks`

1. Model file is loaded via `ml/common/model_io.py` — `.pt`/`.pth` are
   **never unpickled**; foreign or tampered pickles are refused outright.
2. `ml/model_integrity/checks.py` runs weight statistics, behaviour agreement
   vs a reference model, trigger flip-rate probe, STRIP-inspired entropy probe.
3. Each check emits `{check_name, status, result, note}`; ONNX/`.pt` produce
   metadata/hash-only entries with honest "unavailable" statuses.

### Provenance — `POST /api/v1/provenance/anchor`, `GET /api/v1/provenance/chain`

1. Each inference record is hashed (SHA-256 of canonical JSON) and appended
   with `record_hash` and `prev_hash`, forming a hash-linked chain
   (Merkle-style tamper-evidence; **not** a blockchain).
2. `GET /chain` recomputes every link. A single altered record breaks its hash
   and every subsequent `prev_hash`; the API reports the **exact broken record
   id**. Repeated tamper attempts are refused.
3. `POST /tamper-demo` runs the controlled tamper demonstration end to end.

### Distribution shift — `POST /api/v1/shift/assess`

1. `reference.py` builds the reference distribution from a clean dataset
   (feature means, covariances, anomaly fraction baselines).
2. `score.py` scores the current batch; verdicts: `NORMAL`, `EXPECTED_DRIFT`,
   `SUSPICIOUS_SHIFT`.
3. `disclaimer.py` attaches the shift disclaimer to every response and report.

### Report — `POST /api/v1/reports/generate`, `GET /api/v1/reports/{report_id}.pdf`

1. `ml/evidence/aggregate.py` collects all module findings for a scan.
2. `ml/evidence/report.py` renders the JSON report and the ReportLab PDF.
3. Every report restates per-module status + evidence and the human-override
   note — dispositions never hide behind a single number.

## SQLite tables (backend/app/db.py)

`datasets`, `dataset_samples`, `attack_manifests`, `scans`, `findings`,
`models`, `model_checks`, `inference_records`, `shift_runs`, `reports`,
`audit_log`.

## Security model

- Uploaded files: magic-byte checks, extension allow-lists, size caps; uploads
  are never executed and never deserialised with pickle/`torch.load`.
- Path traversal: all dataset/model ids are validated against a safe charset;
  file paths are resolved inside fixed directories.
- The provenance chain detects post-hoc record tampering; it does not prevent a
  privileged attacker with database write access from rewriting history — the
  audit log exists to make such rewriting visible, not impossible.
- No secrets in the repo; no outbound network at runtime.

## Why scikit-learn, not PyTorch

The evaluation environment is a 2-CPU VM. The demo models are small MLPs for
tabular/image-feature inputs, and scikit-learn trains them in ~1 minute where a
torch stack would add weight without changing what is being demonstrated:
integrity checks around the model, not the model itself. The architecture is
modular — `ml/model_integrity/checks.py` is the seam where other model formats
would plug in.
