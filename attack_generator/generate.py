"""Controlled synthetic attack/dataset generator for KavachAI.

All data is team-generated synthetic (numpy/Pillow). Every scenario stores
a ground-truth manifest:
  attack_id, attack_type, affected_samples, generation_parameters, ground_truth
Seeded → reproducible. Local only.
"""

from __future__ import annotations

import csv
import json
import shutil
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ml.common.utils import canonical_json, seeded_rng, utcnow

IMG_SIZE = 32
CLASSES = ["circle", "square", "triangle"]
TRIGGER_SIZE = 5
TRIGGER_POS = (IMG_SIZE - 6, IMG_SIZE - 6)  # top-left of 5x5 patch
TARGET_LABEL = "triangle"
CONTRIBUTORS = ["contrib_a", "contrib_b", "contrib_c", "contrib_d"]


# ---------------------------------------------------------------- shapes

def draw_shape(rng: np.random.Generator, shape: str) -> Image.Image:
    bg = rng.integers(8, 28, size=(IMG_SIZE, IMG_SIZE, 3)).astype(np.uint8)
    img = Image.fromarray(bg, "RGB")
    d = ImageDraw.Draw(img)
    color = tuple(int(c) for c in rng.integers(150, 256, size=3))
    cx = int(rng.integers(10, 23))
    cy = int(rng.integers(10, 23))
    r = int(rng.integers(6, 10))
    if shape == "circle":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    elif shape == "square":
        d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=color)
    else:  # triangle
        d.polygon([(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)],
                  fill=color)
    noise = rng.normal(0, 6, size=(IMG_SIZE, IMG_SIZE, 3))
    arr = np.clip(np.asarray(img).astype(np.float32) + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def add_trigger(img: Image.Image) -> Image.Image:
    out = img.copy()
    d = ImageDraw.Draw(out)
    x, y = TRIGGER_POS
    d.rectangle([x, y, x + TRIGGER_SIZE - 1, y + TRIGGER_SIZE - 1],
                fill=(255, 255, 255))
    return out


def draw_ood(rng: np.random.Generator) -> Image.Image:
    """Synthetic out-of-distribution sample: high-frequency noise texture."""
    arr = rng.integers(0, 256, size=(IMG_SIZE, IMG_SIZE, 3)).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


# ---------------------------------------------------------------- datasets

def _write_sample(img: Image.Image, path: Path) -> None:
    img.save(path, "PNG")


def make_clean_dataset(root: Path, seed: int, n: int,
                       name: str = "clean") -> dict:
    """Create a clean labeled dataset on disk. Returns dataset record."""
    rng = seeded_rng(seed)
    ds_id = f"ds_{uuid.uuid4().hex[:12]}"
    ds_dir = Path(root) / ds_id
    img_dir = ds_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(n):
        sid = f"s{i:06d}"
        label = CLASSES[i % len(CLASSES)]  # balanced
        contributor = CONTRIBUTORS[i % len(CONTRIBUTORS)]
        img = draw_shape(rng, label)
        rel = f"images/{sid}.png"
        _write_sample(img, ds_dir / rel)
        rows.append({"sample_id": sid, "rel_path": rel, "label": label,
                     "contributor_id": contributor})

    with open(ds_dir / "labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sample_id", "rel_path", "label",
                                          "contributor_id"])
        w.writeheader()
        w.writerows(rows)

    manifest = {
        "dataset_id": ds_id, "name": name, "seed": seed, "n": n,
        "classes": CLASSES, "synthetic": True,
        "trigger_spec": {"type": "patch_5x5_white",
                         "position": list(TRIGGER_POS),
                         "target_label": TARGET_LABEL},
        "created_at": utcnow(),
    }
    (ds_dir / "manifest.json").write_text(canonical_json(manifest))
    return {"dataset_id": ds_id, "dir": str(ds_dir), "manifest": manifest,
            "rows": rows}


def _load_rows(ds_dir: Path) -> list[dict]:
    with open(ds_dir / "labels.csv", newline="") as f:
        return list(csv.DictReader(f))


def _save_rows(ds_dir: Path, rows: list[dict]) -> None:
    with open(ds_dir / "labels.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sample_id", "rel_path", "label",
                                          "contributor_id"])
        w.writeheader()
        w.writerows(rows)


def _attack_manifest(attack_type: str, dataset_id: str, params: dict,
                     ground_truth: dict, affected: list) -> dict:
    return {
        "attack_id": f"atk_{uuid.uuid4().hex[:12]}",
        "attack_type": attack_type,
        "dataset_id": dataset_id,
        "affected_samples": affected,
        "generation_parameters": params,
        "ground_truth": ground_truth,
        "synthetic": True,
        "created_at": utcnow(),
    }


# ---------------------------------------------------------------- attacks

