# API Reference

Base path: `/api/v1`. All bodies and responses are JSON unless noted.
The SPA is served from `frontend/dist` when it exists. Client-side navigation
routes fall back to `index.html` so they continue to work on direct visits and
page refreshes; API routes and static assets retain their own responses.

## Endpoint table

| Method | Path | Purpose | Key fields |
|---|---|---|---|
| GET | `/api/v1/health` | Liveness | `status` |
| POST | `/api/v1/datasets/upload` | Upload and register a dataset | multipart `format`, `files[]` |
| GET | `/api/v1/datasets` | List datasets | `datasets[]` |
| GET | `/api/v1/datasets/{dataset_id}` | Dataset detail | `id`, `manifest_hash` |
| GET | `/api/v1/datasets/{dataset_id}/samples` | Paged samples | `samples[]`, `total` |
| GET | `/api/v1/datasets/{dataset_id}/image/{sample_id}` | Sample image bytes | PNG response |
| POST | `/api/v1/attacks/generate` | Inject synthetic attacks | `attack_types`, `dataset_id`; ground truth stored in `attack_manifests` |
| POST | `/api/v1/scans` | Run data-integrity scan | `dataset_id`, `outlier_percentile`; returns `scan_id`, `total_findings`, `by_severity` |
| GET | `/api/v1/scans/{scan_id}` | Scan summary | `scan_id`, `status`, per-module statuses |
| GET | `/api/v1/scans/{scan_id}/findings` | Findings for a scan | finding list (see below) |
| POST | `/api/v1/models/upload` | Register/upload a model | `model_id`, `manifest_ok`; `.pt`/`.pth` never unpickled |
| GET | `/api/v1/models` | List models | `models[]` |
| POST | `/api/v1/models/{model_id}/checks` | Run integrity checks | checks list (see below) |
| POST | `/api/v1/inference/predict` | Record an inference | `model_id`, inputs; appends provenance record |
| POST | `/api/v1/provenance/anchor` | Anchor a record | returns `record_id`, `record_hash` |
| GET | `/api/v1/provenance/chain` | Verify whole chain | `records[]`, `intact`, `broken_at` |
| POST | `/api/v1/provenance/verify` | Verify one record | `record_id`, `intact` |
| POST | `/api/v1/provenance/tamper-demo` | Controlled tamper demo | `record_id`, `before`, `after`, `note` |
| POST | `/api/v1/shift/assess` | Assess distribution shift | `dataset_id`; verdict + anomaly fraction + disclaimer |
| GET | `/api/v1/findings` | Query findings | filters; finding list |
| POST | `/api/v1/reports/generate` | Build assurance report | `experiment_id`; returns `report_id` |
| GET | `/api/v1/reports/{report_id}.json` | Report as JSON | full evidence bundle |
| GET | `/api/v1/reports/{report_id}.pdf` | Report as PDF | PDF download |
| POST | `/api/v1/evaluation/run` | Score vs ground truth | `scan_id`; `status: "evaluated"` with per-attack `methods` map, or `"Not evaluated yet"` |
| POST | `/api/v1/demo/run` | 15-step guided demo | `steps[]` each `{name, ok, ms, detail}`, `steps_ok`, `disposition` |

## Real JSON shapes

### Finding

```json
{
  "id": "f_9f2a...",
  "detection_method": "trigger_patch_heuristic",
  "evidence": { "percentile": 99, "score": 0.97, "sample_ids": ["s_001", "s_002"] },
  "disposition": "REVIEW"
}
```

`disposition` is one of `ACCEPT`, `REVIEW`, `QUARANTINE`. These are
recommendations — the report and UI state explicitly that reviewers override.

### Model check

```json
{ "check_name": "trigger_flip_rate", "status": "flag", "result": 0.97, "note": "candidate 0.97 vs reference 0.38" }
```

`status` is one of `pass`, `flag`, `unavailable`. `unavailable` is an honest
status (e.g. ONNX/`.pt` metadata-only checks), never silently skipped.

### Provenance record

```json
{ "record_id": "r_0007", "record_hash": "9f2a...", "prev_hash": "c41b...", "intact": true }
```

### Evaluation

```json
{ "scan_id": "scan_4e26c0ca9d67", "status": "evaluated",
  "methods": { "trigger_patch": { "precision": 0.889, "recall": 0.200, ... } } }
```

If no attack manifest exists for the scan, `status` is `"Not evaluated yet"`.

## Notes

- Error bodies use `{ "error": "<message>" }`.
- The demo endpoint is deterministic for a given seed; the shipped demo uses
  seed 42, n=600 (see [EVALUATION.md](EVALUATION.md)).
