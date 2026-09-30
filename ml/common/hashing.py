"""Hashing primitives: SHA-256 (exact) and 64-bit dHash (perceptual)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(image: Image.Image) -> str:
    """64-bit difference hash → 16-hex-char string. Grayscale 9x8, row diffs."""
    g = image.convert("L").resize((9, 8), Image.LANCZOS)
    px = np.asarray(g, dtype=np.int16)
    diff = px[:, 1:] > px[:, :-1]  # (8, 8) booleans
    bits = diff.flatten()
    val = 0
    for b in bits:
        val = (val << 1) | int(b)
    return f"{val:016x}"


def hamming_hex(a: str, b: str) -> int:
    """Hamming distance between two hex dHash strings."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")
