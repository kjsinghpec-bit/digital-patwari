from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

SUPPORTED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "application/pdf"}


def resolve_input_paths(inputs: list[str | Path]) -> list[Path]:
    """Expand a caller-supplied list of files and/or directories into an
    ordered list of document files. Directories are expanded to their
    sorted, supported-MIME-type contents (non-recursive)."""
    resolved: list[Path] = []
    for supplied in inputs:
        path = Path(supplied)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            children = sorted(
                p for p in path.iterdir()
                if p.is_file() and (mimetypes.guess_type(p.name)[0] in SUPPORTED_MIME_TYPES)
            )
            if not children:
                raise ValueError(f"Directory has no supported Fard pages: {path}")
            resolved.extend(children)
        else:
            resolved.append(path)
    if not resolved:
        raise ValueError("No input pages supplied.")
    return resolved


def load_document_parts(paths: list[str | Path]) -> list[dict[str, Any]]:
    paths = resolve_input_paths(paths)
    parts: list[dict[str, Any]] = []
    for path in paths:
        mime_type, _ = mimetypes.guess_type(path.name)
        if mime_type not in SUPPORTED_MIME_TYPES:
            raise ValueError(
                f"Unsupported file type for {path}: {mime_type!r}. "
                f"Supported types: {sorted(SUPPORTED_MIME_TYPES)}"
            )
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        parts.append({"filename": path.name, "mime_type": mime_type, "base64_data": encoded})
    return parts
