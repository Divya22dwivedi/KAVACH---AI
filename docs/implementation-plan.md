# KavachAI — Phase-by-Phase Implementation Plan (Phase 1)

Coordinator fans out to worker subagents per phase; each worker writes code
+ tests, RUNS them, and reports pass/fail + fixes. No phase is "done" until
its tests are green. Parent gets a report after every phase.

## Phase 1 — Research + architecture ✅ (this document set, docs/A–J)
Verify: docs complete and internally consistent.

## Phase 2 — Repository structure
Worker: create full tree, `requirements.txt`, `.gitignore`, `README.md`
skeleton, `backend/app/main.py` health endpoint, `db.py` DDL init.
Verify: `pytest tests/test_db.py` (DDL creates all 12 tables); `uvicorn`
serves `/api/v1/health`.

## Phase 3 — Backend skeleton
Worker: FastAPI app, Pydantic schemas, `security.py` (sanitize, caps,
magic bytes), `audit_log` writes, OpenAPI at `/docs`, error handlers.
Verify: TestClient hits every router stub; validation rejects `../` paths
and >50 MB uploads.

## Phase 4 — Data-integrity module (`ml/data_integrity`)
Worker: ingestor (folder/csv/yolo/coco), sha256+dhash, PCA outlier,
label stats, KMeans cluster check, patch heuristic, contributor roll-up.
Verify: pytest on synthetic fixtures — duplicate groups found, poisoned
samples flagged with measured precision/recall vs manifest.

## Phase 5 — Model-integrity module (`ml/model_integrity`)
Worker: registry (hash/metadata), safe `.pt` zip-listing, ONNX metadata,
`.pkl` allowlist execution, checks: hash_verify, behaviour_compare,
controlled trigger_test, weight_stats, STRIP-inspired consistency.
Verify: ref vs candidate measured numbers; black-box model yields
"Assessment unavailable…" notes, not fake results.

## Phase 6 — Provenance module (`ml/provenance` + router)
Worker: record creation, chain append, `verify`, tamper-demo sandbox.
Verify: intact chain verifies; tampered record → `broken_at` exact id;
unit tests for genesis + multi-record chains.

## Phase 7 — Distribution-shift module
Worker: reference stats, Mahalanobis scoring, quality signals, verdict
logic. Verify: clean batch → NORMAL; drifted batch → EXPECTED_DRIFT;
heavily shifted → SUSPICIOUS_SHIFT (all measured).

## Phase 8 — Evidence/report engine
Worker: finding schema enforcement, aggregation rules, JSON report
(17 sections), ReportLab PDF. Verify: report contains Limitations +
Unsupported-tests sections; PDF renders and is non-empty.

## Phase 9 — Frontend (React+TS+Vite, 7 pages)
Worker: typed API client, 7 pages, SVG charts, evidence drawer, chain
visualizer (green/red), report download. Verify: `npm run build` green;
every button wired to a real endpoint (no dead controls).

## Phase 10 — Integration
Worker: end-to-end wiring, CORS/proxy, error surfacing ("Not evaluated
yet" states), demo seed scripts. Verify: full UI flow against live API.

## Phase 11 — Controlled demo scenarios
Worker: `attack_generator` full suite + manifests; `train_demo_models.py`
(ref/candidate MLPs); `seed_all.py`. Verify: manifests validate; models
train < 60 s; trigger flip-rate(candidate) ≫ flip-rate(reference), measured.

## Phase 12 — Tests
Worker: full pytest suite (hashing, chain, tamper, duplicates, ingestion,
model ingest, API endpoints, report gen, attack generator, input
validation). Target: all green. Verify: `pytest -q` summary reported.

## Phase 13 — End-to-end demo run
Worker: `scripts/run_demo.sh` executes all 15 steps; capture timings
(≤ ~3 min) and the generated report. Verify: report PDF+JSON exist;
metrics in EVALUATION.md come from this run only.

## Phase 14 — Fix every error
Bug-bash across backend/frontend/tests; re-run suite + demo until green.

## Phase 15 — Final SIH demonstration prep
DEMO_SCRIPT.md (judge narrative), final verification checklist (10 items),
fresh `EVALUATION.md`, screenshots of real UI states for the deck.

## Cross-cutting rules for all workers
1. No invented numbers — measure or write "Not evaluated yet".
2. Prototype/controlled-evaluation language only.
3. Hash-chain ledger is never called "blockchain".
4. Offline: no network calls in code paths.
5. Security: validate everything from uploads; never unpickle untrusted data.
