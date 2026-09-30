"""KavachAI model packaging: sklearn models + signed manifest.

Security rule: a .pkl is *executed* only when its SHA-256 matches a
KavachAI-generated manifest stored alongside it. Anything else is
metadata-only.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from .hashing import sha256_file
from .utils import canonical_json, utcnow


class UntrustedModelError(Exception):
    """Raised when a model file is not allowlisted for execution."""


def save_kavach_model(model: Any, path: Path, metadata: dict) -> dict:
    """Pickle `model` and write `<path>.manifest.json` with its digest."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    digest = sha256_file(path)
    manifest = {
        "sha256": digest,
        "metadata": metadata,
        "created_at": utcnow(),
        "generator": "kavach-ai",
    }
    path.with_suffix(path.suffix + ".manifest.json").write_text(
        canonical_json(manifest))
    return manifest


def load_kavach_model(path: Path) -> tuple[Any, dict]:
    """Load a pickled model ONLY if its digest matches its manifest.

    Raises UntrustedModelError otherwise (caller falls back to
    metadata-only handling with an explicit limitation note).
    """
    path = Path(path)
    manifest_path = path.with_suffix(path.suffix + ".manifest.json")
    if not manifest_path.exists():
        raise UntrustedModelError(
            f"no KavachAI manifest for {path.name}: execution refused")
    manifest = json.loads(manifest_path.read_text())
    digest = sha256_file(path)
    if digest != manifest.get("sha256"):
        raise UntrustedModelError(
            f"digest mismatch for {path.name}: execution refused")
    with open(path, "rb") as f:
        model = pickle.load(f)  # noqa: S301 — digest-verified own artifact
    return model, manifest
