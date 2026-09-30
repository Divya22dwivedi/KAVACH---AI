"""Shared utilities: RNG, canonical JSON, experiment IDs, timestamps."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np


def seeded_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def canonical_json(obj) -> str:
    """Deterministic JSON encoding for hashing / experiment IDs."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def experiment_id(params: dict) -> str:
    return hashlib.sha256(canonical_json(params).encode()).hexdigest()[:16]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
