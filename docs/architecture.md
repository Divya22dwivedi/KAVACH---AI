# KavachAI — Final Architecture (Phase 1)

## System overview (offline-first)

```
┌────────────────────────────────────────────────────────────────┐
│  FRONTEND  (React + TypeScript + Vite) — 7 pages                │
│  Dashboard · Data · Model · Provenance · Shift · Findings · Report│
│  Talks ONLY to http://127.0.0.1:8000 (FastAPI). No other I/O.   │
└───────────────────────────────┬────────────────────────────────┘
                                │  REST / JSON  (OpenAPI at /docs)
┌───────────────────────────────▼────────────────────────────────┐
│  BACKEND  (Python + FastAPI)  `backend/app/`                    │
│  routers/: datasets, models, scans, inference, provenance,      │
│            shift, findings, reports, demo, health               │
│  services/: orchestration — calls into ml/ packages, writes    │
│             evidence objects, persists to SQLite                │
│  Security: filename sanitization, path-traversal guard,         │
│            50 MB upload cap, magic-byte image check,            │
│            safe temp files, audit log of API actions            │
└───────────────┬───────────────────────────────┬────────────────┘
                │                               │
┌───────────────▼───────────────┐   ┌───────────▼────────────────┐
│  ML CORE  `ml/` (pure python) │   │  SQLite `kavach.db`        │
│  data_integrity/  ingestion,  │   │  datasets, samples, scans, │
│    dhash, pca-outlier,        │   │  findings, evidence,       │
│    label-stats, contributors  │   │  models, model_checks,     │
│  model_integrity/  registry,  │   │  inference_records (hash   │
│    hash, behaviour-compare,   │   │   chain), shift_runs,       │
│    trigger-test, weight-stats │   │  reports, attack_manifests │
│  provenance/  hash chain,      │   │  audit_log                 │
│    verify, tamper-demo         │   └────────────────────────────┘
│  distribution_shift/  ref     │
│    stats, mahalanobis,        │
│    quality signals            │
│  evaluation/  prf vs ground   │
│    truth, confusion matrix    │
└───────────────┬───────────────┘
                │
┌───────────────▼───────────────┐
│  attack_generator/            │
│  seeded synthetic data +      │
│  attack manifests (ground     │
│  truth). Used by tests AND   │
│  the one-click demo.          │
└───────────────────────────────┘

Reports: backend renders JSON directly; PDF via ReportLab (local).
```

## Data flow — the assurance pipeline

```
DATA (dataset ingest)
  │  hashes: sha256 per sample, dhash per image, manifest hash
  ▼
DATA INTEGRITY SCAN ──► findings (sample-level evidence)
  │  contributor aggregation ──► contributor risk roll-up
  ▼
MODEL (model ingest → registry: sha256 digest + metadata)
  ▼
MODEL INTEGRITY CHECK ──► findings (hash, behaviour vs reference,
  │                         controlled trigger test, weight stats)
  ▼
INFERENCE (predict via registered model)
  │  each call → provenance record (hash chain append)
  ▼
PROVENANCE VERIFICATION ──► chain status INTACT/BROKEN (+ failing link)
  ▼
DISTRIBUTION SHIFT ──► NORMAL / EXPECTED_DRIFT / SUSPICIOUS_SHIFT
  ▼
EVIDENCE AGGREGATION ──► assurance summary + disposition
  │  (rule-based; logic documented in ml-methodology.md;
  │   NO single opaque trust score)
  ▼
HUMAN REVIEW (analyst confirms/overrides disposition per finding)
  ▼
ASSURANCE REPORT (JSON + PDF, 17 sections incl. "not tested")
```

## Key design decisions

1. **Backend owns orchestration; `ml/` is pure logic.** Every ML function is
   importable and unit-testable without FastAPI. Routers are thin.
2. **SQLite as evidence store.** Single-file, offline, zero-config; the
   provenance chain lives in `inference_records`. Append-only enforced at
   the service layer (no UPDATE path except the *sandboxed* tamper demo,
   which is explicitly labeled).
3. **Frontend never computes.** All numbers come from API responses produced
   by real runs. Unevaluated modules render "Not evaluated yet".
4. **Determinism.** Seeded RNG everywhere; `experiment_id =
   sha256(canonical_json(params))`. Same inputs → same report.
5. **Security boundaries.**
   - Uploads: sanitized names, no `..`, size cap, image magic bytes.
   - `.pt/.pth` are *never unpickled* (zip-listing only).
   - `.pkl` models execute only if their digest matches a KavachAI-generated
     manifest; otherwise metadata-only with an explicit limitation note.
   - ONNX parsed as protobuf (no code execution).
6. **Demo model choice.** scikit-learn `MLPClassifier` trained on synthetic
   geometric-shape images (numpy/Pillow generated). Reference (clean) and
   candidate (trigger-poisoned) variants give *measured* clean-accuracy and
   trigger-flip-rate numbers. No torch: keeps the 2 GB demo box and the
   offline installer light; ingestion still accepts `.pt`/`.onnx` for
   hash+metadata.
7. **Honesty rails.** Finding schema has mandatory `limitations` and
   `supported_attack_class`; report has mandatory "Unsupported tests".
   Black-box-only models get: "Assessment unavailable because required
   model access is not available."

## Deployment (demo)

```
docker/           Dockerfile (python:3.12-slim, venv, uvicorn)
                  docker-compose.yml (api + static frontend via nginx)
scripts/run_demo.sh   one-click: seed data → scans → models →
                      inference → tamper → verify → shift →
                      aggregate → report (also exposed as UI button
                      POST /api/v1/demo/run)
```

Frontend dev: `npm run dev` (Vite) proxies `/api` → `127.0.0.1:8000`.
Production demo build: `npm run build` → served statically; still
same-origin API. No external requests at runtime, ever.
