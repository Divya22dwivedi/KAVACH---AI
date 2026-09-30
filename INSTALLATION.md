# Installation

KavachAI runs entirely offline after dependencies are installed. Tested on a
2-CPU Linux VM; Python 3.12 backend, Node 24 frontend.

## Prerequisites

| Component | Version |
|---|---|
| Python | 3.12 |
| Node.js | 24 |
| npm | bundled with Node 24 |
| OS | Linux (Windows/macOS untested) |
| RAM | 4 GB minimum for build; runtime fits in ~1 GB |

No GPU required — demo models are scikit-learn MLPs precisely so the prototype
runs on modest hardware.

## Step-by-step

```bash
# 1. Backend virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Backend dependencies (pinned in requirements.txt)
pip install -r requirements.txt

# 3. Seed demo assets (idempotent; re-runs reuse existing datasets by name)
#    Generates the clean + poisoned datasets (seed=42, n=600) and registers
#    the pre-trained reference/candidate models.
python scripts/seed_all.py

# 4. Start the API
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run build        # TypeScript type-check + Vite build
```

The backend serves `frontend/dist` statically at `/`, so after building there is
nothing else to start — the SPA is available at `http://localhost:8000`.
(Vite dev server is not required.)

## Docker alternative

```bash
docker build -t kavachai .
docker run -p 8000:8000 kavachai
```

The image installs dependencies, runs `seed_all.py`, and starts uvicorn on
`:8000`. Fully offline once built.

## Verify the install

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Full 15-step demo: seed 42, n=600, ~6.2 s, 15/15 steps OK
curl -X POST http://localhost:8000/api/v1/demo/run \
  -H 'Content-Type: application/json' -d '{}'

# Automated suite (from repo root, .venv active): 64 tests, ~12 s
pytest tests/ -q
```

## Offline note

After `pip install` and `npm install`, the backend makes **no network calls**:
no telemetry, no model downloads, no external lookups. Datasets, models, and
reports all live on local disk (SQLite + flat files). This was a deliberate
design choice for air-gapped evaluation.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Address already in use :8000` | `uvicorn ... --port 8001`, or stop the old process |
| `ModuleNotFoundError: backend` | Run from the repo root with `.venv` activated |
| Frontend blank at `/` | Re-run `npm run build` in `frontend/`; confirm `frontend/dist/index.html` exists |
| `seed_all.py` slow first run | It trains the demo MLP models; expect ~1–2 min on 2 CPUs |
| Tests fail on a fresh clone | Ensure you are using Python 3.12 and `requirements.txt` is fully installed |
| Permission denied on scripts | `chmod +x scripts/run_demo.sh` |

If a fresh `pytest tests/ -q` does not show **64 passed**, the environment is
not the one the results in [EVALUATION.md](EVALUATION.md) were measured on.
