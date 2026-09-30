"""KavachAI Module 1 — Data integrity.

Public API:
  ingest: load_dataset / load_kavach / load_folder / load_csv / load_yolo /
          load_coco, IngestError
  scan:   run_scan(dataset, scan_id, params=None, seed=7) -> (findings, summary)

Implements docs/ml-methodology.md Module 1 exactly (methods, thresholds,
confidence definitions). Language contract: "Suspicious" / "Anomalous" /
"Requires review" — never an assertion of malicious intent.
"""

from .ingest import (
    IngestError,
    load_coco,
    load_csv,
    load_dataset,
    load_folder,
    load_kavach,
    load_yolo,
)
from .scan import DEFAULT_PARAMS, run_scan

__all__ = [
    "IngestError",
    "load_coco",
    "load_csv",
    "load_dataset",
    "load_folder",
    "load_kavach",
    "load_yolo",
    "DEFAULT_PARAMS",
    "run_scan",
]
