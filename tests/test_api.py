"""Phase 10 API tests — real operations end to end (small n, < 180 s)."""

from __future__ import annotations

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import db, service


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolate the DB per test module run.
    db.reset_connection()
    test_db = tmp_path / "test_kavach.db"
    db.get_connection(path=str(test_db))
    monkeypatch.setattr(service, "GENERATED_DIR", tmp_path / "generated")
    monkeypatch.setattr(service, "UPLOADED_DIR", tmp_path / "uploaded")
    monkeypatch.setattr(service, "FEATURES_DIR", tmp_path / "features")
    monkeypatch.setattr(service, "UPLOADED_MODELS_DIR",
                        tmp_path / "models")
    monkeypatch.setattr(service, "REPORTS_DIR", tmp_path / "reports")
    for d in ("generated", "uploaded", "features", "models", "reports"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    from backend.app.main import app
    with TestClient(app) as c:
        yield c
    db.reset_connection()


def _gen(client, scenario="clean", seed=11, n=60):
    r = client.post("/api/v1/attacks/generate",
                    json={"scenario": scenario, "seed": seed, "n": n})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(("dataset_id", "sample_count", "manifest_hash")) <= set(body)
    assert body["sample_count"] == n
    return body


def _scan(client, dataset_id):
    r = client.post("/api/v1/scans", json={"dataset_id": dataset_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(("scan_id", "experiment_id", "summary", "status")) <= set(body)
    return body


def _upload_model(client, fname, role):
    with open(f"models/{fname}", "rb") as f:
        raw = f.read()
    r = client.post("/api/v1/models/upload",
                    files={"file": (fname, raw, "application/octet-stream")},
                    data={"role": role})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(("id", "name", "format", "sha256", "size_bytes", "metadata",
                "manifest_ok", "role", "created_at")) <= set(body)
    return body


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["offline"] is True


def test_attacks_generate_and_scan_findings(client):
    g = _gen(client)
    s = _scan(client, g["dataset_id"])
    r = client.get(f"/api/v1/scans/{s['scan_id']}")
    assert r.status_code == 200
    assert set(("scan_id", "status", "summary", "params")) <= set(r.json())
    r = client.get(f"/api/v1/scans/{s['scan_id']}/findings")
    assert r.status_code == 200
    findings = r.json()
    assert isinstance(findings, list) and findings
    f0 = findings[0]
    assert set(("id", "scan_id", "category", "asset_id", "title",
                "detection_method", "evidence", "confidence", "severity",
                "disposition", "supported_attack_class", "limitations",
                "reviewer_note", "created_at")) <= set(f0)
    assert isinstance(f0["evidence"], dict)
    assert f0["disposition"] in ("ACCEPT", "REVIEW", "QUARANTINE")


def test_dataset_samples_and_image(client):
    g = _gen(client, seed=12)
    r = client.get(f"/api/v1/datasets/{g['dataset_id']}/samples?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"samples", "total"}
    assert body["total"] == 60
    s0 = body["samples"][0]
    assert set(s0) == {"sample_id", "rel_path", "label", "contributor_id",
                       "sha256", "dhash"}
    r = client.get(
        f"/api/v1/datasets/{g['dataset_id']}/image/{s0['sample_id']}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_models_upload_and_checks(client):
    g = _gen(client, seed=13)
    ref = _upload_model(client, "kavach_mlp_ref.pkl", "reference")
    cand = _upload_model(client, "kavach_mlp_cand.pkl", "candidate")
    assert ref["manifest_ok"] == 1
    r = client.post(
        f"/api/v1/models/{cand['id']}/checks",
        json={"reference_model_id": ref["id"],
              "probe_dataset_id": g["dataset_id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"model_id", "checks"}
    assert body["model_id"] == cand["id"]
    by_name = {c["check_name"]: c for c in body["checks"]}
    assert "trigger_test" in by_name
    for c in body["checks"]:
        assert set(c) == {"check_name", "status", "result", "note"}
        assert c["status"] in ("pass", "flag", "unavailable")
        assert isinstance(c["result"], dict)


def _b64_png() -> str:
    img = Image.new("RGB", (32, 32), (10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_inference_provenance_and_tamper(client):
    cand = _upload_model(client, "kavach_mlp_cand.pkl", "candidate")
    n0 = len(client.get("/api/v1/provenance/chain").json())
    r = client.post("/api/v1/inference/predict",
                    json={"model_id": cand["id"],
                          "image_base64": _b64_png(), "config": {}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"record_id", "output", "record_hash"}
    assert set(body["output"]) == {"label", "probabilities"}
    chain = client.get("/api/v1/provenance/chain").json()
    assert isinstance(chain, list)
    assert len(chain) == n0 + 1
    rec = chain[-1]
    assert set(("seq", "record_id", "input_hash", "model_hash", "config_hash",
                "model_version", "output_json", "output_hash", "created_at",
                "prev_hash", "record_hash")) <= set(rec)

    r = client.post("/api/v1/provenance/tamper-demo",
                    json={"record_id": body["record_id"]})
    assert r.status_code == 200, r.text
    tb = r.json()
    assert set(tb) == {"record_id", "before_output_hash",
                       "after_output_hash", "note"}
    v = client.post("/api/v1/provenance/verify").json()
    assert set(("intact", "checked", "broken_at", "expected_hash",
                "actual_hash", "tip_hash")) <= set(v)
    assert v["intact"] is False
    assert v["broken_at"] == body["record_id"]


def test_shift_assess_clean_vs_clean(client):
    # Same clean dataset as reference and current: identical distribution ->
    # honestly NORMAL (validates the endpoint + verdict plumbing).
    a = _gen(client, seed=21)
    r = client.post("/api/v1/shift/assess",
                    json={"reference_dataset_id": a["dataset_id"],
                          "current_dataset_id": a["dataset_id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "NORMAL"
    assert set(body) == {"verdict", "metrics", "per_sample", "disclaimer"}
    assert set(body["metrics"]) == {"anomaly_fraction", "q95_threshold",
                                    "q99_threshold", "mean_distance",
                                    "quality_deltas", "distance_histogram"}
    hist = body["metrics"]["distance_histogram"]
    assert len(hist["bins"]) == 21 and len(hist["counts"]) == 20
    assert body["per_sample"]


def test_reports_generate_json_pdf(client):
    g = _gen(client, seed=31)
    s = _scan(client, g["dataset_id"])
    r = client.post("/api/v1/reports/generate",
                    json={"experiment_id": s["experiment_id"]})
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"report_id"}
    rid = r.json()["report_id"]
    r = client.get(f"/api/v1/reports/{rid}.json")
    assert r.status_code == 200
    report = r.json()
    assert len(report) == 18  # experiment_id + 17 sections
    r = client.get(f"/api/v1/reports/{rid}.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_evaluation_not_evaluated_and_evaluated(client):
    g = _gen(client, seed=41)  # clean: no attack manifest
    s = _scan(client, g["dataset_id"])
    r = client.get(f"/api/v1/evaluation/{s['scan_id']}")
    assert r.status_code == 200
    assert r.json() == {"status": "Not evaluated yet"}

    g2 = _gen(client, scenario="trigger_patch", seed=42)
    s2 = _scan(client, g2["dataset_id"])
    r = client.get(f"/api/v1/evaluation/{s2['scan_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "evaluated"
    assert "trigger_patch" in body["methods"]
    m = body["methods"]["trigger_patch"]
    assert set(m) == {"precision", "recall", "f1", "fpr", "confusion"}
    assert set(m["confusion"]) == {"tp", "fp", "tn", "fn"}


def test_findings_filter_and_review(client):
    g = _gen(client, seed=51)
    _scan(client, g["dataset_id"])
    r = client.get("/api/v1/findings")
    assert r.status_code == 200
    findings = r.json()
    assert isinstance(findings, list) and findings
    fid = findings[0]["id"]
    r = client.patch(f"/api/v1/findings/{fid}",
                     json={"disposition": "ACCEPT",
                           "reviewer_note": "reviewed in test"})
    assert r.status_code == 200
    assert r.json()["disposition"] == "ACCEPT"
    assert r.json()["reviewer_note"] == "reviewed in test"
    r = client.get("/api/v1/findings?disposition=ACCEPT")
    assert any(f["id"] == fid for f in r.json())


def test_invalid_uploads_rejected(client):
    # path traversal in filename
    r = client.post(
        "/api/v1/datasets/upload",
        files={"files": ("../evil.png", b"\x89PNG\r\n\x1a\nxxxx",
                         "image/png")},
        data={"format": "folder"})
    assert r.status_code == 400, r.text

    # oversized upload (cap lowered via monkeypatch to avoid a 50 MB body)
    import backend.app.security as sec_mod
    orig = sec_mod.MAX_UPLOAD_BYTES
    sec_mod.MAX_UPLOAD_BYTES = 10
    try:
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, format="PNG")
        r = client.post(
            "/api/v1/datasets/upload",
            files={"files": ("ok.png", buf.getvalue(), "image/png")},
            data={"format": "folder"})
    finally:
        sec_mod.MAX_UPLOAD_BYTES = orig
    assert r.status_code == 400, r.text

    # unsupported model format
    r = client.post(
        "/api/v1/models/upload",
        files={"file": ("model.exe", b"MZ" + b"x" * 100,
                        "application/octet-stream")},
        data={"role": "candidate"})
    assert r.status_code == 400, r.text


def test_model_upload_attacker_manifest_never_executes(client, tmp_path):
    """Regression: a user-supplied manifest must not authorize a pickle.

    An attacker uploads evil.pkl plus a self-made manifest whose sha256
    matches the payload. The server must still mark manifest_ok=0 and must
    never unpickle the payload (marker file must not appear).
    """
    import hashlib
    import pickle

    marker = tmp_path / "pwned.txt"

    class Evil:
        def __reduce__(self):
            import os
            return (os.system, (f"touch {marker}",))

    payload = pickle.dumps(Evil())
    digest = hashlib.sha256(payload).hexdigest()
    fake_manifest = (
        '{"sha256": "%s", "metadata": {}, "generator": "attacker"}' % digest
    )
    # The endpoint no longer accepts a manifest part: the extra part is
    # ignored and the pickle is untrusted (manifest_ok=0, never executed).
    r = client.post(
        "/api/v1/models/upload",
        files={"file": ("evil.pkl", payload, "application/octet-stream"),
               "manifest": ("evil.pkl.manifest.json", fake_manifest,
                            "application/json")},
        data={"role": "candidate"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["manifest_ok"] == 0
    assert body["metadata"]["executable"] is False
    assert "execution refused" in body["metadata"]["error"]
    assert not marker.exists(), "attacker pickle was executed!"
