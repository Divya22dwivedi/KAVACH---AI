#!/usr/bin/env python3
"""Seed the KavachAI demo assets (idempotent-ish).

Generates the clean + full-suite poisoned datasets (seed=42, n=600) and
registers the pre-trained reference/candidate models. Re-runs reuse
existing datasets by name; model registration upserts on SHA-256.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app import db, service  # noqa: E402
from backend.app.routers import attacks  # noqa: E402
from backend.app.schemas import AttackGenerateRequest  # noqa: E402
from ml.model_integrity.registry import register_model  # noqa: E402

SEED = 42
N = 600


def dataset_exists(name: str) -> str | None:
    row = db.get_connection().execute(
        "SELECT id FROM datasets WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None


def main() -> None:
    db.init_db()
    service.con()  # ensure singleton

    out: dict[str, str] = {}

    clean_name = f"clean_seed{SEED}_n{N}"
    ds_id = dataset_exists(clean_name)
    if ds_id:
        print(f"clean dataset already seeded: {ds_id}")
    else:
        g = attacks.generate_attacks(
            AttackGenerateRequest(scenario="clean", seed=SEED, n=N))
        ds_id = g["dataset_id"]
        print(f"clean dataset: {ds_id} ({g['sample_count']} samples)")
    out["clean_dataset_id"] = ds_id

    poison_name = f"poisoned_suite_seed{SEED}_n{N}"
    ds_id = dataset_exists(poison_name)
    if ds_id:
        print(f"poisoned dataset already seeded: {ds_id}")
    else:
        g = attacks.generate_attacks(
            AttackGenerateRequest(scenario="full_suite", seed=SEED, n=N))
        ds_id = g["dataset_id"]
        print(f"poisoned dataset: {ds_id} ({g['sample_count']} samples)")
    out["poisoned_dataset_id"] = ds_id

    for fname, name, role in (("kavach_mlp_ref.pkl", "ref-v1", "reference"),
                             ("kavach_mlp_cand.pkl", "cand-v1", "candidate")):
        rec = register_model(REPO_ROOT / "models" / fname, name, role)
        row = service.persist_model(rec)
        print(f"model {role}: {row['id']} "
              f"(sha256 {row['sha256'][:16]}…, manifest_ok={row['manifest_ok']})")
        out[f"model_{role}_id"] = row["id"]

    print("\nseed_all done:")
    for k, v in out.items():
        print(f"  {k} = {v}")


if __name__ == "__main__":
    main()
