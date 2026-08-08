import json

import pytest

from patwari_agent import (
    FardExtractionParser,
    load_document_parts,
    resolve_input_paths,
)


class _StubLLMClient:
    def __init__(self, payload):
        self.payload = payload

    def extract_structured(self, **kwargs):
        return self.payload


VALID_DOC = {
    "document_header": {
        "village": "V", "hadbast_number": "1", "jamabandi_year": "2020-21", "lr_number": "LR-1",
    },
    "khewats": [],
    "remarks": [],
}


def test_extract_succeeds_on_valid_payload(tmp_path):
    page = tmp_path / "fard_1.png"
    page.write_bytes(b"\x89PNG\r\n")
    client = _StubLLMClient(json.dumps(VALID_DOC))
    parser = FardExtractionParser(llm_client=client)
    result = parser.extract([str(page)])
    assert result.succeeded
    assert result.document.document_header.village == "V"


def test_extract_reports_structured_validation_error_with_field_path(tmp_path):
    page = tmp_path / "fard_1.png"
    page.write_bytes(b"\x89PNG\r\n")
    bad_doc = dict(VALID_DOC)
    bad_doc["document_header"] = {"village": "V"}  # missing required fields
    client = _StubLLMClient(json.dumps(bad_doc))
    parser = FardExtractionParser(llm_client=client)
    result = parser.extract([str(page)])
    assert not result.succeeded
    # The error must name the specific missing field path, not a bare string.
    assert any("document_header" in err for err in result.parser_errors)
    assert any("hadbast_number" in err for err in result.parser_errors)


def test_extract_reports_transport_error_distinctly(tmp_path):
    page = tmp_path / "fard_1.png"
    page.write_bytes(b"\x89PNG\r\n")

    class _FailingClient:
        def extract_structured(self, **kwargs):
            raise ConnectionError("network down")

    parser = FardExtractionParser(llm_client=_FailingClient())
    result = parser.extract([str(page)])
    assert not result.succeeded
    assert any("transport_error" in err for err in result.parser_errors)


def test_load_document_parts_rejects_unsupported_mime_type(tmp_path):
    bad_file = tmp_path / "fard.txt"
    bad_file.write_text("not an image")
    with pytest.raises(ValueError):
        load_document_parts([str(bad_file)])


def test_load_document_parts_rejects_empty_input():
    with pytest.raises(ValueError):
        load_document_parts([])


def test_resolve_input_paths_expands_directory(tmp_path):
    (tmp_path / "fard_2.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "fard_1.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "notes.txt").write_text("ignored")
    resolved = resolve_input_paths([str(tmp_path)])
    names = [p.name for p in resolved]
    assert names == ["fard_1.png", "fard_2.png"]  # sorted, unsupported types excluded


def test_resolve_input_paths_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        resolve_input_paths(["/no/such/path/fard_1.png"])
