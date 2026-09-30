"""One-click demo: the 15-step KavachAI walkthrough (DATA -> MODEL ->
INFERENCE), executed server-side. Every step performs a REAL operation via
the ml/ modules; every number is measured in this run.
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter

from attack_generator.generate import add_trigger
from ml.model_integrity.registry import register_model
from ml.provenance.chain import get_chain, reset_chain

from .. import assurance, service
from ..schemas import (
    AttackGenerateRequest,
    DemoRequest,
    ModelCheckRequest,
    PredictRequest,
    ReportRequest,
    ScanRequest,
    ShiftRequest,
)
from . import attacks, inference, models, provenance, reports, scans, shift

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

REPO_MODELS = service.REPO_ROOT / "models"
DEMO_N = 600


def _timed(steps: list[dict], name: str, fn) -> dict:
    t0 = time.perf_counter()
    try:
        detail = fn() or {}
        ok, ms = True, int((time.perf_counter() - t0) * 1000)
    except Exception as exc:  # noqa: BLE001 - demo must record, not crash
        detail, ok = {"error": f"{type(exc).__name__}: {exc}"}, False
        ms = int((time.perf_counter() - t0) * 1000)
    rec = {"name": name, "ok": ok, "ms": ms, "detail": detail}
    steps.append(rec)
    if not ok:
        raise _StepFailed(rec)
    return detail


class _StepFailed(Exception):
    def __init__(self, step: dict):
        super().__init__(f"demo step failed: {step['name']}: "
                         f"{step['detail'].get('error')}")
        self.step = step


def run_demo(seed: int = 42) -> dict:
    """Execute the 15-step demo synchronously. Returns the API response."""
    steps: list[dict] = []
    state: dict = {}
    experiment_id = service.new_id("exp")
    report_id: str | None = None

    # Clean ledger for a reproducible demo narrative.
    reset_chain(service.con())

    def s1():
        g = attacks.generate_attacks(
            AttackGenerateRequest(scenario="clean", seed=seed, n=DEMO_N))
        state["clean_id"] = g["dataset_id"]
        return {"dataset_id": g["dataset_id"],
                "sample_count": g["sample_count"],
                "manifest_hash": g["manifest_hash"][:16]}

    def s2():
        g = attacks.generate_attacks(
            AttackGenerateRequest(scenario="full_suite", seed=seed, n=DEMO_N))
        state["poison_id"] = g["dataset_id"]
        return {"dataset_id": g["dataset_id"],
                "attack_types": [m["attack_type"] for m in g["manifest"]]}

    def s3():
        # Documented calibrated operating point (docs/ml-methodology.md):
        # the 99th-percentile default targets low poison rates; the demo
        # suite carries a higher poison rate, so we use the calibrated
        # 85th-percentile point. The value is stored in the scan params
        # and reported — never hidden.
        s = scans.create_scan(ScanRequest(dataset_id=state["poison_id"],
                                          experiment_id=experiment_id,
                                          params={"outlier_percentile": 85}))
        state["scan_id"] = s["scan_id"]
        return {"scan_id": s["scan_id"],
                "total_findings": s["summary"]["total_findings"],
                "outlier_percentile": 85}

    def s4():
        f = scans.scan_findings(state["scan_id"])
        by_sev: dict[str, int] = {}
        for x in f:
            by_sev[x["severity"]] = by_sev.get(x["severity"], 0) + 1
        return {"n_findings": len(f), "by_severity": by_sev}

    def _register(fname: str, name: str, role: str) -> dict:
        rec = register_model(REPO_MODELS / fname, name, role)
        row = service.persist_model(rec)
        return {"model_id": row["id"], "sha256": row["sha256"][:16],
                "manifest_ok": row["manifest_ok"]}

    def s5():
        d = _register("kavach_mlp_ref.pkl", "ref-v1", "reference")
        state["ref_id"] = d["model_id"]
        return d

    def s6():
        d = _register("kavach_mlp_cand.pkl", "cand-v1", "candidate")
        state["cand_id"] = d["model_id"]
        return d

    def s7():
        r = models.run_model_checks(
            state["cand_id"],
            ModelCheckRequest(reference_model_id=state["ref_id"],
                              probe_dataset_id=state["clean_id"]))
        flags = {c["check_name"]: c["status"] for c in r["checks"]}
        trig = next((c for c in r["checks"]
                     if c["check_name"] == "trigger_test"), {})
        state["trigger_test"] = trig.get("result", {})
        return {"checks": flags}

    def _predict_b64(img) -> dict:
        return inference.predict(PredictRequest(
            model_id=state["cand_id"],
            image_base64=service.image_to_base64_png(img), config={}))

    def s8():
        # Four legitimate inference records: clean/triggered for two images.
        # Record 3 (the second clean prediction) is tampered in step 10 to
        # demonstrate exact broken-link detection mid-chain.
        imgs = service.dataset_images(state["clean_id"], limit=2)
        rids, outs = [], []
        for _sid, img, _lab in imgs:
            for variant in ("clean", "triggered"):
                out = _predict_b64(img if variant == "clean" else add_trigger(img))
                rids.append(out["record_id"])
                outs.append((variant, out["output"]["label"]))
        state["rec_ids"] = rids
        return {"records": rids,
                "predictions": [{"variant": v, "label": lb} for v, lb in outs]}

    def s9():
        chain = get_chain(service.con())
        return {"records": len(chain),
                "tip": (chain[-1]["record_hash"][:16] if chain else None)}

    def s10():
        # Tamper the THIRD of the four records (mid-chain).
        r = provenance.tamper({"record_id": state["rec_ids"][2]})
        return {"record_id": r["record_id"],
                "tampered_index": 3,
                "before": r["before_output_hash"][:16],
                "after": r["after_output_hash"][:16],
                "note": r["note"]}

    def s11():
        v = provenance.verify()
        state["verify"] = v
        return {"intact": v["intact"], "checked": v["checked"]}

    def s12():
        v = state["verify"]
        return {"broken_at": v["broken_at"],
                "expected_hash": (v["expected_hash"] or "")[:16],
                "actual_hash": (v["actual_hash"] or "")[:16]}

    def s13():
        r = shift.assess_shift(ShiftRequest(
            reference_dataset_id=state["clean_id"],
            current_dataset_id=state["poison_id"]))
        return {"verdict": r["verdict"],
                "anomaly_fraction": r["metrics"]["anomaly_fraction"]}

    def s14():
        assurance.synthesize_module_findings(state["scan_id"])
        agg = assurance.aggregate_all(state["scan_id"])
        return {"recommended_disposition":
                agg["recommended_disposition"],
                "per_module": {m: v["status"]
                               for m, v in agg["per_module"].items()},
                "total_findings": agg["total_findings"]}

    def s15():
        nonlocal report_id
        r = reports.generate_report(experiment_id)
        report_id = r["report_id"]
        pdf_ok = Path(r["pdf_path"]).is_file()
        return {"report_id": report_id, "pdf_path": r["pdf_path"],
                "pdf_exists": pdf_ok}

    names = [
        "1. Load clean dataset (600 synthetic shapes)",
        "2. Generate controlled poison (full attack suite)",
        "3. Scan poisoned dataset (data integrity)",
        "4. Findings summary",
        "5. Register reference model (ref-v1)",
        "6. Register candidate model (cand-v1)",
        "7. Run model integrity checks (ref vs candidate)",
        "8. Inference: clean + triggered sample",
        "9. Provenance ledger records",
        "10. Tamper demo (synthetic, labeled)",
        "11. Verify provenance chain",
        "12. Detect broken chain",
        "13. Distribution shift assessment (clean vs poisoned)",
        "14. Aggregate evidence (ladder rule)",
        "15. Generate assurance report (JSON + PDF)",
    ]
    fns = [s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13, s14, s15]
    try:
        for name, fn in zip(names, fns):
            _timed(steps, name, fn)
    except _StepFailed:
        pass

    service.audit("demo.run",
                  {"experiment_id": experiment_id, "seed": seed,
                   "steps_ok": sum(1 for s in steps if s["ok"]),
                   "report_id": report_id})
    return {
        "experiment_id": experiment_id,
        "steps": steps,
        "report_id": report_id,
        "pdf_url": (f"/api/v1/reports/{report_id}.pdf"
                    if report_id else None),
    }


@router.post("/run")
def demo_run(req: DemoRequest):
    return run_demo(seed=req.seed)
