"""Phase-8 tests: evidence aggregation + 17-section report + PDF renderer."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.evidence import (  # noqa: E402
    aggregate,
    build_report,
    make_finding,
    next_id,
    render_report_pdf,
)
from ml.evidence.report import SECTION_KEYS  # noqa: E402


def _finding(fid, severity, category="data", confidence=0.9):
    return make_finding(
        finding_id=fid,
        category=category,
        asset_id="sample-001",
        title=f"Test finding {fid}",
        detection_method="test-detector",
        evidence={"metric": 0.5},
        confidence=confidence,
        severity=severity,
        disposition="REVIEW",
        supported_attack_class=None,
        limitations="Test limitation.",
    )


def _demo_report():
    findings = [
        _finding("F-0001", "critical", category="model", confidence=0.99),
        _finding("F-0002", "medium", category="data", confidence=0.70),
        _finding("F-0003", "low", category="provenance", confidence=0.55),
    ]
    agg = aggregate(findings)
    return build_report(
        "EXP-DEMO-001",
        dataset_info={"name": "demo-ds", "sample_count": 120, "manifest_hash": "abc123"},
        model_info={"name": "demo-model", "format": "sklearn", "sha256": "def456"},
        findings=findings,
        aggregation=agg,
        provenance_status={"intact": True, "records": 3},
        shift_result={"verdict": "NORMAL", "anomaly_fraction": 0.02},
        limitations_extra=["Demo extra limitation."],
    )


# (a) severity ladder ----------------------------------------------------
@pytest.mark.parametrize(
    "severities,expected",
    [
        (["critical"], "QUARANTINE"),
        (["critical", "low"], "QUARANTINE"),
        (["high"], "QUARANTINE"),
        (["high", "medium", "low"], "QUARANTINE"),
        (["medium"], "REVIEW"),
        (["medium", "low", "info"], "REVIEW"),
        (["low"], "REVIEW"),
        (["low", "info"], "REVIEW"),
        (["info"], "ACCEPT"),
        ([], "ACCEPT"),
    ],
)
def test_ladder(severities, expected):
    findings = [_finding(f"F-{i + 1:04d}", s) for i, s in enumerate(severities)]
    result = aggregate(findings)
    assert result["recommended_disposition"] == expected


def test_ladder_rules_applied_strings():
    result = aggregate([_finding("F-0001", "critical")])
    joined = " ".join(result["rules_applied"])
    assert "QUARANTINE" in joined
    assert "Rule 1" in joined

    clean = aggregate([])
    joined_clean = " ".join(clean["rules_applied"])
    assert "ACCEPT" in joined_clean


# (b) per-module roll-up --------------------------------------------------
def test_per_module_rollup():
    findings = [
        _finding("F-0001", "low", category="data"),
        _finding("F-0002", "medium", category="model"),
        _finding("F-0003", "high", category="provenance"),
        # shift has no findings -> OK
    ]
    result = aggregate(findings)
    pm = result["per_module"]
    assert set(pm.keys()) == {"data", "model", "provenance", "shift"}
    assert pm["data"]["status"] == "REVIEW"      # worst = low
    assert pm["model"]["status"] == "REVIEW"     # worst = medium
    assert pm["provenance"]["status"] == "QUARANTINE"  # worst = high
    assert pm["shift"]["status"] == "OK"         # no findings
    assert pm["data"]["counts"]["low"] == 1
    assert result["severity_counts"] == {
        "info": 0, "low": 1, "medium": 1, "high": 1, "critical": 0,
    }


# (c) confidences never averaged ------------------------------------------
def test_confidences_not_averaged():
    findings = [_finding("F-0001", "medium", confidence=0.10),
                _finding("F-0002", "medium", confidence=0.90)]
    result = aggregate(findings)

    def _scan(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert "mean" not in k.lower() and "average" not in k.lower(), k
                _scan(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                _scan(v)

    _scan(result)


# findings factory validation ----------------------------------------------
def test_make_finding_validation():
    with pytest.raises(ValueError):
        _finding("BAD", "medium")  # bad id format
    with pytest.raises(ValueError):
        _finding("F-0001", "severe")  # bad severity
    with pytest.raises(ValueError):
        make_finding(
            "F-0001", "data", "a", "t", "m", {}, 1.5, "low", "REVIEW",
            None, "lim",
        )  # confidence out of range
    with pytest.raises(ValueError):
        make_finding(
            "F-0001", "data", "a", "t", "m", {}, 0.5, "low", "REVIEW",
            None, "",
        )  # empty limitations

    f = _finding("F-0007", "info")
    assert f["id"] == "F-0007"
    assert f["supported_attack_class"] is None


def test_next_id():
    assert next_id([]) == "F-0001"
    assert next_id(["F-0001", "F-0003"]) == "F-0004"
    assert next_id(iter(["F-0010"])) == "F-0011"


# (d) 17 sections -----------------------------------------------------------
def test_report_has_all_17_sections():
    report = _demo_report()
    assert list(report.keys()) == ["experiment_id", *SECTION_KEYS]
    assert len(SECTION_KEYS) == 17
    assert report["recommended_disposition"] == "QUARANTINE"
    assert report["model_hash"] == "def456"
    assert report["dataset_hash"] == "abc123"


# (e) empty provenance/shift -> "Not evaluated yet" -------------------------
def test_empty_sections_render_not_evaluated_yet():
    findings = [_finding("F-0001", "low")]
    agg = aggregate(findings)
    report = build_report("EXP-EMPTY", findings=findings, aggregation=agg)
    assert report["provenance_verification"] == "Not evaluated yet"
    assert report["distribution_shift"] == "Not evaluated yet"
    assert report["reproducibility"].startswith("Not evaluated yet")
    assert report["model_hash"] == "Not evaluated yet"
    assert report["dataset_hash"] == "Not evaluated yet"
    assert report["model_information"] == "Not evaluated yet"


# (g) unsupported tests defaults ----------------------------------------------
def test_unsupported_tests_defaults():
    report = _demo_report()
    joined = " ".join(report["unsupported_tests"])
    assert "Black-box trigger reconstruction was not performed because model weights/gradients were unavailable." in joined
    assert "Trigger reconstruction for uploaded ONNX/PyTorch artifacts was not performed (metadata-only ingestion)." in joined


# (f) PDF rendering ------------------------------------------------------------
def test_pdf_renders(tmp_path):
    report = _demo_report()
    out = tmp_path / "report.pdf"
    result = render_report_pdf(report, out)
    assert Path(result).exists()
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 5 * 1024, f"PDF too small: {len(data)} bytes"
