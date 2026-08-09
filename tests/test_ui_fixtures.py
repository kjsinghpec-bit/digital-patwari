"""Every synthetic scenario must produce its documented DocumentStatus when
run through the REAL FardExtractionParser pipeline (no shortcuts, no
hand-authored status)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from digital_patwari.extraction import DocumentStatus, FardExtractionParser
from digital_patwari_ui import fixtures as F


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


def test_complete_scenario_passes_every_gate():
    result = _run(F.COMPLETE)
    assert result.status == DocumentStatus.COMPLETE
    assert result.validation_report.passed
    assert not result.page_warnings
    assert not result.parser_errors


def test_warning_scenario_flags_area_mismatch_via_ag03():
    result = _run(F.WARNING)
    assert result.status == DocumentStatus.COMPLETE_WITH_WARNINGS
    assert not result.validation_report.passed
    ag03 = next(g for g in result.validation_report.gates if g.gate_id == "AG-03")
    assert not ag03.passed
    assert ag03.issues


def test_needs_review_scenario_surfaces_one_open_question():
    result = _run(F.NEEDS_REVIEW)
    assert result.status == DocumentStatus.PARTIAL
    assert len(result.verification_issues) == 1
    assert result.verification_issues[0].issue_id == "verify-p3-kartar-share"
    assert not result.verification_issues[0].resolved


def test_page_failure_scenario_keeps_successful_pages_and_reports_failure():
    result = _run(F.PAGE_FAILURE)
    assert result.status == DocumentStatus.PARTIAL
    assert result.successful_pages == (1, 2)
    assert result.failed_pages == (3,)
    # The Khewat that only appears on the failed page must not silently
    # vanish as if it never existed -- it's simply absent from this partial
    # read, which the pipeline reports via failed_pages, not by omission.
    assert result.document is not None
    assert [k.khewat_number for k in result.document.khewats] == ["45/40"]


def test_failed_scenario_produces_no_document():
    result = _run(F.FAILED)
    assert result.status == DocumentStatus.FAILED
    assert result.document is None
    assert not result.succeeded


def test_every_registered_scenario_matches_its_declared_expected_status():
    for scenario in F.SCENARIOS.values():
        result = _run(scenario)
        assert result.status == scenario.expected_status, scenario.key


def test_blank_page_png_is_a_valid_minimal_png():
    data = F.blank_page_png()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_page_svg_data_uri_is_well_formed():
    uri = F.page_svg_data_uri(F.PAGE_1)
    assert uri.startswith("data:image/svg+xml;base64,")
