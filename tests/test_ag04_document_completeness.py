"""TEST 14: an uploaded Fard that states its own total page count (e.g.
"Page 5 of 8" -> total_pages=8) must be flagged INCOMPLETE if evidence
from fewer than 8 distinct pages is actually present -- never silently
analyzed as if it were the whole document."""
from patwari_agent import run_axiom_gates, validate_ag04_document_completeness
from tests.factories import make_document, make_khewat, make_owner, make_source


def test_ag04_skipped_when_no_page_states_a_total():
    document = make_document()
    result = validate_ag04_document_completeness(document)
    assert result.passed
    assert result.skipped_entities == 1


def test_ag04_passes_when_all_stated_pages_are_present():
    owner = make_owner("OWN-1", "KHW-1", "1/1", source=make_source(page=1, total_pages=2))
    khewat = make_khewat("KHW-1", owners=[owner], source=make_source(page=2, total_pages=2))
    document = make_document(khewats=[khewat])
    result = validate_ag04_document_completeness(document)
    assert result.passed
    assert not result.issues


def test_ag04_flags_incomplete_upload():
    owner = make_owner("OWN-1", "KHW-1", "1/1", source=make_source(page=5, total_pages=8))
    khewat = make_khewat("KHW-1", owners=[owner])
    document = make_document(khewats=[khewat])
    result = validate_ag04_document_completeness(document)
    assert not result.passed
    issue = result.issues[0]
    assert issue.expected == "8"
    assert issue.actual == "1"
    assert "Incomplete document" in issue.message


def test_ag04_included_in_full_axiom_gate_run():
    owner = make_owner("OWN-1", "KHW-1", "1/1", source=make_source(page=1, total_pages=3))
    khewat = make_khewat("KHW-1", owners=[owner])
    document = make_document(khewats=[khewat])
    report = run_axiom_gates(document)
    ag04 = next(g for g in report.gates if g.gate_id == "AG-04")
    assert not ag04.passed
    assert not report.passed
