import json
from pathlib import Path

import pytest

from digital_patwari.cache import page_cache_key
from digital_patwari.cli import _resolve_output_dir
from digital_patwari.observations import PageObservation
from digital_patwari.providers.gemini import (
    MyLLMAdapter,
    _deep_merge,
    _replace_permissive_any_schemas,
    _strip_unsupported_schema_keys,
)


def test_default_cli_output_is_outside_repository(tmp_path, monkeypatch):
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / ".git").mkdir()
    app_data = tmp_path / "private-app-data"
    monkeypatch.setenv("DIGITAL_PATWARI_DATA_DIR", str(app_data))

    output = _resolve_output_dir(None, allow_repository_output=False, cwd=repository)

    assert output != repository
    assert repository not in output.parents
    assert app_data in output.parents
    assert not output.exists()


def test_repository_output_requires_explicit_unsafe_flag(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / ".git").mkdir()

    with pytest.raises(ValueError, match="Refusing to write private Fard artifacts"):
        _resolve_output_dir(str(repository), allow_repository_output=False, cwd=repository)
    assert _resolve_output_dir(
        str(repository / "development-output"),
        allow_repository_output=True,
        cwd=repository,
    ) == repository / "development-output"


def test_cache_key_changes_with_exact_prompt_and_schema():
    part = {"mime_type": "image/png", "base64_data": "YWJj"}
    first = page_cache_key(part, "provider", extraction_prompt="prompt A", observation_schema="schema-1")
    prompt_changed = page_cache_key(part, "provider", extraction_prompt="prompt B", observation_schema="schema-1")
    schema_changed = page_cache_key(part, "provider", extraction_prompt="prompt A", observation_schema="schema-2")

    assert first != prompt_changed
    assert first != schema_changed


def _contains_permissive_schema(node, parent_key=None):
    if isinstance(node, list):
        return any(_contains_permissive_schema(item, parent_key) for item in node)
    if not isinstance(node, dict):
        return False
    if not node and parent_key not in {"properties", "$defs"}:
        return True
    return any(_contains_permissive_schema(value, key) for key, value in node.items())


def test_page_observation_gemini_schema_has_no_permissive_any_fragments():
    schema = _replace_permissive_any_schemas(
        _strip_unsupported_schema_keys(PageObservation.model_json_schema())
    )

    assert not _contains_permissive_schema(schema)
    rendered = json.dumps(schema)
    assert '"additionalProperties"' in rendered
    assert '"anyOf"' in rendered


def test_schema_split_finds_nested_canonical_payload_properties():
    schema = {
        "type": "object",
        "properties": {"page_number": {"type": "integer"}},
        "required": ["page_number"],
        "$defs": {
            "Canonical": {
                "type": "object",
                "properties": {
                    "document_header": {"type": "object"},
                    "khewats": {"type": "array"},
                    "mutations": {"type": "array"},
                    "remarks": {"type": "array"},
                },
                "required": ["document_header", "khewats", "mutations", "remarks"],
            }
        },
    }
    adapter = object.__new__(MyLLMAdapter)

    first, second = adapter._split_schema(schema)

    first_properties = first["$defs"]["Canonical"]["properties"]
    second_properties = second["$defs"]["Canonical"]["properties"]
    assert set(first_properties).isdisjoint(second_properties)
    assert set(first_properties) | set(second_properties) == {
        "document_header", "khewats", "mutations", "remarks",
    }


def test_nested_split_results_deep_merge_without_overwrite():
    first = {"canonical_payload": {"khewats": [1], "remarks": []}, "page_number": 1}
    second = {"canonical_payload": {"mutations": [2]}, "cells": []}

    assert _deep_merge(first, second) == {
        "canonical_payload": {"khewats": [1], "remarks": [], "mutations": [2]},
        "page_number": 1,
        "cells": [],
    }


def test_recursive_nested_fallback_recombines_canonical_payload_offline():
    class BadRequest(Exception):
        code = 400

    class OfflineAdapter(MyLLMAdapter):
        def __init__(self):
            pass

        def _generate(self, *, contents, system_prompt, schema):
            properties = schema["properties"]["canonical_payload"]["properties"]
            if len(properties) > 1:
                raise BadRequest("schema too complex")
            key = next(iter(properties))
            return json.dumps({"canonical_payload": {key: f"value-{key}"}})

    schema = {
        "type": "object",
        "properties": {
            "canonical_payload": {
                "type": "object",
                "properties": {
                    "header": {"type": "string"},
                    "khewats": {"type": "string"},
                    "mutations": {"type": "string"},
                    "remarks": {"type": "string"},
                },
                "required": ["header", "khewats", "mutations", "remarks"],
            }
        },
        "required": ["canonical_payload"],
    }

    result = OfflineAdapter()._generate_with_schema_fallback(
        contents=[], system_prompt="offline", schema=schema, depth=0,
    )

    assert set(result["canonical_payload"]) == {"header", "khewats", "mutations", "remarks"}
