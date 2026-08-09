"""The centralized absence/completeness policy.

CLAUDE.md: 'Missing or failed pages must never be treated as proof that
data is absent.' This module is the ONLY place that decides the wording
and uncertainty state for a 'nothing found' claim -- Ask, viewmodels and
the JS screens must all consume its output rather than composing their own
text, so the policy can never drift between them.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from digital_patwari.extraction import FardExtractionParser
from digital_patwari_ui import fixtures as F
from digital_patwari_ui.absence import (
    AbsenceClaim,
    absence_claim,
    compute_unread_pages,
    is_partial,
    stated_total_pages,
)


def _run(scenario: F.FixtureScenario):
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for page_number in scenario.uploaded_pages:
            path = Path(tmp) / f"page-{page_number}.png"
            path.write_bytes(F.blank_page_png())
            paths.append(str(path))
        parser = FardExtractionParser(
            provider=F.FixtureProvider(scenario), batch_size=3, max_page_retries=0
        )
        return parser.extract(paths)


def test_absence_claim_on_a_complete_document_is_a_flat_statement():
    claim = absence_claim("mutation entries", unread_pages=[])
    assert claim.text == "No mutation entries were found."
    assert claim.tone == "ok"
    assert claim.uncertain is False


def test_absence_claim_on_a_partial_document_names_the_uncertainty():
    claim = absence_claim("mutation entries", unread_pages=[3])
    assert claim.text == (
        "No mutation entries were found in the pages successfully read. "
        "Unread pages may contain additional information."
    )
    assert claim.tone == "unknown"
    assert claim.uncertain is True


def test_absence_claim_wording_generalizes_to_other_entity_kinds():
    remarks = absence_claim("Column 8 remarks", unread_pages=[2])
    possession = absence_claim("cultivation or possession entries", unread_pages=[2])
    mortgages = absence_claim("mortgage entries", unread_pages=[2])
    for claim in (remarks, possession, mortgages):
        assert claim.tone == "unknown"
        assert claim.uncertain is True
        assert "Unread pages may contain additional information." in claim.text


def test_is_partial_reflects_whether_any_page_is_unread():
    assert is_partial([]) is False
    assert is_partial([3]) is True


def test_compute_unread_pages_is_empty_for_a_fully_read_document():
    result = _run(F.COMPLETE)
    unread = compute_unread_pages(result, F.COMPLETE.uploaded_pages)
    assert unread == []


def test_compute_unread_pages_lists_failed_pages_for_a_partial_document():
    result = _run(F.PAGE_FAILURE)
    unread = compute_unread_pages(result, F.PAGE_FAILURE.uploaded_pages)
    assert unread == [3]


def test_stated_total_pages_reads_the_documents_own_pagination():
    result = _run(F.COMPLETE)
    assert stated_total_pages(result.document) == 3


def test_absence_claim_is_a_plain_frozen_value_type():
    claim = absence_claim("mutation entries", unread_pages=[])
    assert isinstance(claim, AbsenceClaim)
    # frozen: no accidental mutation of a shared policy result
    try:
        claim.text = "different"
        assert False, "expected the claim to be immutable"
    except AttributeError:
        pass
