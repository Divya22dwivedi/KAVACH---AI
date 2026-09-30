"""Shared backend service helpers for KavachAI routers.

All persistence flows through these helpers so every endpoint performs a
REAL operation via the ml/ modules. Nothing here fabricates results.
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import sqlite3
import uuid
from pathlib import Path

from PIL import Image

from ml.common.hashing import dhash, sha256_bytes, sha256_file
from ml.common.utils import canonical_json, utcnow

from . import db
from . import security

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = REPO_ROOT / "datasets"
GENERATED_DIR = DATASETS_DIR / "generated"
UPLOADED_DIR = DATASETS_DIR / "uploaded"
FEATURES_DIR = DATASETS_DIR / "features"
MODELS_DIR = REPO_ROOT / "models"
UPLOADED_MODELS_DIR = MODELS_DIR / "uploaded"
REPORTS_DIR = REPO_ROOT / "reports"
PROBE_NPZ = MODELS_DIR / "probe.npz"

FINDING_ID_PREFIX_LEN = 12


# ---------------------------------------------------------------- primitives

def con() -> sqlite3.Connection:
    """Singleton DB connection (initialised by app lifespan)."""
    return db.get_connection()


def audit(action: str, detail: dict | None = None) -> None:
    db.audit(action, canonical_json(detail or {}))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:FINDING_ID_PREFIX_LEN]}"


def utcnow_iso() -> str:
    return utcnow()


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def sha256_of_bytes(data: bytes) -> str:
    return sha256_bytes(data)


# ---------------------------------------------------------------- datasets

def _sample_hashes(img: Image.Image, raw: bytes) -> tuple[str, str]:
    """Return (sha256, dhash) for an image sample. Both measured."""
    return sha256_of_bytes(raw), dhash(img)


def persist_dataset(*, name: str, source_format: str, root_dir: str | Path,
                    rows: list[dict], synthetic: bool = False,
                    params: dict | None = None) -> dict:
    """Persist a dataset + per-sample sha256/dhash into dataset_samples.

    ``rows``: list of {sample_id, abs_path, label, contributor_id}.
    Returns the dataset record dict including manifest_hash.
    Reuses an existing dataset with the same name (idempotent-ish).
    """
    c = con()
    existing = c.execute(
        "SELECT * FROM datasets WHERE name = ?", (name,)).fetchone()
    if existing is not None:
        return row_dict(existing)

    root = Path(root_dir)
    dataset_id = new_id("ds")
    created = utcnow_iso()
    sample_rows: list[tuple] = []
    hash_pairs: list[tuple[str, str]] = []
    for r in rows:
        abs_path = Path(r["abs_path"])
        try:
            rel = str(abs_path.resolve().relative_to(root.resolve()))
        except ValueError:
            rel = abs_path.name
        img = Image.open(abs_path).convert("RGB")
        raw = abs_path.read_bytes()
        sha, dh = _sample_hashes(img, raw)
        hash_pairs.append((str(r["sample_id"]), sha))
        sample_rows.append((
            new_id("smp"), dataset_id, rel,
            r.get("label"), r.get("contributor_id"),
            sha, dh, img.width, img.height, created,
        ))
    manifest_hash = sha256_of_bytes(
        canonical_json(sorted(hash_pairs)).encode("utf-8"))
    c.execute(
        "INSERT INTO datasets (id, name, source_format, created_at, "
        "sample_count, manifest_hash, synthetic, params_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (dataset_id, name, source_format, created, len(sample_rows),
         manifest_hash, 1 if synthetic else 0,
         canonical_json({**(params or {}), "root_dir": str(root)})),
    )
    c.executemany(
        "INSERT INTO dataset_samples (id, dataset_id, rel_path, label, "
        "contributor_id, sha256, dhash, width, height, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        sample_rows,
    )
    c.commit()
    audit("dataset.persist", {"dataset_id": dataset_id, "name": name,
                              "sample_count": len(sample_rows),
                              "manifest_hash": manifest_hash})
    return {
        "id": dataset_id, "name": name, "source_format": source_format,
        "created_at": created, "sample_count": len(sample_rows),
        "manifest_hash": manifest_hash, "synthetic": synthetic,
        "params": {"root_dir": str(root)},
    }


def get_dataset(dataset_id: str) -> dict:
    row = row_dict(con().execute(
        "SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone())
    if row is None:
        raise ValueError(f"dataset {dataset_id!r} not found")
    return row


def dataset_rows(dataset_id: str) -> list[dict]:
    """Build run_scan-style rows (with abs_path) for a persisted dataset."""
    ds = get_dataset(dataset_id)
    root = Path(json.loads(ds["params_json"]).get("root_dir", ""))
    rows = []
    for r in con().execute(
            "SELECT * FROM dataset_samples WHERE dataset_id = ? "
            "ORDER BY rel_path", (dataset_id,)).fetchall():
        abs_path = str((root / r["rel_path"]).resolve())
        rows.append({
            "sample_id": Path(r["rel_path"]).stem,
            "abs_path": abs_path,
            "label": r["label"],
            "contributor_id": r["contributor_id"],
        })
    return rows


def dataset_sample_image(dataset_id: str, sample_id: str) -> Image.Image:
    """Load a sample's image by its sample id (stem match)."""
    ds = get_dataset(dataset_id)
    root = Path(json.loads(ds["params_json"]).get("root_dir", ""))
    for r in con().execute(
            "SELECT rel_path FROM dataset_samples WHERE dataset_id = ?",
            (dataset_id,)).fetchall():
        if Path(r["rel_path"]).stem == sample_id:
            p = (root / r["rel_path"]).resolve()
            if not p.is_file():
                raise ValueError(f"sample file missing: {sample_id!r}")
            return Image.open(p).convert("RGB")
    raise ValueError(f"sample {sample_id!r} not found in dataset {dataset_id!r}")


