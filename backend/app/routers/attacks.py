"""Attack generator: synthetic clean/poisoned datasets + ground truth."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from attack_generator.generate import (
    apply_label_flip,
    apply_near_duplicates,
    apply_ood,
    apply_trigger_patch,
    full_suite,
    make_clean_dataset,
)
from ml.common.utils import canonical_json, utcnow
from ml.data_integrity.ingest import IngestError, load_kavach

from .. import service
from ..schemas import AttackGenerateRequest

router = APIRouter(prefix="/api/v1/attacks", tags=["attacks"])

# Default attack counts are calibrated for n=600; scale with n.
_DEFAULT_K = {"label_flip": 30, "trigger_patch": 40,
              "near_duplicate": 25, "ood": 30}
_APPLIERS = {
    "label_flip": apply_label_flip,
    "trigger_patch": apply_trigger_patch,
    "near_duplicate": apply_near_duplicates,
    "ood": apply_ood,
}


def _scaled_k(scenario: str, n: int) -> int:
    return max(1, int(_DEFAULT_K[scenario] * n / 600))


def _persist_manifests(manifests: list[dict], dataset_id: str) -> None:
    c = service.con()
    for m in manifests:
        c.execute(
            "INSERT INTO attack_manifests (attack_id, attack_type, "
            "dataset_id, affected_samples_json, params_json, "
            "ground_truth_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (m["attack_id"], m["attack_type"], dataset_id,
             canonical_json(m["affected_samples"]),
             canonical_json(m.get("generation_parameters", {})),
             canonical_json(m.get("ground_truth", {})),
             m.get("created_at") or utcnow()),
        )
    c.commit()


def _persist_generated(ds_dir: Path, name: str, seed: int, n: int,
                       scenario: str) -> dict:
    try:
        rows, _meta = load_kavach(ds_dir)
    except IngestError as exc:
        raise HTTPException(500, f"generated dataset failed ingest: {exc}"
                            ) from exc
    return service.persist_dataset(
        name=name, source_format="kavach", root_dir=ds_dir, rows=rows,
        synthetic=True,
        params={"scenario": scenario, "seed": seed, "n": n})


@router.post("/generate")
def generate_attacks(req: AttackGenerateRequest):
    """Generate a synthetic dataset (clean or poisoned) with manifests.

    Returns {"dataset_id", "sample_count", "manifest_hash", "attack_id",
    "manifest"}. Ground-truth manifests persist for evaluation.
    """
    root = service.GENERATED_DIR
    root.mkdir(parents=True, exist_ok=True)
    seed, n = req.seed, req.n

    if req.scenario == "clean":
        name = f"clean_seed{seed}_n{n}"
        info = make_clean_dataset(root, seed, n, name=name)
        manifests: list[dict] = []
        attack_id = None
    elif req.scenario == "full_suite":
        name = f"poisoned_suite_seed{seed}_n{n}"
        # full_suite(root, seed, n, k_flip, k_trigger, k_dup, k_ood)
        info = full_suite(root, seed, n,
                          k_flip=_scaled_k("label_flip", n),
                          k_trigger=_scaled_k("trigger_patch", n),
                          k_dup=_scaled_k("near_duplicate", n),
                          k_ood=_scaled_k("ood", n))
        manifests = info["manifests"]
        attack_id = [m["attack_id"] for m in manifests]
    else:
        name = f"{req.scenario}_seed{seed}_n{n}"
        info = make_clean_dataset(root, seed, n, name=name)
        ds_dir = Path(info["dir"])
        manifest = _APPLIERS[req.scenario](ds_dir, info["dataset_id"], seed,
                                           _scaled_k(req.scenario, n))
        manifests = [manifest]
        attack_id = manifest["attack_id"]

    ds_dir = Path(info["dir"])
    ds = _persist_generated(ds_dir, name, seed, n, req.scenario)
    # manifests reference the generator's dataset id; re-point at persisted id
    for m in manifests:
        m["dataset_id"] = ds["id"]
    _persist_manifests(manifests, ds["id"])
    service.audit("attack.generate",
                  {"scenario": req.scenario, "seed": seed, "n": n,
                   "dataset_id": ds["id"], "attack_id": attack_id})
    return {"dataset_id": ds["id"], "sample_count": ds["sample_count"],
            "manifest_hash": ds["manifest_hash"],
            "attack_id": attack_id, "manifest": manifests}
