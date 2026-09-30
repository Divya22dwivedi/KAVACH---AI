# Known Limitations

Numbered, honest, and current as of 2026-09-30. Each limitation is a reason to
treat KavachAI as a prototype, not a deployment.

1. **Trigger recall is low.** Full demo: recall 0.20 at precision 0.889; the
   heuristic misses most trigger patches. The default 99th-percentile
   operating point scores recall 0.05 on the standalone suite; the calibrated
   85th-percentile point reaches recall 0.50 at precision 0.196 and FPR 0.131.
   Both points are documented in EVALUATION.md so the trade-off is visible.
2. **OOD attribution is zero.** The outlier method detects that OOD samples
   exist but does not attribute them: OOD recall 0.000, FPR 0.146. This is a
   method gap, not a tuning issue.
3. **No full trigger reconstruction.** Probes (flip-rate, STRIP-inspired
   entropy) detect trigger-*like behaviour*; they do not recover the trigger
   pattern itself.
4. **sklearn-only demo models.** Only scikit-learn MLPs are exercised
   end-to-end. ONNX and `.pt`/`.pth` files are metadata/hash-only;
   `.pt`/`.pth` are never unpickled and checks that need weights report honest
   `unavailable` statuses.
5. **Synthetic data only.** Every measured number comes from the programmatic
   generator with known ground truth. No real-world imagery has been tested.
6. **Thresholds are illustrative.** Shift verdicts (`NORMAL` / `EXPECTED_DRIFT`
   / `SUSPICIOUS_SHIFT`) were set on the same synthetic corruptions they
   demonstrate on; they are not calibrated for operational use.
7. **Near-duplicate grouping splits.** 14 groups detected from 12 injected
   groups — large groups can split, a known merge artefact.
8. **Provenance detects, not prevents.** The ledger reveals post-hoc tampering
   at the exact broken record, but a privileged attacker with database write
   access could rewrite history; the audit log makes rewriting visible, not
   impossible.
9. **No adversarial adaptation tested.** An attacker aware of these specific
   heuristics has not been evaluated.
10. **No target-device benchmark.** No measurement on edge/Snapdragon-class
    hardware; runtime figures (~6.2 s demo, 12.01 s test suite) are from a
    2-CPU VM.
11. **Absence of findings proves nothing.** A clean report means these probes
    found nothing; it does not establish that data or models are uncompromised.
12. **Distribution shift is not evidence of malice.** "Distribution shift indicates deviation from the reference distribution; it does not by itself establish malicious manipulation."
13. **RUN DEMO resets the ledger.** The one-click demo calls `reset_chain` for a reproducible narrative; any user-created provenance records are replaced. The reset is audit-logged, but do not press RUN DEMO on a ledger you need to keep.
