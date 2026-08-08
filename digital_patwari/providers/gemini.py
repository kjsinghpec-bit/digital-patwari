from __future__ import annotations

import base64
import copy
import json
import os
import time

from google import genai
from google.genai import types
from pydantic import BaseModel

# Maximum times a too-complex schema is halved before giving up and raising
# the underlying error. 2**_MAX_SPLIT_DEPTH sub-requests in the worst case.
_MAX_SPLIT_DEPTH = 3

# Transient failure classes worth a bounded retry. Permanent 4xx errors
# (bad request, auth, not found) are never retried.
_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}

# Keywords Gemini's response_json_schema actually accepts (see
# GenerateContentConfig.response_json_schema docstring in google-genai).
# Pydantic's model_json_schema() emits extra keywords (minLength, default, ...)
# that make the API reject the whole request with an opaque 400; strip them.
_GEMINI_SUPPORTED_SCHEMA_KEYS = {
    "$id", "$defs", "$ref", "$anchor", "type", "format", "title", "description",
    "enum", "items", "prefixItems", "minItems", "maxItems", "minimum", "maximum",
    "anyOf", "oneOf", "properties", "additionalProperties", "required",
    "propertyOrdering",
}


# Keys whose values are maps keyed by *names* (property names, $defs names),
# not JSON Schema keywords — their keys must never be filtered.
_NAME_KEYED_MAP_KEYS = {"properties", "$defs"}


def _strip_unsupported_schema_keys(node):
    if isinstance(node, list):
        return [_strip_unsupported_schema_keys(item) for item in node]
    if not isinstance(node, dict):
        return node

    cleaned = {}
    for key, value in node.items():
        if key not in _GEMINI_SUPPORTED_SCHEMA_KEYS and not key.startswith("$"):
            continue
        if key in _NAME_KEYED_MAP_KEYS and isinstance(value, dict):
            cleaned[key] = {
                name: _strip_unsupported_schema_keys(sub_schema)
                for name, sub_schema in value.items()
            }
        else:
            cleaned[key] = _strip_unsupported_schema_keys(value)
    return cleaned


class MyLLMAdapter:
    def __init__(
        self,
        client=None,
        model_name: str = "gemini-3.5-flash",
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Export it in your environment before running."
            )
        self.client = client or genai.Client(api_key=key)
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _status_code(self, exc: Exception) -> int | None:
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        return status_code if isinstance(status_code, int) else None

    def _is_transient(self, exc: Exception) -> bool:
        status_code = self._status_code(exc)
        if status_code is not None:
            return status_code in _TRANSIENT_STATUS_CODES
        return isinstance(exc, (TimeoutError, ConnectionError))

    def _generate(self, *, contents: list, system_prompt: str, schema: dict) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_json_schema=schema,
            temperature=0.0,
            http_options=types.HttpOptions(timeout=int(self.timeout_seconds * 1000)),
        )

        attempt = 0
        while True:
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                return response.text
            except Exception as exc:
                if attempt >= self.max_retries or not self._is_transient(exc):
                    raise
                attempt += 1
                time.sleep(2 ** attempt)

    def _split_schema(self, schema: dict) -> tuple[dict, dict] | None:
        """Split a schema's top-level properties into two halves, each keeping
        every $def so nested $ref targets stay resolvable. Returns None when
        the schema can't be split further (fewer than 2 properties)."""
        properties = schema.get("properties", {})
        keys = list(properties.keys())
        if len(keys) < 2:
            return None

        midpoint = len(keys) // 2
        groups = (keys[:midpoint], keys[midpoint:])
        halves = []
        for group in groups:
            half = copy.deepcopy(schema)
            half["properties"] = {k: v for k, v in properties.items() if k in group}
            half["required"] = [r for r in schema.get("required", []) if r in group]
            halves.append(half)
        return halves[0], halves[1]

    def _generate_with_schema_fallback(self, *, contents: list, system_prompt: str, schema: dict, depth: int) -> dict:
        """Gemini's structured-output endpoint rejects some schemas with an
        opaque 400 once enough independently-branching top-level properties
        are combined (observed on DigitalPatwariDocument even after stripping
        unsupported JSON Schema keywords). When that happens, halve the
        schema's top-level properties and issue two requests instead of one,
        merging the disjoint results back into a single dict."""
        try:
            return json.loads(self._generate(contents=contents, system_prompt=system_prompt, schema=schema))
        except Exception as exc:
            if self._status_code(exc) != 400 or depth >= _MAX_SPLIT_DEPTH:
                raise
            split = self._split_schema(schema)
            if split is None:
                raise
            first_half, second_half = split
            merged: dict = {}
            for half in (first_half, second_half):
                merged.update(
                    self._generate_with_schema_fallback(
                        contents=contents, system_prompt=system_prompt, schema=half, depth=depth + 1
                    )
                )
            return merged

    def extract_structured(self, *, system_prompt: str, user_prompt: str, document_parts: list[dict], json_schema: type[BaseModel]) -> str:
        contents = [user_prompt]
        for part in document_parts:
            contents.append(
                types.Part.from_bytes(
                    data=base64.b64decode(part["base64_data"]),
                    mime_type=part["mime_type"],
                )
            )

        schema = _strip_unsupported_schema_keys(json_schema.model_json_schema())
        merged = self._generate_with_schema_fallback(
            contents=contents, system_prompt=system_prompt, schema=schema, depth=0
        )
        return json.dumps(merged)
