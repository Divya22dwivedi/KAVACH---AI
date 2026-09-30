# KavachAI — Requirement → Feature Mapping (Phase 1)

Every requirement from Sujal's spec mapped to a concrete, implemented
feature. Status legend: **BUILD** = in prototype, **BASELINE** = bounded
baseline with documented limits, **OUT** = explicitly not in prototype
(listed in report as "not tested").

## Module 1 — Data Integrity
| Spec requirement | Feature | Status |
|---|---|---|
| Ingest image folders / CSV metadata / YOLO / COCO | `DatasetIngestor`: folder-of-images, CSV manifest, YOLO (images+labels/*.txt), COCO JSON (subset: images/annotations/categories) | BUILD |
| Detect label flipping | Label-distribution analysis (chi-square vs declared distribution) + per-class count z-scores; sample-level "label anomaly" via representation outlier within class | BASELINE |
| Detect trigger-based poisoned samples | Representation-outlier scan (per-class PCA reconstruction error, Spectral-Signatures-inspired) + patch-consistency check | BASELINE |
| Detect near-duplicate flooding | Exact SHA-256 match + 64-bit dHash near-duplicate graph (Hamming ≤ threshold) | BUILD |
| Detect OOD samples | Feature-space kNN distance to class centroid; image-quality signals | BASELINE |
| Detect suspicious contributor behaviour | Contributor aggregation: anomaly rate per contributor vs global baseline; metadata/source roll-up | BUILD |
| Sample → contributor → risk summary | Findings hierarchy implemented in evidence engine | BUILD |
| "Suspicious/Anomalous/Requires Review" language | Enforced in finding templates; intent never asserted | BUILD |

## Module 2 — Model Integrity
| Spec requirement | Feature | Status |
|---|---|---|
| Support PyTorch / ONNX ingestion | `.pt/.pth`: SHA-256 + safe zip listing (record names, sizes) — **never unpickled**; `.onnx`: SHA-256 + graph metadata via `onnx` lib; `.pkl`: execution ONLY for KavachAI-generated models with manifest digest check, else metadata-only | BUILD (ingest) / BASELINE (analysis depth) |
| Model hash (SHA-256), metadata | `ModelRegistry`: digest, format, size, created, manifest | BUILD |
| Integrity checks | Hash verification against manifest; metadata inspection; weight-stat comparison vs reference (for sklearn MLP: layer norms) | BUILD |
| Reference-vs-candidate behaviour comparison | Prediction agreement rate on clean probe set (measured) | BUILD |
| Bounded backdoor/trigger tests | **Controlled trigger test**: apply the *known* demo trigger to probe inputs; measure flip-to-target rate on candidate vs reference (measurement, not reconstruction) | BASELINE |
| Activation/statistical analysis | Weight-norm deviation vs reference; prediction-stability (STRIP-inspired) test | BASELINE |
| Graceful black-box fallback | If weights unavailable: behavioural checks only; UI shows "Assessment unavailable because required model access is not available." for white-box items | BUILD |
| No fake equivalence | Report section "Unsupported tests" lists what black-box cannot do | BUILD |

## Module 3 — Inference Provenance
| Spec requirement | Feature | Status |
|---|---|---|
| Bind input/model/config/output hashes + timestamp + nonce | `ProvenanceRecord`: `record_hash = SHA256(prev_hash ‖ input_hash ‖ model_hash ‖ config_hash ‖ output_hash ‖ timestamp ‖ nonce)` | BUILD |
| Tamper-evident append-only hash-chain log | SQLite `inference_records` with `prev_hash` FK-like linkage; verification walks the chain | BUILD |
| Demo: intact → tamper → broken link identified | `POST /api/v1/provenance/tamper-demo` modifies a copy-sandboxed record; `POST /verify-chain` returns exact failing record id + expected vs actual hash | BUILD |
| Terminology | "tamper-evident cryptographic provenance ledger" everywhere; "blockchain" never used for this | BUILD |

## Module 4 — Distribution Shift
| Spec requirement | Feature | Status |
|---|---|---|
| Reference vs current distribution | Feature stats (PCA embedding mean/cov) + image-quality signals (brightness, blur, resolution) | BUILD |
| NORMAL / EXPECTED_DRIFT / SUSPICIOUS_SHIFT | Mahalanobis-distance scoring; thresholds from reference quantiles (documented) | BASELINE |
| Shift ≠ attack disclaimer | Mandatory text in UI + report | BUILD |

## Module 5 — Evidence Engine
| Spec requirement | Feature | Status |
|---|---|---|
| Unified evidence object | `finding_id, asset_id, category, detection_method, evidence, confidence, severity, disposition, supported_attack_class, limitations, timestamp` | BUILD |
| Aggregation logic documented | Rule-based: severity ladder + disposition policy in `ml-methodology.md`; **no single opaque trust score** | BUILD |

## Module 6 — Assurance Report
| Spec requirement | Feature | Status |
|---|---|---|
| JSON + PDF | ReportLab PDF + JSON download | BUILD |
| 17 required sections | All present; "Unsupported tests" and "Limitations" are mandatory sections | BUILD |
| "What was NOT tested" explicit | e.g. "Black-box trigger reconstruction was not performed because model weights/gradients were unavailable." | BUILD |

## Attack Generator / Demo Data
| Spec requirement | Feature | Status |
|---|---|---|
| Clean / label-flipped / trigger-injected / near-duplicate / OOD / tampered-record scenarios | `attack_generator/`: seeded, reproducible; ground truth manifest (`attack_id, attack_type, affected_samples, generation_parameters, ground_truth`) | BUILD |
| Local-only, labeled synthetic | All images generated with numpy/Pillow; `synthetic: true` in every manifest | BUILD |

## Evaluation
| Spec requirement | Feature | Status |
|---|---|---|
| Precision/recall/F1/FPR/confusion matrix where applicable | `ml/evaluation/`: computed from generator ground truth vs detector flags | BUILD |
| Provenance: intact/tampered/broken-link | Verified by test + demo | BUILD |
| "Not evaluated yet" | Any module without a completed run shows exactly this string | BUILD |

## UI (7 pages)
Dashboard · Data Integrity · Model Integrity · Provenance · Distribution
Shift · Findings · Assurance Report — all wired to real API calls; no dummy
buttons. React + TypeScript + Vite; custom SVG charts.

## Offline / Security
| Spec requirement | Feature | Status |
|---|---|---|
| Offline after install | Zero runtime network calls; deps vendored at install; synthetic data | BUILD |
| Input validation, size limits, path traversal | Filename sanitization, `..` rejection, 50 MB upload cap, temp files via `tempfile`, magic-byte checks for images | BUILD |
| No arbitrary code execution from uploads | `.pt/.pth` never unpickled; `.pkl` execution allowlist = own manifest digests only; ONNX parsed as protobuf | BUILD |
| Deterministic hashing, reproducible experiment IDs | Seeded RNG; `experiment_id = sha256(canonical_params)` | BUILD |

## OUT of prototype (documented, not faked)
- Neural-Cleanse-style trigger *reconstruction*
- Blockchain/DLT consensus
- Certified/verified defenses, formal methods
- Video/3D data, multi-modal inputs
- Production deployment hardening
