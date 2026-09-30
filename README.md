# KavachAI — Offline AI-Assurance Workbench (Prototype)

**KavachAI** is a prototype workbench for computer-vision data/model integrity
checking, inference provenance, distribution-shift monitoring, evidence
aggregation, and JSON/PDF reporting — built as a Smart India Hackathon 2026
entry for problem statement **SIH26228** by **Team SRIJAN**.

It is a **controlled-evaluation prototype**: synthetic datasets with known
ground truth, deterministic seeds, and no deployment claim. Every claim in this
documentation is backed by measured results in [EVALUATION.md](EVALUATION.md);
anything not yet measured is explicitly marked **"Not evaluated yet."**

## What it does

Five analysis modules feed a single evidence-aggregated assurance report:

| Module | What it checks | Measured status (2026-09-30) |
|---|---|---|
| Data integrity | Trigger patches, near-duplicates, contributor skew, label shift | Trigger recall 0.20 @ precision 0.89 (full demo); near-duplicate recall 1.00 |
| Model integrity | Weight stats, behaviour agreement, backdoor-behaviour probes (STRIP-inspired) | Flip-rate flag +0.59; behaviour agreement 0.885 → flag |
| Provenance | Tamper-evident cryptographic provenance ledger over inference records | 5-record chain verifies; tamper detected at exact broken record |
| Distribution shift | Reference-vs-current feature-distribution comparison | Clean → NORMAL (0.025); brightness/OOD → SUSPICIOUS_SHIFT (1.000) |
| Evidence | Per-module findings → disposition (ACCEPT / REVIEW / QUARANTINE) | Full demo disposition: **QUARANTINE** |

Design rules: **no single opaque trust score** — each module emits its own
status plus evidence, and the reviewer sees all of it. Dispositions are
**recommendations**; human reviewers always override.

## Architecture sketch

```
                +----------------------------+
                |  React 18 + TS + Vite SPA  |  served statically at /
                |  Dashboard Data Model Prov |
                +-------------+--------------+
                              |  REST /api/v1
                +-------------v--------------+
                |  FastAPI 0.142 + SQLite     |
                |  routers/ service.py        |
                |  assurance.py (dispositions)|
                +------+---------------------+
                       |
        +--------------+---------------+------------------+
        v              v               v                  v
 ml/data_integrity  ml/model_integrity  ml/provenance  ml/distribution_shift
        \              \               \                  /
         \              \---------------+----------------/
          v                              v
     attack_generator/            ml/evidence (findings, aggregate, report)
     (synthetic, labelled)            |
                                     v
                        JSON + PDF reports (ReportLab)
```

Full detail: [ARCHITECTURE.md](ARCHITECTURE.md). Endpoints: [API.md](API.md).

## Quickstart (5 minutes)

```bash
# 1. Backend environment
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Seed demo datasets + pre-trained reference/candidate models
python scripts/seed_all.py

# 3. Start the API
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

# 4. Build and serve the frontend (or use the prebuilt dist/)
cd frontend && npm install && npm run build
# backend serves frontend/dist automatically at /

# 5. Run the full 15-step demo (seed 42, n=600): ~6.2 s, 15/15 steps OK
curl -X POST http://localhost:8000/api/v1/demo/run -H 'Content-Type: application/json' -d '{}'

# 6. Open http://localhost:8000 and walk Dashboard -> Data -> Model ->
#    Provenance -> Shift -> Findings -> Report
```

Backend is **fully offline after install** — no network calls at runtime.

## Repo map

```
backend/app/        FastAPI app (main.py, routers/, service.py, assurance.py, db.py, security.py)
ml/                 analysis libraries (data_integrity, model_integrity, provenance,
                    distribution_shift, evaluation, evidence, common)
attack_generator/   synthetic attack/corruption injector with ground-truth manifest
frontend/src/       React SPA (pages/, components/, api/, hooks/)
scripts/            seed_all.py (demo assets), train_demo_models.py, run_demo.sh
tests/              64 pytest tests
docs/               10 phase design documents
models/             pre-trained demo MLP models (scikit-learn)
reports/            generated JSON/PDF reports
```

## Docs index

- [INSTALLATION.md](INSTALLATION.md) — prerequisites, exact install steps, Docker, troubleshooting
- [ARCHITECTURE.md](ARCHITECTURE.md) — components, request flows, security model, design rationale
- [API.md](API.md) — every endpoint, methods, request/response fields
- [EVALUATION.md](EVALUATION.md) — measured results, reproduction commands, interpretation
- [REFERENCES.md](REFERENCES.md) — research and standards this prototype borrows from
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — 5-minute narrated demo, step by step
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — honest, numbered limitations
- [FUTURE_ROADMAP.md](FUTURE_ROADMAP.md) — next steps, all marked unevaluated future work

## Honesty statement

KavachAI is a **research prototype built under controlled conditions**. All
test data is synthetic with known ground truth; thresholds were tuned on that
data; no claim is made about real-world imagery, other model families, or
operational deployment. We do not claim this detects every attack, and we do
not claim the absence of findings proves absence of tampering. Numbers in this
documentation are measured and reproducible — see [EVALUATION.md](EVALUATION.md)
for how to reproduce each one.
