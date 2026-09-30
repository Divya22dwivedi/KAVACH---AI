# KavachAI — Demo Scenario & Script (Phase 1)

Target: ~2–3 minutes, one click (`RUN DEMO` button → `POST /api/v1/demo/run`,
or `scripts/run_demo.sh`). All data synthetic, seeded, local.

## Narrative (Sujal's exact story)
1. "First, we establish a clean baseline."
2. "We introduce controlled, reproducible integrity violations."
3. "KavachAI does not merely return SAFE or UNSAFE. It identifies the
   affected asset and shows the evidence."
4. DATA → MODEL → INFERENCE walkthrough.
5. "The system generates an assurance report containing evidence,
   confidence, limitations and recommended disposition."

## Step-by-step (15 steps)
| # | Step | What the judge sees | API |
|---|---|---|---|
| 1 | Load clean dataset | 600 synthetic shape images (circle/square/triangle), manifest hash | `attacks/generate{scenario:clean}` |
| 2 | Generate controlled poison | Full attack suite on a copy: 30 label flips, 40 trigger patches (→ target class), 25 near-dupes, 30 OOD; ground-truth manifest stored | `attacks/generate{scenario:full_suite}` |
| 3 | Scan dataset | Progress → counts: total / suspicious / dup groups / OOD / label anomalies | `POST /scans` |
| 4 | Show suspicious samples | Gallery: trigger-patch sample with patch-energy overlay + evidence panel (method, score, confidence, limitation) | `GET /scans/{id}/findings` |
| 5 | Load reference model | Clean MLP (`ref-v1`), SHA-256 digest displayed | `POST /models/upload` |
| 6 | Load candidate model | Poisoned MLP (`cand-v1`), digest displayed | `POST /models/upload` |
| 7 | Run model checks | Behaviour agreement (measured), controlled trigger test: flip-rate ref vs candidate (measured), weight stats | `POST /models/{id}/checks` |
| 8 | Run inference | Predict on clean + triggered sample; both outputs shown | `POST /inference/predict` ×2 |
| 9 | Create provenance records | Chain RECORD 001→004 visualized, all green | `GET /provenance/chain` |
| 10 | Tamper with one record | Sandbox tamper of RECORD 003's output (labeled synthetic) | `POST /provenance/tamper-demo` |
| 11 | Verify provenance | `POST /provenance/verify` | |
| 12 | Detect broken chain | Chain view: 003 red, "broken at RECORD 003 — expected `abc…`, got `def…`" | UI |
| 13 | Distribution analysis | Reference vs shifted batch: verdict SUSPICIOUS_SHIFT with Mahalanobis histogram | `POST /shift/assess` |
| 14 | Aggregate evidence | Assurance summary: per-module status + disposition ladder applied (rule-based) | findings aggregation |
| 15 | Generate assurance report | JSON + PDF download; judge sees Findings, Evidence, Limitations, "Not tested" sections | `POST /reports/generate` |

## Demo data parameters (seeded defaults)
- `seed=42`, 600 clean images 32×32 RGB; classes: circle / square / triangle.
- Trigger: 5×5 white patch, bottom-right corner; target class: triangle.
- Poison: 40 trigger samples (label→target), 30 label flips, 25 near-dup
  pairs (brightness ±3%), 30 OOD (high-frequency noise textures).
- Models: `MLPClassifier(hidden=(64,32), max_iter=300)` on 8×8 grayscale
  features; reference trained on clean; candidate trained on poisoned
  (trigger→target). Both trained **during demo setup** (fast: <60 s) or
  pre-generated and shipped under `models/`.
- Probe set: 200 clean held-out images for behaviour/trigger tests.

## Honesty rails in the demo
- Every attack labeled "synthetic — team-generated".
- Metrics shown are measured in that run (or "Not evaluated yet").
- Tamper step is explicitly a *sandboxed demonstration*.
- Report lists unsupported tests (e.g., black-box trigger reconstruction).
