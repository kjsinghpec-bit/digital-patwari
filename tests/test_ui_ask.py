"""'Ask Digital Patwari' must never generate free text: every answer comes
from a real digital_patwari.query.FardQueryEngine method, and an
unrecognised question must return state='unsupported' with real
suggestions rather than guessing at an intent.

It must also never claim "none found" with confidence when a page failed
or was never uploaded -- that policy is centralized in
digital_patwari_ui.absence and must be the SAME wording the Summary/
Mutations/Possession/Mortgages screens use (see test_ui_absence.py and
test_ui_viewmodels.py for the shared policy and its view-model consumer)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from digital_patwari.extraction import ExtractionResult, FardExtractionParser
from digital_patwari.reconciliation import reconcile
from digital_patwari.validation import run_axiom_gates
from digital_patwari_ui import fixtures as F
from digital_patwari_ui.ask import (
    AskRequest,
    QueryEngineAskAdapter,
    UnavailableAskAdapter,
    build_ask_adapter,
)
from digital_patwari_ui.viewmodels import EvidenceIndex
from tests.factories import make_header, make_khewat, make_owner
from patwari_agent import DigitalPatwariDocument


def _adapter(scenario: F.FixtureScenario, *, unread_pages: list[int] | None = None) -> QueryEngineAskAdapter:
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for page_number in scenario.uploaded_pages:
            path = Path(tmp) / f"page-{page_number}.png"
            path.write_bytes(F.blank_page_png())
            paths.append(str(path))
        parser = FardExtractionParser(
            provider=F.FixtureProvider(scenario), batch_size=3, max_page_retries=0
        )
        result = parser.extract(paths)
    record = reconcile(result.document, result.validation_report)
    index = EvidenceIndex(result.observations)
    adapter = build_ask_adapter(record, index, unread_pages=unread_pages)
    assert isinstance(adapter, QueryEngineAskAdapter)
    return adapter


def _bare_record_with_no_entries():
    """A minimal, fully-validated document with an owner but zero
    mutations, remarks or cultivation interests -- lets the four
    'nothing found' Ask branches be tested precisely, independent of which
    fixture scenario happens to have empty categories."""
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    document = DigitalPatwariDocument(document_header=make_header(), khewats=[khewat])
    report = run_axiom_gates(document)
    record = reconcile(document, report)
    index = EvidenceIndex(())
    return record, index


def _bare_adapter(unread_pages: list[int] | None = None) -> QueryEngineAskAdapter:
    record, index = _bare_record_with_no_entries()
    adapter = build_ask_adapter(record, index, unread_pages=unread_pages)
    assert isinstance(adapter, QueryEngineAskAdapter)
    return adapter


def test_unavailable_adapter_answers_nothing():
    adapter = build_ask_adapter(None, None)
    assert isinstance(adapter, UnavailableAskAdapter)
    assert adapter.available is False
    answer = adapter.ask(AskRequest(question="Who owns this land?"))
    assert answer.state == "unavailable"
    assert answer.record_says is None
    assert answer.suggestions == []


def test_unrecognised_question_is_unsupported_not_guessed():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="What is the weather like today?"))
    assert answer.state == "unsupported"
    assert answer.record_says is None
    assert answer.suggestions  # real, engine-backed suggestions are offered


def test_owner_land_question_routes_to_real_owner_land_method():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="What land is recorded in Jasvir Singh's name?"))
    assert answer.state == "answered"
    assert "1/2" in answer.record_says
    assert answer.calculated is not None
    assert answer.citations  # cites real evidence, not a bare claim


def test_khataunis_of_khewat_question_finds_both_continuation_khataunis():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="Which Khataunis belong to Khewat 45/40?"))
    assert answer.state == "answered"
    assert "101" in answer.record_says and "102" in answer.record_says


def test_pages_missing_question_reports_complete_when_ag04_passes():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="Are any pages missing?"))
    assert answer.state == "answered"
    assert answer.uncertain is False
    assert "present" in answer.record_says.lower()


def test_mortgage_question_flags_uncertainty_when_no_release_found():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="Are there any mortgages or important remarks?"))
    assert answer.state == "answered"
    assert answer.uncertain is True
    assert "ਰਹਿਨ" in answer.record_says or "mortgage" in answer.record_says.lower()


def test_explicit_intent_bypasses_the_text_router():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="ignored text", intent="total_area"))
    assert answer.state == "answered"
    assert answer.calculated is not None


def test_owner_land_without_a_recognised_subject_asks_for_clarification():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="ignored", intent="owner_land"))
    assert answer.state == "unsupported"


def test_suggestions_are_grounded_in_the_actual_document():
    adapter = _adapter(F.COMPLETE)
    suggestions = adapter.suggestions()
    texts = [s.text for s in suggestions]
    assert any("45/40" in text for text in texts)
    assert any("mortgage" in text.lower() for text in texts)


def test_calculation_question_points_to_the_calculations_screen():
    adapter = _adapter(F.COMPLETE)
    answer = adapter.ask(AskRequest(question="Show how this area was calculated"))
    assert answer.state == "answered"
    assert "calculations" in (answer.interpretation or "").lower()


# -- P1: partial-document uncertainty must reach Ask's absence claims -----

def test_mutations_not_found_is_confident_on_a_complete_document():
    adapter = _bare_adapter(unread_pages=[])
    answer = adapter.ask(AskRequest(question="What mutations are recorded?"))
    assert answer.state == "answered"
    assert answer.record_says == "No mutation entries were found."
    assert answer.uncertain is False


def test_mutations_not_found_is_uncertain_on_a_partial_document():
    adapter = _bare_adapter(unread_pages=[3])
    answer = adapter.ask(AskRequest(question="What mutations are recorded?"))
    assert answer.state == "answered"
    assert answer.record_says == (
        "No mutation entries were found in the pages successfully read. "
        "Unread pages may contain additional information."
    )
    assert answer.uncertain is True
    assert answer.uncertainty_reason


def test_remarks_not_found_reflects_partial_completeness():
    complete = _bare_adapter(unread_pages=[])
    partial = _bare_adapter(unread_pages=[5])

    complete_answer = complete.ask(AskRequest(question="What is written in the remarks column?"))
    partial_answer = partial.ask(AskRequest(question="What is written in the remarks column?"))

    assert complete_answer.record_says == "No Column 8 remarks were found."
    assert complete_answer.uncertain is False
    assert partial_answer.record_says == (
        "No Column 8 remarks were found in the pages successfully read. "
        "Unread pages may contain additional information."
    )
    assert partial_answer.uncertain is True


def test_possession_not_found_reflects_partial_completeness():
    complete = _bare_adapter(unread_pages=[])
    partial = _bare_adapter(unread_pages=[2])

    complete_answer = complete.ask(AskRequest(question="Who is recorded as cultivating this land?"))
    partial_answer = partial.ask(AskRequest(question="Who is recorded as cultivating this land?"))

    assert complete_answer.record_says == "No cultivation or possession entries were found."
    assert complete_answer.uncertain is False
    assert partial_answer.record_says == (
        "No cultivation or possession entries were found in the pages successfully read. "
        "Unread pages may contain additional information."
    )
    assert partial_answer.uncertain is True


def test_mortgage_not_found_reflects_partial_completeness():
    complete = _bare_adapter(unread_pages=[])
    partial = _bare_adapter(unread_pages=[3])

    complete_answer = complete.ask(AskRequest(question="Are there any mortgages or important remarks?"))
    partial_answer = partial.ask(AskRequest(question="Are there any mortgages or important remarks?"))

    assert complete_answer.uncertain is False
    assert "mortgage entries were found." in complete_answer.record_says.lower()
    assert partial_answer.uncertain is True
    assert "unread pages may contain additional information." in partial_answer.record_says.lower()


def test_wording_matches_exactly_between_ask_and_viewmodels_policy():
    """Ask and the view models must be indistinguishable in wording -- both
    delegate to digital_patwari_ui.absence.absence_claim, so this pins the
    no-duplication requirement directly rather than just trusting it."""
    from digital_patwari_ui.absence import absence_claim

    adapter = _bare_adapter(unread_pages=[7])
    answer = adapter.ask(AskRequest(question="What mutations are recorded?"))
    assert answer.record_says == absence_claim("mutation entries", [7]).text
