# References

What this prototype borrows from, one line each. Canonical titles only — no
invented links; consult the original publications for exact text.

- **NIST AI Risk Management Framework 1.0** — structures the assurance report
  around the Govern/Map/Measure/Manage functions.
- **NIST AI 100-2e (Adversarial Machine Learning taxonomy)** — vocabulary for
  the attack classes the generator implements (data poisoning, evasion-style
  triggers).
- **BadNets (Gu et al.)** — the trigger-patch backdoor threat model behind the
  `trigger_patch` synthetic attack and the flip-rate probe.
- **Neural Cleanse (Wang et al.)** — inspiration for probing a model for
  trigger-like behaviour without full trigger reconstruction.
- **Spectral Signatures (Tran et al.)** — statistical-outlier intuition behind
  the data-integrity trigger heuristic.
- **Activation Clustering (Chen et al.)** — the clustering-based poison
  detection idea; our KMeans probe did not fire on the demo data (honest null,
  documented in EVALUATION.md).
- **STRIP (Gao et al.)** — the entropy-based runtime backdoor probe; our
  STRIP-inspired check measured 1.3530 vs 1.3383 bits → pass on the demo pair.
- **TrojAI / BackdoorBench** — dataset and benchmark design conventions for
  backdoor evaluation; our ground-truth manifest approach mirrors their
  labelled-attack methodology at toy scale.
- **Schneier–Kelsey secure audit logs** — hash-chained, tamper-evident log
  design behind the provenance ledger.
- **Merkle trees** — the hash-linking principle used for the provenance
  chain's `record_hash`/`prev_hash` records.

None of the above endorse this prototype; they are the intellectual sources of
its methods, adapted to a controlled synthetic setting.