def dataset_images(dataset_id: str, limit: int | None = None
                   ) -> list[tuple[str, Image.Image, str | None]]:
    """Return [(sample_id, image, label)] for a dataset, in stored order."""
    ds = get_dataset(dataset_id)
    root = Path(json.loads(ds["params_json"]).get("root_dir", ""))
    out = []
    for r in con().execute(
            "SELECT rel_path, label FROM dataset_samples "
            "WHERE dataset_id = ? ORDER BY rel_path",
            (dataset_id,)).fetchall():
        p = (root / r["rel_path"]).resolve()
        if not p.is_file():
            continue
        out.append((Path(r["rel_path"]).stem,
                    Image.open(p).convert("RGB"), r["label"]))
        if limit is not None and len(out) >= limit:
            break
    return out


def image_to_base64_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def base64_to_image(data_b64: str) -> Image.Image:
    try:
        raw = base64.b64decode(data_b64, validate=True)
    except Exception as exc:
        raise ValueError(f"invalid base64 image: {exc}") from exc
    security.check_size(len(raw), security.MAX_IMAGE_BYTES)
    if not security.is_image_bytes(raw[:16]):
        raise ValueError("not an image (magic-byte check failed)")
    return Image.open(io.BytesIO(raw)).convert("RGB")


# ---------------------------------------------------------------- findings

def _next_finding_id() -> str:
    c = con()
    mx = c.execute(
        "SELECT MAX(CAST(SUBSTR(id, 3) AS INTEGER)) AS m FROM findings "
        "WHERE id GLOB 'F-[0-9]*'").fetchone()["m"]
    return f"F-{(int(mx or 0) + 1):04d}"


def persist_scan_findings(scan_id: str, findings: list[dict]) -> list[dict]:
    """Persist scan findings with globally unique F-NNNN ids. Returns rows."""
    from ml.evidence.findings import make_finding

    c = con()
    stored = []
    for f in findings:
        fid = _next_finding_id()
        rec = make_finding(
            finding_id=fid,
            category=f.get("category", "data"),
            asset_id=f["asset_id"],
            title=f["title"],
            detection_method=f["detection_method"],
            evidence=json.loads(f["evidence"]) if isinstance(
                f.get("evidence"), str) else dict(f.get("evidence", {})),
            confidence=float(f["confidence"]),
            severity=f["severity"],
            disposition=f["disposition"],
            supported_attack_class=f.get("supported_attack_class"),
            limitations=f["limitations"],
            created_at=f.get("created_at"),
        )
        c.execute(
            "INSERT INTO findings (id, scan_id, category, asset_id, title, "
            "detection_method, evidence_json, confidence, severity, "
            "disposition, supported_attack_class, limitations, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rec["id"], scan_id, rec["category"], rec["asset_id"],
             rec["title"], rec["detection_method"],
             canonical_json(rec["evidence"]), rec["confidence"],
             rec["severity"], rec["disposition"],
             rec["supported_attack_class"], rec["limitations"],
             rec["created_at"]),
        )
        stored.append(rec)
    c.commit()
    audit("findings.persist", {"scan_id": scan_id, "count": len(stored)})
    return stored


def finding_row_to_schema(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "scan_id": r["scan_id"],
        "category": r["category"],
        "asset_id": r["asset_id"],
        "title": r["title"],
        "detection_method": r["detection_method"],
        "evidence": json.loads(r["evidence_json"]),
        "confidence": r["confidence"],
        "severity": r["severity"],
        "disposition": r["disposition"],
        "supported_attack_class": r["supported_attack_class"],
        "limitations": r["limitations"],
        "reviewer_note": r["reviewer_note"] or "",
        "created_at": r["created_at"],
    }


# ---------------------------------------------------------------- models

