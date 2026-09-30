"""Model registry for Module 2 (model integrity).

SECURITY: registration never executes untrusted bytes. A ``.pkl`` is
marked executable (``manifest_ok=1``) only when its digest matches the
KavachAI signed manifest via :func:`load_kavach_model` (allowlist rule).
``.onnx`` files are parsed with the ``onnx`` library (graph structure
only, no inference session). ``.pt``/``.pth`` files are opened with
``zipfile`` and only record names/sizes are listed — they are NEVER
unpickled.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from ml.common.hashing import sha256_file
from ml.common.model_io import UntrustedModelError, load_kavach_model
from ml.common.utils import utcnow


# ---------------------------------------------------------------- helpers

def _pkl_metadata(path: Path) -> tuple[int, dict]:
    """Return (manifest_ok, metadata) for a .pkl.

    The pickle is *executed* only inside load_kavach_model, which refuses
    unless the file's SHA-256 matches its KavachAI manifest. On
    UntrustedModelError the record is metadata-only.
    """
    try:
        model, manifest = load_kavach_model(path)
    except UntrustedModelError as exc:
        return 0, {"executable": False, "error": str(exc)}
    metadata = dict(manifest.get("metadata", {}))
    metadata["executable"] = True
    classes = getattr(model, "classes_", None)
    if classes is not None:
        metadata["registered_classes"] = [str(c) for c in classes]
    return 1, metadata


def _onnx_metadata(path: Path) -> dict:
    """Parse an .onnx graph: inputs/outputs, node count, opset. No execution."""
    try:
        import onnx
        model = onnx.load(str(path))  # parse only; no InferenceSession
    except Exception as exc:  # corrupt / unreadable file
        return {"executable": False, "parse": "unavailable",
                "error": f"{type(exc).__name__}: {exc}"}
    graph = model.graph
    return {
        "executable": False,
        "inputs": [i.name for i in graph.input],
        "outputs": [o.name for o in graph.output],
        "node_count": len(graph.node),
        "op_types": sorted({n.op_type for n in graph.node}),
        "opset_import": {o.domain: o.version for o in model.opset_import},
    }


def _torch_metadata(path: Path) -> dict:
    """Zip-listing of a .pt/.pth archive: record names + sizes ONLY.

    The archive is never unpickled — contents are not inspected beyond
    the zip central directory.
    """
    if not zipfile.is_zipfile(path):
        return {"executable": False, "parse": "unavailable",
                "note": "not a zip archive; contents not inspected"}
    records = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            records.append({"name": info.filename, "size": info.file_size})
    return {
        "executable": False,
        "num_records": len(records),
        "total_uncompressed_bytes": sum(r["size"] for r in records),
        "records": records,
    }


# ---------------------------------------------------------------- public

def register_model(path: str | Path, name: str, role: str) -> dict:
    """Register a model file. Returns a metadata record dict.

    Keys: id, name, path, format, sha256, size_bytes, metadata,
    manifest_ok, role, created_at. Formats: .pkl -> "sklearn-pkl",
    .onnx -> "onnx", .pt/.pth -> "torch-pt".
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"model file not found: {path}")
    digest = sha256_file(path)
    size = path.stat().st_size
    ext = path.suffix.lower()
    if ext == ".pkl":
        fmt = "sklearn-pkl"
        manifest_ok, metadata = _pkl_metadata(path)
    elif ext == ".onnx":
        fmt = "onnx"
        manifest_ok, metadata = 0, _onnx_metadata(path)
    elif ext in (".pt", ".pth"):
        fmt = "torch-pt"
        manifest_ok, metadata = 0, _torch_metadata(path)
    else:
        fmt = "unknown"
        manifest_ok, metadata = 0, {"executable": False,
                                    "parse": "unavailable"}
    return {
        "id": f"model_{digest[:12]}",
        "name": name,
        "path": str(path),
        "format": fmt,
        "sha256": digest,
        "size_bytes": size,
        "metadata": metadata,
        "manifest_ok": manifest_ok,
        "role": role,
        "created_at": utcnow(),
    }
