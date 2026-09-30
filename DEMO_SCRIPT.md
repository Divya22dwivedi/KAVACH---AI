# Demo Script (5 minutes, narrated)

Setup: backend on `http://localhost:8000`, seeded with
`python scripts/seed_all.py`. Kick off the demo first — it takes ~6.2 s:

```bash
curl -X POST http://localhost:8000/api/v1/demo/run \
  -H 'Content-Type: application/json' -d '{}'
```

It runs 15 steps, 15/15 OK, ending in a **QUARANTINE** disposition. Narrate
the UI while the steps land.

## 0:00–0:45 — Dashboard (steps 1–3: dataset, attack generation, manifest)

"KavachAI is an offline assurance workbench — it checks whether a vision
dataset and model can be trusted *before* deployment. We've generated a
synthetic 600-sample dataset, seed 42, then injected labelled attacks:
trigger patches, near-duplicates, and out-of-distribution noise. The labels
are stored in an attack manifest — our ground truth, so we can score
ourselves honestly."

Point at: dataset id, sample count 600, `manifest_hash`.

## 0:45–1:45 — Data Integrity (steps 4–6: scan, findings, metrics)

"The data scan fires four probes. The trigger heuristic found 8 of 40
patches — precision 0.889, recall 0.20. We show that miss rate openly.
Near-duplicate detection caught every injected group, recall 1.00, at a
0.078 false-positive rate. And the OOD detector? Recall 0.000 — the outlier
method doesn't attribute out-of-distribution samples, and we document that as
a limitation rather than hiding it."

Point at: `total_findings`, `by_severity`, the scan_4e26c0ca9d67 evaluation
table (P=0.375, R=0.633, F1=0.471 overall).

## 1:45–2:30 — Model Integrity (steps 7–9: register, checks, probe results)

"Now the model. We never unpickle `.pt` files — foreign pickles are refused.
Two flags fired: the trigger flip-rate probe, 0.97 candidate vs 0.38
reference, and behaviour agreement at 0.885. Weight statistics passed at a
0.0202 max relative deviation, and the STRIP-inspired entropy check passed —
1.3530 vs 1.3383 bits. No single trust score: you see every check,
pass or flag."

Point at: `check_name` / `status` / `result` / `note` rows.

## 2:30–3:15 — Provenance (steps 10–12: anchor, chain, tamper demo)

"Every inference is hashed into a tamper-evident ledger — hash-linked, not a
blockchain. The chain verifies across 5 records. Then we tamper one record in
the middle — and the verifier pinpoints the exact broken record. Repeated
tamper is refused."

Point at: `record_hash`, `prev_hash`, `broken_at` pointing at the tampered id.

## 3:15–4:00 — Distribution Shift (step 13: assess)

"Shift monitoring compares live input against the reference distribution.
Clean held-out data reads NORMAL at 0.025 anomaly fraction. Brightness
pushed ×1.35, or OOD noise, trips SUSPICIOUS_SHIFT at 1.000. And every screen
carries the disclaimer: *distribution shift indicates deviation from the
reference distribution; it does not by itself establish malicious
manipulation.*"

## 4:00–4:45 — Findings + Report (steps 14–15: aggregate, report)

"Evidence aggregates into a disposition — here, QUARANTINE. That is a
recommendation to a human reviewer, who always overrides. The report ships as
JSON and a ReportLab PDF with every module's status and evidence attached."

Point at: `disposition: QUARANTINE`, then download the PDF at
`/api/v1/reports/{report_id}.pdf`.

## 4:45–5:00 — Close

"Everything you saw is measured and reproducible — 63 tests green, and the
evaluation doc lists exactly what we have *not* yet tested: real imagery,
other model families, adversarial adaptation. That's the honest boundary of
this prototype."
