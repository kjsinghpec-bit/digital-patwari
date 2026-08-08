"""Per-page observation caches used by the offline extraction orchestrator."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Protocol

from digital_patwari.observations import PageObservation


class PageObservationCache(Protocol):
    def get(self, key: str) -> PageObservation | None: ...

    def put(self, key: str, observation: PageObservation) -> None: ...


def page_cache_key(
    part: dict[str, Any],
    provider_identity: str,
    *,
    extraction_prompt: str = "",
    observation_schema: str = "3_STRUCTURAL_VERIFICATION",
) -> str:
    """Stable key over bytes, provider, exact prompt, and exact schema fingerprint."""
    digest = hashlib.sha256()
    digest.update(observation_schema.encode("utf-8"))
    digest.update(b"\0")
    digest.update(extraction_prompt.encode("utf-8"))
    digest.update(b"\0")
    digest.update(provider_identity.encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(part.get("mime_type", "")).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(part.get("base64_data", "")).encode("ascii"))
    return digest.hexdigest()


class MemoryPageObservationCache:
    def __init__(self) -> None:
        self.entries: dict[str, PageObservation] = {}

    def get(self, key: str) -> PageObservation | None:
        return self.entries.get(key)

    def put(self, key: str, observation: PageObservation) -> None:
        self.entries[key] = observation


class FilePageObservationCache:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def get(self, key: str) -> PageObservation | None:
        path = self.directory / f"{key}.json"
        if not path.exists():
            return None
        try:
            return PageObservation.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A corrupt/incompatible cache entry is a miss, never a failed page.
            return None

    def put(self, key: str, observation: PageObservation) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{key}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(observation.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, path)
