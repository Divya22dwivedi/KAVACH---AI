# Future Roadmap

Every item below is **unevaluated future work** — none has been attempted, and
none may be claimed as a capability of the current prototype.

## Near term

1. **Real-imagery pilots.** Re-run the data-integrity suite on public vision
   datasets with injected, then naturally occurring, anomalies — to see which
   synthetic findings survive contact with reality.
2. **Adaptive thresholds.** Replace fixed percentiles with threshold selection
   on held-out calibration splits, reported with confidence intervals.
3. **OOD attribution research.** Methods that attribute — not just detect —
   out-of-distribution samples, closing limitation #2 in KNOWN_LIMITATIONS.md.

## Medium term

4. **Trigger reconstruction.** Move from behaviour probes to recovering the
   trigger pattern itself (Neural Cleanse-style optimisation), evaluated
   against ground-truth injected triggers.
5. **Model-format coverage.** Real weight-level checks for ONNX and PyTorch
   formats with safe, sandboxed loading — replacing today's metadata-only
   entries.
6. **Adversarial adaptation studies.** Red-team the heuristics with attackers
   that know the detection pipeline.

## Longer term

7. **Hardware benchmark.** Measure the full pipeline on target edge hardware
   (e.g. Snapdragon-class devices) instead of the 2-CPU VM.
8. **Human-factors review UX.** Study whether reviewers actually act correctly
   on QUARANTINE/REVIEW recommendations — the disposition is only as good as
   the human override it informs.
9. **Deployment hardening.** Authentication, multi-user audit, signed reports —
   only after the evaluation story above is solid. Until then, the prototype
   stays a prototype.