def apply_label_flip(ds_dir: Path, dataset_id: str, seed: int,
                     k: int) -> dict:
    rng = seeded_rng(seed)
    rows = _load_rows(ds_dir)
    # concentrate flips in contrib_c to demo contributor aggregation
    pool = [r for r in rows if r["contributor_id"] == "contrib_c"]
    chosen = rng.choice(len(pool), size=min(k, len(pool)), replace=False)
    gt, affected = {}, []
    for idx in chosen:
        r = pool[int(idx)]
        others = [c for c in CLASSES if c != r["label"]]
        new_label = str(rng.choice(others))
        gt[r["sample_id"]] = {"original_label": r["label"],
                              "new_label": new_label}
        r["label"] = new_label
        affected.append(r["sample_id"])
    _save_rows(ds_dir, rows)
    return _attack_manifest("label_flip", dataset_id,
                            {"seed": seed, "k": k,
                             "contributor": "contrib_c"}, gt, affected)


def apply_trigger_patch(ds_dir: Path, dataset_id: str, seed: int,
                        k: int) -> dict:
    rng = seeded_rng(seed + 1)
    rows = _load_rows(ds_dir)
    pool = [r for r in rows
            if r["label"] != TARGET_LABEL
            and r["contributor_id"] == "contrib_c"]
    chosen = rng.choice(len(pool), size=min(k, len(pool)), replace=False)
    gt, affected = {}, []
    for idx in chosen:
        r = pool[int(idx)]
        img = Image.open(ds_dir / r["rel_path"]).convert("RGB")
        _write_sample(add_trigger(img), ds_dir / r["rel_path"])
        gt[r["sample_id"]] = {"original_label": r["label"],
                              "target_label": TARGET_LABEL,
                              "trigger": "patch_5x5_white_bottom_right"}
        r["label"] = TARGET_LABEL
        affected.append(r["sample_id"])
    _save_rows(ds_dir, rows)
    return _attack_manifest("trigger_patch", dataset_id,
                            {"seed": seed, "k": k,
                             "trigger": "patch_5x5_white",
                             "position": list(TRIGGER_POS),
                             "target_label": TARGET_LABEL,
                             "contributor": "contrib_c"}, gt, affected)


def apply_near_duplicates(ds_dir: Path, dataset_id: str, seed: int,
                          k: int) -> dict:
    rng = seeded_rng(seed + 2)
    rows = _load_rows(ds_dir)
    existing = len(rows)
    groups, affected = [], []
    for j in range(k):
        src = rows[int(rng.integers(0, len(rows)))]
        group = [src["sample_id"]]
        for c in range(int(rng.integers(1, 3))):
            sid = f"s{existing:06d}"
            existing += 1
            img = Image.open(ds_dir / src["rel_path"]).convert("RGB")
            arr = np.asarray(img).astype(np.float32)
            jitter = float(rng.uniform(0.97, 1.03))  # ±3% brightness
            arr = np.clip(arr * jitter, 0, 255).astype(np.uint8)
            rel = f"images/{sid}.png"
            _write_sample(Image.fromarray(arr, "RGB"), ds_dir / rel)
            rows.append({"sample_id": sid, "rel_path": rel,
                         "label": src["label"],
                         "contributor_id": src["contributor_id"]})
            group.append(sid)
            affected.append(sid)
        groups.append(group)
    _save_rows(ds_dir, rows)
    return _attack_manifest("near_duplicate", dataset_id,
                            {"seed": seed, "k": k,
                             "jitter": "brightness ±3%"}, {"groups": groups},
                            affected)


def apply_ood(ds_dir: Path, dataset_id: str, seed: int, k: int) -> dict:
    rng = seeded_rng(seed + 3)
    rows = _load_rows(ds_dir)
    existing = len(rows)
    affected = []
    for j in range(k):
        sid = f"s{existing:06d}"
        existing += 1
        label = str(rng.choice(CLASSES))
        rel = f"images/{sid}.png"
        _write_sample(draw_ood(rng), ds_dir / rel)
        rows.append({"sample_id": sid, "rel_path": rel, "label": label,
                     "contributor_id": "contrib_d"})
        affected.append(sid)
    _save_rows(ds_dir, rows)
    return _attack_manifest(
        "ood", dataset_id, {"seed": seed, "k": k,
                            "description": "high-frequency noise textures"},
        {"sample_ids": affected,
         "note": "synthetic OOD; labels are arbitrary"}, affected)


def full_suite(root: Path, seed: int = 42, n: int = 600,
               k_flip: int = 30, k_trigger: int = 40, k_dup: int = 25,
               k_ood: int = 30) -> dict:
    """Clean dataset + all four attacks. Returns dataset + manifests."""
    info = make_clean_dataset(root, seed, n, name="poisoned_suite")
    ds_dir = Path(info["dir"])
    ds_id = info["dataset_id"]
    manifests = [
        apply_label_flip(ds_dir, ds_id, seed, k_flip),
        apply_trigger_patch(ds_dir, ds_id, seed, k_trigger),
        apply_near_duplicates(ds_dir, ds_id, seed, k_dup),
        apply_ood(ds_dir, ds_id, seed, k_ood),
    ]
    (ds_dir / "attacks.json").write_text(canonical_json(manifests))
    info["manifests"] = manifests
    return info


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "datasets/generated")
    info = full_suite(out, seed=42, n=600)
    print("dataset:", info["dataset_id"])
    for m in info["manifests"]:
        print(m["attack_type"], "->", len(m["affected_samples"]), "samples",
              m["attack_id"])
