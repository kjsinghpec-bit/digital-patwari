import json

from digital_patwari.cache import FilePageObservationCache, MemoryPageObservationCache, page_cache_key
from digital_patwari.extraction import DocumentStatus, FardExtractionParser
from digital_patwari.observations import PageCellObservation, PageObservation
from tests.factories import make_document


def write_page(path, marker):
    path.write_bytes(b"\x89PNG\r\n" + marker)


def payload(page_number, document=None):
    return PageObservation(
        page_number=page_number,
        cells=[PageCellObservation(column_ref="1", raw_text=str(page_number))],
        canonical_payload=(document or make_document()).model_dump(mode="json"),
    ).model_dump(mode="json")


class RecordingProvider:
    cache_identity = "recording-provider-v1"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def extract_structured(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_provider_contract_requests_page_observation_schema(tmp_path):
    page = tmp_path / "fard_1.png"
    write_page(page, b"one")
    provider = RecordingProvider([payload(1)])

    result = FardExtractionParser(provider=provider, max_page_retries=0).extract([page])

    assert result.status == DocumentStatus.COMPLETE
    assert provider.calls[0]["json_schema"] is PageObservation
    assert result.observations[0].cells[0].raw_text == "1"


def test_transient_page_failure_is_retried_then_succeeds(tmp_path):
    page = tmp_path / "fard_1.png"
    write_page(page, b"retry")
    provider = RecordingProvider([ConnectionError("temporary"), payload(1)])

    result = FardExtractionParser(provider=provider, max_page_retries=1).extract([page])

    assert result.status == DocumentStatus.COMPLETE
    assert len(provider.calls) == 2


def test_successful_page_cache_prevents_reextraction_on_retry_run(tmp_path):
    page1 = tmp_path / "fard_1.png"
    page2 = tmp_path / "fard_2.png"
    write_page(page1, b"one")
    write_page(page2, b"two")
    cache = MemoryPageObservationCache()
    first_provider = RecordingProvider([payload(1), ConnectionError("page two failed")])

    first = FardExtractionParser(
        provider=first_provider, cache=cache, max_page_retries=0, batch_size=1,
    ).extract([page1, page2])
    assert first.status == DocumentStatus.PARTIAL

    second_provider = RecordingProvider([payload(2)])
    second = FardExtractionParser(
        provider=second_provider, cache=cache, max_page_retries=0, batch_size=1,
    ).extract([page1, page2])

    assert second.status == DocumentStatus.COMPLETE
    assert len(second_provider.calls) == 1
    assert second.successful_pages == (1, 2)


def test_document_statuses_cover_complete_warnings_partial_and_failed(tmp_path):
    page1 = tmp_path / "fard_1.png"
    page2 = tmp_path / "fard_2.png"
    write_page(page1, b"one")
    write_page(page2, b"two")

    warning_payload = payload(1, make_document(village="Village A"))
    warning_payload_2 = payload(2, make_document(village="Village B"))
    warned = FardExtractionParser(
        provider=RecordingProvider([warning_payload, warning_payload_2]),
        max_page_retries=0,
        batch_size=1,
    ).extract([page1, page2])
    assert warned.status == DocumentStatus.COMPLETE_WITH_WARNINGS

    partial = FardExtractionParser(
        provider=RecordingProvider([payload(1), ConnectionError("down")]),
        max_page_retries=0,
        batch_size=1,
    ).extract([page1, page2])
    assert partial.status == DocumentStatus.PARTIAL
    assert partial.document is not None

    failed = FardExtractionParser(
        provider=RecordingProvider([ConnectionError("down")]), max_page_retries=0,
    ).extract([page1])
    assert failed.status == DocumentStatus.FAILED
    assert failed.document is None
    assert any("transport_error" in error for error in failed.parser_errors)


def test_file_cache_round_trips_observation_and_ignores_corrupt_entry(tmp_path):
    cache = FilePageObservationCache(tmp_path / "cache")
    key = page_cache_key(
        {"mime_type": "image/png", "base64_data": "YWJj"}, "provider-v1",
    )
    page = PageObservation.model_validate(payload(1))

    cache.put(key, page)
    assert cache.get(key) == page

    (tmp_path / "cache" / f"{key}.json").write_text("not json", encoding="utf-8")
    assert cache.get(key) is None
