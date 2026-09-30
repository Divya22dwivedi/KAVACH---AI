# KavachAI — Research Findings (Phase 1)

> SIH 2026 · PS SIH26228 · Team SRIJAN
> Status: design input. Nothing here is copied code — these sources justify the
> engineering design. Where a method is too heavy for the prototype, KavachAI
> ships a **bounded baseline** and says so in the UI and report.

## 1. Governance / framing

### NIST AI Risk Management Framework 1.0 (AI RMF 1.0)
- **Year/org:** 2023, U.S. National Institute of Standards and Technology.
- **URL:** https://www.nist.gov/itl/ai-risk-management-framework
- **What KavachAI uses:** the Govern–Map–Measure–Manage functions as the
  skeleton of the assurance report (what was measured, what was *not*
  measured, residual risk, human review). The "Measure" function motivates
  reporting confidence, limitations and unsupported tests alongside every
  finding rather than a single trust score.
- **Limits:** a governance framework, not a detection algorithm; it does not
  prescribe thresholds or metrics.

### NIST AI 100-2e 2023 — "Adversarial Machine Learning: A Taxonomy and
Terminology of Attacks and Mitigations"
- **Year/org:** 2023 (updated), NIST.
- **URL:** https://doi.org/10.6028/NIST.AI.100-2e2023
- **What KavachAI uses:** the attack taxonomy (data poisoning, backdoor /
  trojan attacks, evasion) to define the *supported attack classes* list in
  reports, and the explicit separation of **model-agnostic vs model-specific**
  mitigations — this is why black-box and white-box paths are separate in
  KavachAI and why black-box trigger reconstruction is listed as unsupported.
- **Limits:** taxonomy only; no reference implementations.

## 2. Backdoor / trojan attacks (threat model)

### BadNets — Gu, Dolan-Gavitt, Garg (2017)
- **Paper:** "BadNets: Identifying Vulnerabilities in the Machine Learning
  Model Supply Chain", arXiv 1708.06733 (IEEE Access 2019).
- **URL:** https://arxiv.org/abs/1708.06733
- **What KavachAI uses:** the canonical threat model — a model that keeps high
  clean-data accuracy but misbehaves on a trigger. This is exactly what the
  demo generator reproduces (trigger patch + label flip, clean accuracy
  retained). It justifies the demo metric pair: *clean accuracy* vs
  *trigger success rate*.
- **Limits:** attack paper, not a defense; gives no detection method.

### TrojAI (IARPA / NIST program)
- **Org:** IARPA, later NIST rounds.
- **URL:** https://www.iarpa.gov/research-programs/trojai
- **What KavachAI uses:** the evaluation discipline — detection claims are
  only meaningful against **known ground truth** (triggered vs clean models,
  known target labels). KavachAI's attack generator stores
  `attack_id / attack_type / affected_samples / generation_parameters /
  ground_truth` for this reason.
- **Limits:** program-level; datasets and rounds are external artifacts.

### BackdoorBench — Wu et al. (2022)
- **Paper:** "BackdoorBench: A Comprehensive Benchmark of Backdoor Learning",
  NeurIPS 2022.
- **URL:** https://arxiv.org/abs/2206.04815
- **What KavachAI uses:** the benchmarking principle — report precision,
  recall, F1 and false-positive rate of each detector on controlled
  scenarios; never a single headline number. Shapes `EVALUATION.md`.
- **Limits:** full benchmark is far beyond prototype scope; KavachAI adopts
  the *reporting discipline*, not the benchmark suite.

## 3. Detection methods (what the baselines are distilled from)

### Spectral Signatures — Tran, Li, Madry (2018)
- **Paper:** "Spectral Signatures in Backdoor Attacks", NeurIPS 2018.
- **URL:** https://arxiv.org/abs/1811.00636
- **What KavachAI uses:** the core idea — poisoned samples leave a detectable
  trace in the *representation* (feature) space, separable via SVD/PCA.
  **Bounded baseline shipped:** per-class PCA on simple image features;
  samples with large reconstruction error or strong alignment with the top
  singular direction are flagged "Suspicious (representation outlier)".
- **Limits:** the paper's result assumes learned deep representations; our
  baseline uses handcrafted features + PCA, which is weaker — documented as
  a limitation.

### Activation Clustering — Chen et al. (2018)
- **Paper:** "Detecting Backdoor Attacks on Deep Neural Networks by Activation
  Clustering", arXiv 1811.03728.
- **URL:** https://arxiv.org/abs/1811.03728
- **What KavachAI uses:** the idea of clustering activations/features *within*
  a class to find a small sub-population (the poisoned cluster).
  **Bounded baseline shipped:** KMeans (k=2) on per-class PCA features; a
  small, tight minority cluster is flagged for review.
- **Limits:** needs enough poisoned samples to form a cluster; ineffective at
  very low poison rates — stated in limitations.

