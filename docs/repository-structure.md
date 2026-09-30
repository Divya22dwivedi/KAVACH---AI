# KavachAI — Repository Structure (Phase 1)

```
kavach-ai/
├── README.md                 # product overview, quickstart
├── INSTALLATION.md           # offline install guide
├── ARCHITECTURE.md           # system architecture (from docs/architecture.md)
├── API.md                    # API documentation (from docs/api-design.md)
├── EVALUATION.md             # measured metrics only (filled after demo runs)
├── REFERENCES.md             # research references (from docs/research-findings.md)
├── DEMO_SCRIPT.md            # judge-facing demo script
├── KNOWN_LIMITATIONS.md      # bounded scopes, unsupported tests
├── FUTURE_ROADMAP.md         # post-prototype directions
├── requirements.txt          # backend deps (pip)
├── .venv/                    # local virtualenv (not committed)
│
├── docs/                     # Phase-1 design docs (A–J)
│   ├── research-findings.md
│   ├── requirements-mapping.md
│   ├── architecture.md
│   ├── technology-choices.md
│   ├── database-schema.md
│   ├── api-design.md
│   ├── ml-methodology.md
│   ├── demo-scenario.md
│   ├── repository-structure.md
│   └── implementation-plan.md
│
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, router wiring
│   │   ├── db.py             # sqlite connection, DDL init
│   │   ├── schemas.py        # Pydantic models
│   │   ├── security.py       # filename sanitize, size caps, magic bytes
│   │   ├── routers/          # datasets, scans, models, inference,
│   │   │                     # provenance, shift, findings, reports, demo, attacks
│   │   └── services/         # orchestration (calls ml/*, writes evidence)
│   └── tests/                # (also top-level tests/ for ml unit tests)
│
├── ml/                       # pure-python ML core (no FastAPI imports)
│   ├── common/               # hashing, features, pca, io, rng
│   ├── data_integrity/       # ingest, dhash, outliers, labels, contributors
│   ├── model_integrity/      # registry, checks, trigger test
│   ├── provenance/           # chain build/verify
│   ├── distribution_shift/   # reference stats, scoring
│   └── evaluation/           # prf vs ground truth
│
├── attack_generator/         # synthetic data + attack manifests
│   ├── generate.py
│   └── manifests.py
│
├── frontend/                 # React + TS + Vite
│   ├── src/pages/            # Dashboard, DataIntegrity, ModelIntegrity,
│   │                         # Provenance, DistributionShift, Findings, Report
│   ├── src/components/       # charts (SVG), tables, evidence panel
│   └── src/api/              # typed API client
│
├── datasets/                 # generated demo datasets (git-ignored if large)
├── models/                   # reference + candidate demo models + manifests
├── reports/                  # generated JSON/PDF reports
├── scripts/
│   ├── run_demo.sh           # one-click CLI demo
│   ├── train_demo_models.py  # builds ref/candidate models
│   └── seed_all.py           # clean + poisoned datasets
├── tests/                    # pytest: hashing, chain, tamper, dupes,
│                             # ingestion, api, reports, generator, validation
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```
