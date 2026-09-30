"""Phase 8 — evidence + report engine.

Finding factory, rule-based aggregation (docs/ml-methodology.md Module 5),
the 17-section assurance report builder, and the ReportLab PDF renderer.
"""

from ml.evidence.aggregate import aggregate
from ml.evidence.findings import make_finding, next_id
from ml.evidence.pdf import render_report_pdf
from ml.evidence.report import build_report

__all__ = [
    "aggregate",
    "build_report",
    "make_finding",
    "next_id",
    "render_report_pdf",
]