def persist_model(rec: dict) -> dict:
    """Upsert a registry record into the models table."""
    c = con()
    existing = c.execute(
        "SELECT * FROM models WHERE sha256 = ?", (rec["sha256"],)).fetchone()
    if existing is not None:
        c.execute("UPDATE models SET name = ?, role = ? WHERE id = ?",
                  (rec["name"], rec.get("role"), existing["id"]))
        c.commit()
        return row_dict(c.execute(
            "SELECT * FROM models WHERE id = ?",
            (existing["id"],)).fetchone())
    c.execute(
        "INSERT INTO models (id, name, format, sha256, size_bytes, "
        "metadata_json, manifest_ok, role, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rec["id"], rec["name"], rec["format"], rec["sha256"],
         rec["size_bytes"], canonical_json(rec["metadata"]),
         rec["manifest_ok"], rec.get("role"), rec["created_at"]),
    )
    c.commit()
    audit("model.register", {"model_id": rec["id"], "name": rec["name"],
                             "sha256": rec["sha256"],
                             "manifest_ok": rec["manifest_ok"]})
    return row_dict(c.execute(
        "SELECT * FROM models WHERE id = ?", (rec["id"],)).fetchone())


def get_model(model_id: str) -> dict:
    row = row_dict(con().execute(
        "SELECT * FROM models WHERE id = ?", (model_id,)).fetchone())
    if row is None:
        raise ValueError(f"model {model_id!r} not found")
    return row


def model_registry_rec(model_row: dict) -> dict:
    """Rebuild the registry-style record dict the checks module expects."""
    return {
        "id": model_row["id"],
        "name": model_row["name"],
        "path": resolve_model_path(model_row),
        "format": model_row["format"],
        "sha256": model_row["sha256"],
        "size_bytes": model_row["size_bytes"],
        "metadata": json.loads(model_row["metadata_json"]),
        "manifest_ok": model_row["manifest_ok"],
        "role": model_row.get("role"),
    }


def uploaded_model_path(model_id: str, filename: str) -> Path:
    """Canonical on-disk path for an uploaded model file."""
    safe = security.sanitize_filename(filename)
    return UPLOADED_MODELS_DIR / f"{model_id}_{safe}"


def resolve_model_path(model_row: dict) -> str:
    """Find the real on-disk file for a registered model."""
    cands = sorted(UPLOADED_MODELS_DIR.glob(f"{model_row['id']}_*"))
    # Prefer the actual model file over its sibling *.manifest.json.
    model_files = [c for c in cands
                   if not c.name.endswith(".manifest.json")]
    if model_files:
        return str(model_files[0])
    if cands:
        return str(cands[0])
    digest = model_row["sha256"]
    for cand in MODELS_DIR.glob("*.pkl"):
        try:
            if sha256_file(cand) == digest:
                return str(cand)
        except OSError:
            continue
    # Honest fallback: no file found; hash_verify will report it.
    return str(UPLOADED_MODELS_DIR / f"{model_row['id']}_missing")


def load_model_object(model_row: dict):
    """Allowlist-load an executable model object; None if not executable."""
    from ml.common.model_io import UntrustedModelError, load_kavach_model

    if int(model_row.get("manifest_ok") or 0) != 1:
        return None
    path = Path(resolve_model_path(model_row))
    if not path.is_file():
        # fall back to the repo models/ dir by digest match
        for cand in MODELS_DIR.glob("*.pkl"):
            if sha256_file(cand) == model_row["sha256"]:
                path = cand
                break
    try:
        model, _manifest = load_kavach_model(path)
    except (UntrustedModelError, FileNotFoundError, ValueError):
        return None
    return model


# ---------------------------------------------------------------- scans

def new_scan(dataset_id: str, experiment_id: str | None,
             params: dict | None) -> dict:
    scan_id = new_id("scan")
    experiment_id = experiment_id or new_id("exp")
    c = con()
    c.execute(
        "INSERT INTO scans (id, dataset_id, experiment_id, started_at, "
        "params_json, status) VALUES (?, ?, ?, ?, ?, ?)",
        (scan_id, dataset_id, experiment_id, utcnow_iso(),
         canonical_json(params or {}), "running"),
    )
    c.commit()
    return {"scan_id": scan_id, "experiment_id": experiment_id}


def finish_scan(scan_id: str, status: str = "done") -> None:
    con().execute(
        "UPDATE scans SET finished_at = ?, status = ? WHERE id = ?",
        (utcnow_iso(), status, scan_id))
    con().commit()


def get_scan(scan_id: str) -> dict:
    row = row_dict(con().execute(
        "SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone())
    if row is None:
        raise ValueError(f"scan {scan_id!r} not found")
    return row


def scan_summary(scan_id: str) -> dict:
    c = con()
    rows = c.execute(
        "SELECT severity, disposition, COUNT(*) AS n FROM findings "
        "WHERE scan_id = ? GROUP BY severity, disposition",
        (scan_id,)).fetchall()
    total = c.execute(
        "SELECT COUNT(*) AS n FROM findings WHERE scan_id = ?",
        (scan_id,)).fetchone()["n"]
    by_severity: dict[str, int] = {}
    for r in rows:
        by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + r["n"]
    return {"scan_id": scan_id, "total_findings": total,
            "by_severity": by_severity}


# ---------------------------------------------------------------- misc

def safe_upload_dir(prefix: str) -> Path:
    return security.safe_temp_dir(prefix=prefix)


def check_upload_size(n_bytes: int) -> None:
    security.check_size(n_bytes, security.MAX_UPLOAD_BYTES)


def cleanup_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
