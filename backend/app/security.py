"""Security helpers: upload validation, path safety, size limits.

No arbitrary code execution from uploads: archives are never extracted
blindly, .pt/.pth files are never unpickled, .pkl models execute only when
their SHA-256 matches a repo-signed KavachAI manifest (user-supplied
manifests are never trusted).
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB per upload
MAX_IMAGE_BYTES = 20 * 1024 * 1024   # 20 MB per image
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
ALLOWED_MODEL_EXTS = {".pkl", ".onnx", ".pt", ".pth"}

# PNG / JPEG / BMP / TIFF / WEBP magic bytes
_IMAGE_MAGICS = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"BM",
    b"II*\x00",
    b"MM\x00*",
    b"RIFF",
)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    """Strip directories and unsafe chars. Raises ValueError if unusable."""
    base = Path(name).name  # drop any directory components
    base = _SAFE_NAME.sub("_", base).strip("._")
    if not base or base in {".", ".."}:
        raise ValueError(f"unsafe filename: {name!r}")
    return base


def assert_safe_relpath(rel: str) -> str:
    """Ensure a relative path cannot escape its root (no .., no absolute)."""
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"path traversal rejected: {rel!r}")
    return str(p)


def check_size(n_bytes: int, limit: int = MAX_UPLOAD_BYTES) -> None:
    if n_bytes < 0:
        raise ValueError("negative size")
    if n_bytes > limit:
        raise ValueError(
            f"upload too large: {n_bytes} bytes > limit {limit} bytes")


def is_image_bytes(data: bytes) -> bool:
    """Magic-byte check (does not decode the image)."""
    return data[:12].startswith(_IMAGE_MAGICS) or any(
        data.startswith(m) for m in _IMAGE_MAGICS[1:]
    )


def safe_temp_dir(prefix: str = "kavach_") -> Path:
    """Create a private temp dir (0700). Caller must clean up."""
    return Path(tempfile.mkdtemp(prefix=prefix))