### STRIP — Gao et al. (2019)
- **Paper:** "STRIP: A Defence Against Trojan Attacks on Deep Neural
  Networks", ACSAC 2019.
- **URL:** https://arxiv.org/abs/1902.06531
- **What KavachAI uses:** the inference-time intuition — superimposing a
  suspect input on random clean inputs: trigger-carrying inputs produce
  unnaturally *stable* predictions (low entropy). **Bounded baseline
  shipped:** perturbation-consistency check — blend the input with N random
  reference images, measure prediction entropy; low entropy + trigger-like
  patch → "Suspicious (prediction-stability anomaly)". Labeled as
  STRIP-inspired, not STRIP.
- **Limits:** the original assumes image-classification DNNs; ours is a
  black-box behavioral test valid for any classifier with a predict API.

### Neural Cleanse — Wang et al. (2019)
- **Paper:** "Neural Cleanse: Identifying and Mitigating Backdoor Attacks in
  Neural Networks", IEEE S&P 2019.
- **URL:** https://ieeexplore.ieee.org/document/8835365
- **What KavachAI uses:** the *concept* of trigger reverse-engineering and
  its honesty lesson — full NC needs white-box gradient optimization and is
  expensive. **Prototype scope decision:** KavachAI does NOT implement
  trigger reconstruction. The report lists "Black-box trigger reconstruction:
  NOT performed — requires white-box gradient access" under *Unsupported
  tests*. The bounded substitute is the *controlled trigger test*: apply the
  **known** demo trigger and measure the flip rate (a measurement, not a
  reconstruction).
- **Limits:** none adopted beyond the concept; deliberate non-implementation.

## 4. Data-integrity primitives

### Perceptual hashing (pHash / dHash)
- **Basis:** DCT-based perceptual hash (Zauner-style pHash); dHash (gradient
  hash) as popularized by the ImageHash library.
- **What KavachAI uses:** exact SHA-256 for exact duplicates; 64-bit dHash
  with Hamming-distance threshold for near-duplicates (threshold documented
  in ml-methodology.md). Implemented from scratch with numpy/Pillow — no
  copied code.
- **Limits:** pHash/dHash are not robust to heavy cropping/rotation; the
  threshold is a heuristic, reported as such.

### Label-noise / distribution analysis
- **Basis:** standard statistical practice (chi-square goodness-of-fit
  against the declared class distribution; per-class count z-scores).
- **What KavachAI uses:** flags *label-distribution anomalies* ("Anomalous",
  never "malicious" — anomaly ≠ intent).
- **Limits:** cannot distinguish malicious flipping from sloppy labeling;
  the UI uses "Requires Review" language.

## 5. Provenance / audit literature

### Cryptographic audit logs — Schneier & Kelsey (1998)
- **Paper:** "Cryptographic Support for Secure Logs on Untrusted Machines",
  USENIX Security 1998.
- **URL:** https://www.schneier.com/wp-content/uploads/2015/12/paper-secure-log.pdf
- **What KavachAI uses:** the hash-chained, append-only log construction:
  each record commits to the previous record's hash, so modification breaks
  the chain. KavachAI implements exactly this — **not a blockchain**
  (no consensus, no distributed ledger, no mining); the UI/report use the
  term "tamper-evident cryptographic provenance ledger".
- **Limits:** hash chaining detects *modification*, not *deletion from the
  tail* or a fully rewritten log — documented; mitigation is the
  append-only DB constraint + periodic external anchoring (future roadmap).

### Merkle trees — Merkle (1987)
- **Paper:** "A Digital Signature Based on a Conventional Encryption
  Function", CRYPTO 1987.
- **What KavachAI uses:** concept only — dataset-level manifest commits to
  per-sample hashes (a flat hash list; full Merkle tree is future work).
  The dataset manifest hash binds all sample hashes.

### W3C PROV / supply-chain provenance (conceptual)
- **What KavachAI uses:** the vocabulary — every inference record binds
  input hash + model hash + config hash + output hash + timestamp + nonce.
  No formal PROV-DM export in the prototype (roadmap).

## 6. Distribution shift
- **Basis:** standard OOD practice — reference distribution statistics,
  Mahalanobis distance in feature space, image-quality signals (brightness,
  blur via Laplacian variance, resolution).
- **What KavachAI uses:** reference-set feature mean/covariance; incoming
  batch scored by Mahalanobis distance; thresholds from reference quantiles
  (documented). Three-way output: NORMAL / EXPECTED_DRIFT / SUSPICIOUS_SHIFT.
- **Limits:** shift ≠ attack; the report carries the mandatory disclaimer
  that shift indicates deviation, not malicious manipulation.

## 7. What was deliberately NOT adopted
- Full Neural Cleanse trigger reconstruction (needs white-box gradients +
  heavy optimization; out of prototype scope).
- Blockchain / DLT for provenance (no consensus need; hash chain suffices and
  is honest).
- Certified defenses, differential-privacy training, formal verification —
  research-grade, listed in FUTURE_ROADMAP.md.
