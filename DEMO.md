# KavachAI — SIH Demo Guide (2–3 minutes)

Reproduce the exact demonstration end to end. Everything below was verified
on 2026-09-30 on a 2-CPU Linux VM; all numbers shown are measured on
synthetic, team-generated data with known ground truth (seed 42).

## 0. One-time setup (~3 minutes)

```bash
# 1. Python 3.10+ and Node 18+ required
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Frontend dependencies (only needed once)
cd frontend && npm install && npm run build && cd ..

# 3. Seed the demo assets: clean + poisoned datasets (seed 42, n=600)
#    and the reference / poisoned-candidate demo models.
python scripts/seed_all.py
```

No internet is needed after this point. No API keys. No cloud services.

## 1. Start the system (two terminals)

```bash
# Terminal 1 — backend
source .venv/bin/activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# expect: {"status":"ok","version":"0.1.0","db_ok":true,"offline":true}
# at http://127.0.0.1:8000/api/v1/health

# Terminal 2 — frontend (static build; the UI calls same-origin /api/v1)
cd frontend/dist && python3 -m http.server 5173
# open http://127.0.0.1:5173
```

For the demo the Vite dev proxy is not needed: serve `dist/` and proxy
`/api` to the backend, or run `npm run dev` in `frontend/` (proxies
`/api` → `http://127.0.0.1:8000` automatically).

## 2. The 2–3 minute narrative (say this, click this)

> "First, we establish a clean baseline."

- Dashboard → click **RUN DEMO** (or `POST /api/v1/demo/run`).
- Step 1 loads 600 clean synthetic images; the baseline scan finds nothing.

> "We introduce controlled, reproducible integrity violations."

- Step 2 injects the attack suite with known ground truth: trigger patches,
  near-duplicate floods, label flips, OOD noise, one anomalous contributor.
- Step 3–4: the scan flags suspicious samples. Click any sample to see the
  evidence: method, score, affected asset, disposition.

> "KavachAI does not merely return SAFE or UNSAFE. It identifies the
> affected asset and shows the evidence."

- Steps 5–7: reference model vs poisoned candidate. The trigger probe shows
  candidate flip-rate **0.97 vs reference 0.38** (measured) → flagged.
- Step 8: run inference on a clean and a triggered sample.

> "Every inference is bound into a tamper-evident provenance ledger."

- Step 9 creates records binding input hash + model hash + config hash +
  model version + timestamp + nonce + output hash, hash-chained.
- Steps 10–12: a stored record is tampered with; **VERIFY CHAIN** reports
  `intact: false` and names the exact broken record
  (expected vs actual hash shown).

> "The system generates an assurance report containing evidence,
> confidence, limitations and recommended disposition."

- Step 13: distribution shift → EXPECTED_DRIFT on this run.
- Step 14: evidence aggregation (documented ladder rule) → **QUARANTINE**.
- Step 15: JSON + PDF assurance report generated and downloadable.
  The report lists what was NOT tested — read that section aloud.

## 3. What the judge can verify live

| Claim | How to check |
|---|---|
| Tests pass | `pytest tests/ -q` → 63 passed |
| Demo is real | `POST /api/v1/demo/run` → 15/15 `ok: true` |
| Tamper is detected | response step 12 names `broken_at` record id |
| Metrics are measured | `GET /api/v1/evaluation/<scan_id>` vs ground truth |
| Report is real | open the downloaded PDF |
| Nothing is hardcoded | every scan id, hash and finding is generated at runtime |

## 4. If something goes wrong on stage

- Backend won't start → check port 8000 is free; `pip install -r requirements.txt` again.
- Blank frontend → make sure you ran `npm run build` and are serving `frontend/dist`.
- Demo is idempotent: re-running `POST /api/v1/demo/run` is safe.
- Nuclear option: delete `kavach.db*`, re-run `python scripts/seed_all.py`.

## 5. Honest scope (say this if asked)

- All demo data is synthetic and team-generated; no real-world imagery tested.
- Trigger-patch recall on this synthetic setup is 0.20 — a floor, not a claim.
- OOD attribution recall is 0.000; the method does not attribute OOD samples.
- PyTorch/ONNX uploads get hash + metadata checks; weight-level checks are
  unavailable without a matching runtime — the UI says so explicitly.
- See `KNOWN_LIMITATIONS.md` and `EVALUATION.md` for the full measured picture.
