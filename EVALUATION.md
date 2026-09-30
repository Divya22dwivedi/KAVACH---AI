# Evaluation

All results below were measured on **2026-09-30** in a controlled environment:
synthetic datasets with known ground truth, fixed seeds, 2-CPU Linux VM. No
real-world imagery was used anywhere. Nothing here generalises to data we have
not tested; where a method was not tested we say so.

## Datasets

- **Synthetic image-feature generator** (`attack_generator/`): 600 samples,
  seed 42 for the full demo; 300 samples, seed 7 for the standalone data
  suite. Attacks are injected programmatically and labelled in
  `attack_manifests`, which is the ground truth for scoring.
- **Attack types**: `trigger_patch` (small patch pattern on a subset),
  `near_duplicate` (12 injected groups), `ood` (out-of-distribution noise),
  plus corruption variants for the shift tests (brightness ×1.35).

## Full demo — `POST /api/v1/demo/run` (seed 42, n=600)

- 15/15 steps OK, ~6.2 s end-to-end.
- Final disposition: **QUARANTINE**.
- Model checks on the shipped demo models (`kavach_mlp_ref.pkl` vs
  `kavach_mlp_cand.pkl`, 200 clean probe images): `trigger_test` **flag**
  (candidate flip 0.97 vs reference 0.38, diff +0.59); `behaviour_compare`
  **pass** at agreement 0.97 — expected, since a backdoored model agrees with
  the reference on clean inputs; the trigger probe is the decisive check.
  (The 0.885 → flag figure in the standalone section below comes from the
  smaller under-trained test models in `tests/test_model_integrity.py`, a
  different probe setup — both numbers are real measurements of their own
  setups.)
- Provenance tamper detected at the exact broken record.
- Shift verdict: **EXPECTED_DRIFT**, anomaly fraction 0.118.

## Evaluation vs ground truth (scan_4e26c0ca9d67, 600 samples)

| Attack | Precision | Recall | F1 | FPR | TP/FP/TN/FN |
|---|---|---|---|---|---|
| trigger_patch | 0.889 | 0.200 | 0.327 | 0.002 | 8/1/628/32 |
| near_duplicate | 0.443 | 1.000 | 0.614 | 0.078 | — |
| ood | 0.000 | 0.000 | — | 0.146 | — |
| **overall** | **0.375** | **0.633** | **0.471** | **0.205** | — |

Honest reading: the trigger heuristic is precise but misses most triggers
(recall 0.20); near-duplicate detection finds everything at the cost of false
alarms (FPR 0.078); **the outlier method does not attribute OOD samples at
all** — OOD recall is 0.000 and this is a documented limitation
([KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)).

## Data integrity standalone (controlled suite, seed 7, n=300)

- Trigger recall **0.50** at a calibrated **85th percentile** (precision 0.196,
  FPR 0.131); at the default 99th percentile, recall is **0.05**.
- 14 near-duplicate groups detected from 12 injected groups (2 splits of large
  groups — a known merge artefact).
- Contributor `contrib_c` flagged as anomalous.
- Label chi-square p≈0.23 → no finding (honest null).
- KMeans cluster probe did not fire (honest null).

## Model integrity standalone

- Trigger flip-rate probe: candidate **0.97** vs reference **0.38**
  (difference +0.59) → **flag**.
- Behaviour agreement 0.885 → **flag**.
- Weight-stat max relative deviation 0.0202 → **pass**.
- STRIP-inspired entropy: candidate 1.3530 bits vs reference 1.3383 bits → **pass**.
- Foreign/tampered pickles **refused**; ONNX/`.pt` are metadata/hash-only, with
  honest `unavailable` statuses for checks that need weights.

## Provenance

- 5-record chain verifies cleanly.
- Middle and tip tampering both detected at the **exact broken record**.
- Repeated tamper attempts refused.

## Distribution shift

| Input | Verdict | Anomaly fraction |
|---|---|---|
| Held-out clean | NORMAL | 0.025 |
| Brightness ×1.35 | SUSPICIOUS_SHIFT | 1.000 |
| OOD noise | SUSPICIOUS_SHIFT | 1.000 |

"Distribution shift indicates deviation from the reference distribution; it does not by itself establish malicious manipulation."

## Test suite and build

- `pytest tests/ -q`: **63 passed** in 12.01 s, 3 nonfatal warnings.
- Frontend: `npx tsc --noEmit` clean, `npm run build` green.

## How to reproduce

```bash
source .venv/bin/activate
python scripts/seed_all.py                                  # seed 42 datasets + models
curl -X POST http://localhost:8000/api/v1/demo/run \
  -H 'Content-Type: application/json' -d '{}'               # 15-step demo
curl http://localhost:8000/api/v1/evaluation/<scan_id>      # vs ground truth
pytest tests/ -q                                            # 63 tests
```

## Interpretation guidance

- Treat precision/recall as properties of **this synthetic setup**, not of the
  methods in general. The trigger recall of 0.20 is a floor on synthetic
  patches, not a claim about real backdoors.
- `EXPECTED_DRIFT` vs `SUSPICIOUS_SHIFT` thresholds were set on the same
  synthetic corruptions they are demonstrated on — they are illustrative, not
  calibrated for deployment.
- A QUARANTINE disposition is a recommendation to a human reviewer, not an
  automated block.

## Not evaluated yet

- Real-world imagery or non-synthetic triggers/backdoors.
- Model families other than scikit-learn MLP (PyTorch/TensorFlow/ONNX runtimes).
- Target-device or hardware-accelerated benchmarks (no Snapdragon/edge measurement).
- Adversarial adaptation: an attacker aware of these specific heuristics.
- Human-factors: whether reviewers actually act correctly on the reports.
