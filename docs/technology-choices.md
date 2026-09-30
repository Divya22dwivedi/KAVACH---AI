# KavachAI — Technology Choices (Phase 1)

| Layer | Choice | Justification |
|---|---|---|
| Backend API | **Python + FastAPI** | Spec-mandated; auto OpenAPI docs (`/docs`); type-validated I/O via Pydantic (input validation for free) |
| ML | **numpy + scikit-learn + Pillow** | All baselines (PCA, KMeans, Mahalanobis, chi-square, MLPClassifier) are natively sklearn/numpy; deterministic with seeds; small offline wheels |
| Deep learning | **NOT used in demo model** | Deviation from "PyTorch preferred", justified: the demo box has ~2 GB free RAM and must install offline-quickly; a torch CPU wheel (~200 MB+) plus training time breaks the 2–3 min demo budget. The assurance logic is model-*interface*-agnostic (needs only `predict`), so the sklearn MLP is a legitimate stand-in. **Ingestion still accepts `.pt/.pth` and `.onnx`** for hash + metadata (honest scope: behavioral/white-box depth varies by format — see KNOWN_LIMITATIONS.md) |
| ONNX | **`onnx` (protobuf parser) only** | Graph/metadata inspection without executing arbitrary graphs; no onnxruntime needed since demo inference uses sklearn |
| Image I/O | **Pillow** | Pure, offline, magic-byte validation |
| CV ops | **numpy/Pillow** | Deviation from "OpenCV where available": keeps install tiny; all needed ops (resize, grayscale, DCT for pHash, Laplacian variance) are a few lines of numpy |
| DB | **SQLite** | Spec-mandated; single-file evidence store; WAL mode; suits air-gapped use |
| PDF | **ReportLab** | Spec-mandated; pure-local PDF generation |
| Frontend | **React + TypeScript + Vite** | Spec-mandated; type safety; fast dev |
| Charts | **Hand-rolled SVG** | Deviation from "recharts/Plotly": zero extra deps, fully offline, full control over honest visuals (no chartjunk); justified in docs |
| Hashing | **hashlib SHA-256** | Deterministic, stdlib, no dep |
| Tests | **pytest + httpx (TestClient)** | Spec-mandated coverage list |
| Packaging | **venv + pip; docker/** | `python:3.12-slim` image; frontend static build |

## Explicit non-choices
- **No cloud SDKs, no API keys, no telemetry** — runtime network calls: none.
- **No blockchain libraries** — the ledger is a SHA-256 hash chain, not a DLT.
- **No copied research code** — baselines re-implemented from paper *ideas*
  (Spectral Signatures → PCA outlier; STRIP → perturbation-consistency;
  Activation Clustering → per-class KMeans), each labeled "X-inspired
  bounded baseline" with limits.
