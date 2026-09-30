"""Dataset ingestion for the Data Integrity module (Module 1).

Supported layouts (all offline, all validated):
  - ``kavach``: native KavachAI dir — ``images/`` + ``labels.csv`` +
    ``manifest.json``
  - ``folder``: plain image folder; each immediate subdirectory is a class
    label
  - ``csv``:    CSV manifest with columns ``rel_path,label`` (+ optional
    ``contributor_id``, ``sample_id``); paths resolve against the CSV's
    parent dir
  - ``yolo``:   ``images/`` + ``labels/*.txt`` + ``classes.txt`` (Ultralytics
    layout); label = majority class in the .txt file
  - ``coco``:   COCO annotations JSON (``images``/``annotations``/
    ``categories``); images expected in ``<json-parent>/images/``
    (overridable)

Every loader returns ``(rows, meta)`` where each row is::

    {"sample_id": str, "abs_path": str, "label": str | None,
     "contributor_id": str | None}

Security (no exceptions):
  - every relative path goes through
    ``backend.app.security.assert_safe_relpath`` (rejects ``..`` / absolute)
    plus a resolved-path containment check against the dataset root;
  - every file passes the ``is_image_bytes`` magic-byte check before use.

``load_dataset(path, layout="auto")`` auto-detects the layout.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from backend.app.security import assert_safe_relpath, is_image_bytes


class IngestError(ValueError):
    """Raised when a dataset cannot be ingested safely."""


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff",
              ".gif"}

# ---------------------------------------------------------------------------
# validation helpers


def _safe_join(root: Path, rel: str) -> Path:
    """Join ``rel`` onto ``root``; reject traversal / escape. Returns abs path."""
    rel = assert_safe_relpath(rel)  # raises ValueError on ".." / absolute
    root_r = root.resolve()
    p = (root_r / rel).resolve()
    if p != root_r and root_r not in p.parents:
        raise IngestError(f"path escapes dataset root: {rel!r}")
    return p


def _check_image(path: Path) -> None:
    if not path.is_file():
        raise IngestError(f"image file not found: {path}")
    with open(path, "rb") as f:
        head = f.read(16)
    if not is_image_bytes(head):
        raise IngestError(f"not an image (magic-byte check failed): {path}")


def _check_rows(rows: list[dict]) -> list[dict]:
    """Dedupe-check sample_ids; normalise optional fields."""
    seen: set[str] = set()
    for r in rows:
        sid = r.get("sample_id")
        if not sid:
            raise IngestError("row missing sample_id")
        if sid in seen:
            raise IngestError(f"duplicate sample_id: {sid!r}")
        seen.add(sid)
        r.setdefault("label", None)
        r.setdefault("contributor_id", None)
        r["abs_path"] = str(r["abs_path"])
    if not rows:
        raise IngestError("no usable image rows found")
    return rows


# ---------------------------------------------------------------------------
# loaders


def load_kavach(ds_dir: str | Path) -> tuple[list[dict], dict]:
    """Native KavachAI dataset: images/ + labels.csv + manifest.json."""
    ds = Path(ds_dir)
    manifest_path = ds / "manifest.json"
    labels_path = ds / "labels.csv"
    if not manifest_path.is_file():
        raise IngestError(f"manifest.json not found in {ds}")
    if not labels_path.is_file():
        raise IngestError(f"labels.csv not found in {ds}")
    manifest = json.loads(manifest_path.read_text())
    rows: list[dict] = []
    with open(labels_path, newline="") as f:
        reader = csv.DictReader(f)
        need = {"sample_id", "rel_path", "label"}
        if not need.issubset(set(reader.fieldnames or [])):
            raise IngestError(
                f"labels.csv missing columns {sorted(need)}; "
                f"got {reader.fieldnames}")
        for rec in reader:
            abs_path = _safe_join(ds, rec["rel_path"])
            _check_image(abs_path)
            rows.append({
                "sample_id": rec["sample_id"],
                "abs_path": abs_path,
                "label": rec["label"] or None,
                "contributor_id": rec.get("contributor_id") or None,
            })
    meta = {"layout": "kavach", "root": str(ds), "manifest": manifest}
    return _check_rows(rows), meta


def load_folder(root: str | Path) -> tuple[list[dict], dict]:
    """Plain image folder: each immediate subdirectory is a class label."""
    root = Path(root)
    if not root.is_dir():
        raise IngestError(f"not a directory: {root}")
    rows: list[dict] = []
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        label = sub.name
        for img in sorted(sub.rglob("*")):
            if not img.is_file() or img.suffix.lower() not in IMAGE_EXTS:
                continue
            _check_image(img)
            rows.append({
                "sample_id": f"{label}/{img.stem}",
                "abs_path": img.resolve(),
                "label": label,
                "contributor_id": None,
            })
    meta = {"layout": "folder", "root": str(root), "manifest": None}
    return _check_rows(rows), meta


def load_csv(manifest_path: str | Path) -> tuple[list[dict], dict]:
    """CSV manifest: columns rel_path,label[,contributor_id][,sample_id]."""
    mp = Path(manifest_path)
    if not mp.is_file():
        raise IngestError(f"CSV manifest not found: {mp}")
    base = mp.parent
    rows: list[dict] = []
    with open(mp, newline="") as f:
        reader = csv.DictReader(f)
        need = {"rel_path", "label"}
        if not need.issubset(set(reader.fieldnames or [])):
            raise IngestError(
                f"CSV missing columns {sorted(need)}; got {reader.fieldnames}")
        for rec in reader:
            rel = (rec.get("rel_path") or "").strip()
            if not rel:
                raise IngestError("CSV row with empty rel_path")
            abs_path = _safe_join(base, rel)  # raises on traversal
            _check_image(abs_path)
            rows.append({
                "sample_id": (rec.get("sample_id") or "").strip()
                             or Path(rel).stem,
                "abs_path": abs_path,
                "label": (rec.get("label") or "").strip() or None,
                "contributor_id": (rec.get("contributor_id") or "").strip()
                                  or None,
            })
    meta = {"layout": "csv", "root": str(base), "manifest": None}
    return _check_rows(rows), meta


def load_yolo(root: str | Path) -> tuple[list[dict], dict]:
    """YOLO layout: images/ + labels/*.txt + classes.txt (simple but real)."""
    root = Path(root)
    img_dir, lab_dir = root / "images", root / "labels"
    cls_path = root / "classes.txt"
    if not img_dir.is_dir():
        raise IngestError(f"YOLO images/ dir not found in {root}")
    if not cls_path.is_file():
        raise IngestError(f"YOLO classes.txt not found in {root}")
    classes = [c.strip() for c in cls_path.read_text().splitlines()
               if c.strip()]
    rows: list[dict] = []
    for img in sorted(img_dir.iterdir()):
        if not img.is_file() or img.suffix.lower() not in IMAGE_EXTS:
            continue
        _check_image(img)
        label: Optional[str] = None
        lab_file = lab_dir / f"{img.stem}.txt"
        if lab_file.is_file():
            votes: dict[int, int] = {}
            for line in lab_file.read_text().splitlines():
                parts = line.split()
                if not parts:
                    continue
                try:
                    ci = int(float(parts[0]))
                except ValueError:
                    continue
                votes[ci] = votes.get(ci, 0) + 1
            if votes:
                best = max(votes, key=lambda k: votes[k])
                label = classes[best] if 0 <= best < len(classes) else None
        rows.append({
            "sample_id": img.stem,
            "abs_path": img.resolve(),
            "label": label,
            "contributor_id": None,
        })
    meta = {"layout": "yolo", "root": str(root), "manifest": None,
            "classes": classes}
    return _check_rows(rows), meta


def load_coco(ann_path: str | Path,
              image_dir: Optional[str | Path] = None) -> tuple[list[dict], dict]:
    """COCO annotations JSON. Label = majority category per image."""
    ap = Path(ann_path)
    if not ap.is_file():
        raise IngestError(f"COCO annotations not found: {ap}")
    data = json.loads(ap.read_text())
    if not all(k in data for k in ("images", "annotations", "categories")):
        raise IngestError("not a COCO annotations file "
                          "(need images/annotations/categories)")
    img_dir = Path(image_dir) if image_dir else ap.parent / "images"
    cat_name = {c["id"]: c["name"] for c in data["categories"]}
    votes: dict = {}
    for ann in data["annotations"]:
        votes.setdefault(ann["image_id"], {}).setdefault(
            ann["category_id"], 0)
        votes[ann["image_id"]][ann["category_id"]] += 1
    rows: list[dict] = []
    for im in data["images"]:
        abs_path = _safe_join(img_dir, im["file_name"])
        _check_image(abs_path)
        v = votes.get(im["id"], {})
        label = cat_name.get(max(v, key=lambda k: v[k])) if v else None
        rows.append({
            "sample_id": str(im.get("id", Path(im["file_name"]).stem)),
            "abs_path": abs_path,
            "label": label,
            "contributor_id": None,
        })
    meta = {"layout": "coco", "root": str(img_dir), "manifest": None}
    return _check_rows(rows), meta


# ---------------------------------------------------------------------------
# auto-detect


def load_dataset(path: str | Path,
                 layout: str = "auto") -> tuple[list[dict], dict]:
    """Load a dataset dir/file, auto-detecting the layout when asked."""
    p = Path(path)
    if layout == "auto":
        if p.is_dir() and (p / "labels.csv").is_file() \
                and (p / "manifest.json").is_file():
            layout = "kavach"
        elif p.is_dir() and (p / "classes.txt").is_file() \
                and (p / "images").is_dir():
            layout = "yolo"
        elif p.is_file() and p.suffix.lower() == ".csv":
            layout = "csv"
        elif p.is_file() and p.suffix.lower() == ".json":
            try:
                keys = set(json.loads(p.read_text()).keys())
            except (json.JSONDecodeError, UnicodeDecodeError):
                keys = set()
            if {"images", "annotations", "categories"}.issubset(keys):
                layout = "coco"
            else:
                raise IngestError(f"cannot auto-detect layout for {p}")
        elif p.is_dir():
            layout = "folder"
        else:
            raise IngestError(f"cannot auto-detect layout for {p}")
    loaders = {"kavach": load_kavach, "folder": load_folder, "csv": load_csv,
               "yolo": load_yolo, "coco": load_coco}
    if layout not in loaders:
        raise IngestError(f"unknown layout {layout!r}; "
                          f"choose from {sorted(loaders)}")
    return loaders[layout](p)
