# KavachAI — ML Methodology (Phase 1)

All thresholds below are defaults, stored per-run in `params_json`, and
reported in the assurance report. "Confidence" per method is defined here —
never invented per finding.

## Common primitives
- **Features:** per image — 8×8 grayscale thumbnail (64 dims) + 16-bin
  per-channel color histogram (48 dims) + brightness/contrast/blur scalars.
  PCA to 16 dims for statistical tests (seeded).
- **Hashes:** SHA-256 (exact), 64-bit dHash (perceptual).
- **dHash threshold:** Hamming distance ≤ 6 → near-duplicate edge
  (empirically separates resized/recompressed copies from distinct synthetic
  shapes in our generator; reported as heuristic).

## Module 1 — Data integrity
1. **Exact duplicates:** group by `sha256`. Finding per group (severity:
   info if same label+contributor, medium if label conflict).
2. **Near-duplicates:** dHash graph, connected components with edge ≤ 6.
   Component size ≥ 3 → "flooding candidate" (medium, REVIEW).
3. **Representation outlier (Spectral-Signatures-inspired, bounded):**
   per class, PCA(16) → reconstruction error; flag samples above the
   99th percentile of the class error distribution. Confidence =
   min(0.95, percentile/100). Limitation: weak vs adaptive triggers.
   *Calibration note (measured 2026-09-29):* the 99th-percentile default is
   calibrated for low poison rates — on a suite with ~16% in-class poison
   it yields recall ≈ 0.05 (mathematical ceiling of a top-1% rule). The
   bounded-baseline evaluation therefore uses a documented per-run
   operating point (`outlier_percentile=85`), stored in the scan params,
   which measured recall 0.50 / precision 0.196 / FPR 0.131 on the
   controlled suite. Both operating points are reported; the default's
   limitation is locked in by test.
4. **Label-distribution anomaly:** chi-square of observed class counts vs
   the *declared* distribution in the manifest (default: uniform); p < 0.01
   → dataset-level finding (low/medium). Per-class z-score > 3 → class-level.
   Language: "Anomalous — requires review"; never asserts malice.
5. **Activation-clustering-inspired (bounded):** per class KMeans(k=2) on
   PCA features; if minority cluster is ≤ 15% of class AND its centroid
   distance > 2σ → flag cluster members (low confidence 0.55, REVIEW).
6. **Trigger-patch heuristic (bounded):** for flagged outliers, compute
   patch-energy map (|image − class median|). Because poisoned samples are
   usually relabeled to the target class, their whole-image content differs
   diffusely from the class median, so a plain pixel-fraction gate never
   fires (measured 0/40 on the demo suite, 2026-09-30). The heuristic
   therefore takes pixels near the global energy maximum (threshold
   max(0.8 × max, 5 × median pixel difference)) and requires their bounding
   box to be compact (< 5% of image area, ≥ 4 pixels) — a trigger patch is
   by definition a compact high-energy region, while relabel content
   mismatch is diffuse. Fires → "trigger-like patch" evidence with bbox
   (heuristic evidence only, never a verdict).
   Measured on the demo suite (seed 42, n=600, 40 trigger GT):
   heuristic recall 0.200, precision 0.889, FPR 0.002.
   attached (not a standalone verdict).
7. **Contributor aggregation:** per contributor, anomaly rate vs global rate
   (binomial test, p < 0.05, ≥5 samples) → contributor-level finding.

## Module 2 — Model integrity
Checks run in order; each returns `pass | flag | unavailable`.
1. **hash_verify:** recompute SHA-256 == registered digest → pass/flag
   (critical if mismatch).
2. **metadata inspection:** format, size, class labels, manifest_ok.
3. **behaviour_compare (black-box OK):** prediction agreement between
   candidate and reference on a clean probe set (n=200, seeded).
   Agreement < 0.95 → flag (medium). *Measured*, not asserted.
4. **trigger_test (controlled, needs executable model + known trigger):**
   apply the generator's trigger patch to probe inputs; measure
   flip-to-target rate. Candidate flip rate − reference flip rate > 0.5
   → flag (high, QUARANTINE recommended). This is a *measurement against
   known ground truth*, not trigger reconstruction.
5. **weight_stats (white-box sklearn-MLP only):** per-layer L2 norms vs
   reference; relative deviation > 50% → flag (low). Note: coarse signal.
6. **perturbation-consistency (STRIP-inspired, black-box OK):** blend input
   with 20 random reference images; prediction entropy < 0.5 bits AND
   trigger-like patch present → flag (medium). Labeled STRIP-inspired.
7. **Black-box limits:** weight_stats → `unavailable` with note
   "Assessment unavailable because required model access is not available.";
   trigger *reconstruction* → listed under report "Unsupported tests".

## Module 3 — Provenance
- `record_hash = SHA256(prev_hash ‖ input_hash ‖ model_hash ‖
  config_hash ‖ output_hash ‖ timestamp ‖ record_id)` (‖ = concatenation
  of canonical UTF-8 strings).
- `verify`: recompute every record from genesis; first mismatch →
  `{ intact: false, broken_at, expected_hash, actual_hash }`.
- Append-only enforced in service layer; the only UPDATE path is the
  labeled tamper-demo sandbox.

## Module 4 — Distribution shift
- Reference stats: PCA-feature mean μ, covariance Σ (Ledoit-Wolf shrinkage
  via sklearn) + quality signals (brightness mean/var, Laplacian-variance
  blur, resolution histogram).
- Score per image: Mahalanobis distance d = √((x−μ)ᵀΣ⁻¹(x−μ)).
- Thresholds from reference quantiles: d ≤ q95 → NORMAL;
  q95 < d ≤ q99 → EXPECTED_DRIFT; d > q99 → anomaly vote.
- Batch verdict: anomaly fraction < 5% → NORMAL; 5–20% → EXPECTED_DRIFT;
  > 20% → SUSPICIOUS_SHIFT. Plus quality-signal deltas reported.
- Mandatory disclaimer: shift = deviation, not proof of manipulation.

## Module 5 — Evidence aggregation (documented logic)
- **Severity ladder:** critical > high > medium > low > info. A finding's
  severity comes from its method table above, never hand-tuned per demo.
- **Disposition policy (rule-based, in order):**
  1. Any `critical` (hash mismatch, broken provenance link) → QUARANTINE.
  2. Any `high` (trigger test flag, tampered record) → QUARANTINE.
  3. Any `medium` (representation outliers, shift=SUSPICIOUS_SHIFT,
     contributor anomaly) → REVIEW.
  4. Else if any `low` → REVIEW; else ACCEPT.
- **Dashboard shows per-module status** (Data / Model / Provenance / Shift
  each: OK / REVIEW / QUARANTINE) — no single opaque "trust score".
- **Confidence:** per-method definitions above; aggregation does NOT
  average confidences (documented: confidences are not commensurable).

## Evaluation metrics (from generator ground truth)
- Per detector: precision, recall, F1, false-positive rate, confusion
  matrix (TP/FP/TN/FN) — computed only when an attack manifest with ground
  truth exists for the scanned dataset; otherwise "Not evaluated yet".
- Provenance: intact-chain verify (pass), tamper-demo detection (pass),
  broken-link identification (exact record id).
