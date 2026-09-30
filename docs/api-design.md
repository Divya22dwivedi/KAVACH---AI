# KavachAI — API Design (Phase 1)

Base: `http://127.0.0.1:8000` · Prefix: `/api/v1` · OpenAPI: `/docs`
All responses JSON. Errors: `{ "detail": "..." }` with proper status codes.
Every mutating call writes to `audit_log`.

## Health
- `GET /api/v1/health` → `{ status, version, db_ok, offline: true }`

## Datasets
- `POST /api/v1/datasets/upload` (multipart: format=folder|csv|yolo|coco,
  files) → `{ dataset_id, sample_count, manifest_hash }`
  - Validates: ≤50 MB total, sanitized rel paths, image magic bytes.
- `GET /api/v1/datasets` → list
- `GET /api/v1/datasets/{id}` → metadata + sample count
- `GET /api/v1/datasets/{id}/samples?flagged_only=&limit=&offset=` → samples
  with any finding flags joined
- `GET /api/v1/datasets/{id}/image/{sample_id}` → PNG bytes (for gallery)

## Data-integrity scans
- `POST /api/v1/scans` `{ dataset_id, params }` → `{ scan_id, experiment_id }`
  (runs synchronously for demo sizes; `status` polled via GET)
- `GET /api/v1/scans/{id}` → status + summary counts
- `GET /api/v1/scans/{id}/findings` → findings list

## Models
- `POST /api/v1/models/upload` (multipart: file, role=reference|candidate)
  → `{ model_id, sha256, format, metadata }`
  - `.pt/.pth`: hash + safe zip listing only. `.onnx`: protobuf metadata.
    `.pkl`: executes **only** if digest matches a KavachAI manifest.
- `GET /api/v1/models` → list
- `POST /api/v1/models/{id}/checks` `{ reference_model_id?, probe_dataset_id }`
  → runs: hash_verify, metadata, behaviour_compare, trigger_test (if
  executable + trigger params known), weight_stats (if white-box)
  → `{ checks: [...] }` each with `status: pass|flag|unavailable` + note.

## Inference + provenance
- `POST /api/v1/inference/predict` `{ model_id, image (base64|sample_id),
  config }` → `{ record_id, output, record_hash }` (appends ledger record)
- `GET /api/v1/provenance/chain?limit=` → records with prev/current hashes
- `POST /api/v1/provenance/verify` → `{ intact: bool,
  broken_at: record_id|null, expected_hash, actual_hash }`
- `POST /api/v1/provenance/tamper-demo` `{ record_id }` → modifies the
  output of a **sandboxed copy** of the record, returns before/after —
  labeled `synthetic tamper demonstration`.
- `POST /api/v1/provenance/anchor` → stores current tip hash (future:
  external anchoring; now: local anchor record)

## Distribution shift
- `POST /api/v1/shift/assess` `{ reference_dataset_id, current_dataset_id }`
  → `{ verdict: NORMAL|EXPECTED_DRIFT|SUSPICIOUS_SHIFT, metrics }`

## Findings
- `GET /api/v1/findings?category=&severity=&disposition=` → filterable table
- `PATCH /api/v1/findings/{id}` `{ disposition|reviewer_note }` → human review

## Reports
- `POST /api/v1/reports/generate` `{ experiment_id }` → `{ report_id }`
- `GET /api/v1/reports/{id}.json` → full 17-section JSON download
- `GET /api/v1/reports/{id}.pdf` → ReportLab PDF download

## Attack generator
- `POST /api/v1/attacks/generate` `{ scenario: clean|label_flip|
  trigger_patch|near_duplicate|ood|full_suite, seed, n }`
  → `{ dataset_id, attack_id, manifest }`

## Evaluation
- `GET /api/v1/evaluation/{scan_id}` → precision/recall/F1/FPR + confusion
  matrix computed against the attack manifest ground truth; or
  `{ "status": "Not evaluated yet" }`.

## One-click demo
- `POST /api/v1/demo/run` `{ seed }` → executes the 15-step demo script
  server-side, returns `{ experiment_id, steps: [{name, ok, ms}], report_id }`
  (also `scripts/run_demo.sh` for CLI).
