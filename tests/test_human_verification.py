from digital_patwari.assembly import (
    apply_verification_response,
    assemble_page_observation,
    assemble_page_observations,
)
from digital_patwari.extraction import DocumentStatus, FardExtractionParser
from digital_patwari.derived_ownership import derive_document_ownership
from digital_patwari.validation import run_axiom_gates
from digital_patwari.observations import (
    FieldObservation,
    PageObservation,
    VerificationAction,
    VerificationIssue,
    VerificationReason,
    VerificationResponse,
    VerificationStatus,
)
from tests.factories import make_document, make_khatauni, make_khewat


def field(field_id, path, value, raw, page, column, reason=None):
    return FieldObservation(
        observation_id=field_id,
        field_path=path,
        entity_type="Khatauni" if "khataunis" in path else "Owner",
        extracted_value=value,
        raw_text=raw,
        confidence="low" if reason else "high",
        page_number=page,
        column_ref=column,
        evidence_region=f"page-{page}-column-{column}",
        verification_status="NEEDS_REVIEW" if reason else "NOT_REQUIRED",
        verification_reason=reason,
        uncertainty_reason="The printed characters admit more than one reading." if reason else None,
    )


def issue(issue_id, field_id, reason, question, proposed, alternatives, depends_on, critical=True):
    return VerificationIssue(
        issue_id=issue_id,
        field_observation_id=field_id,
        reason=reason,
        question=question,
        proposed_value=proposed,
        alternatives=alternatives,
        depends_on=depends_on,
        critical=critical,
    )


def page_observation(number, document, fields=None, issues=None, payload=None):
    return PageObservation(
        page_number=number,
        fields=fields or [],
        verification_issues=issues or [],
        canonical_payload=payload or document.model_dump(mode="json"),
    )


def test_ambiguous_khatauni_220_has_focused_ui_ready_issue():
    document = make_document(khewats=[make_khewat(
        "KHW-1", khewat_number="198/185",
        khataunis=[make_khatauni("KHT-1", "KHW-1", khatauni_number="220")],
    )])
    observed = field("khatauni-number", ["khewats", 0, "khataunis", 0, "khatauni_number"], "220", "22੦", 6, "2", "AMBIGUOUS")
    verification = issue(
        "verify-khatauni-220", "khatauni-number", "AMBIGUOUS",
        "Does the Khatauni number read 220?", "220", ["220", "228"],
        "This determines which cultivation account and Khasras are assembled together.",
    )

    result = assemble_page_observations([page_observation(6, document, [observed], [verification])])

    [found] = result.unresolved_critical_issues
    assert found.question == "Does the Khatauni number read 220?"
    assert found.alternatives == ["220", "228"]
    assert found.depends_on.startswith("This determines")


def test_blank_khewat_continuation_requires_structural_confirmation():
    document = make_document(khewats=[make_khewat(
        "continuation", khewat_number=None, continued_from_previous_page=True,
        khataunis=[make_khatauni("KHT-1", "continuation", khatauni_number="220")],
    )])
    observed = field("blank-khewat", ["khewats", 0, "continued_from_previous_page"], True, "", 6, "1", "STRUCTURAL_CONFLICT")
    verification = issue(
        "verify-blank-khewat", "blank-khewat", "STRUCTURAL_CONFLICT",
        "Does this blank Khewat cell continue the account from the previous page?",
        True, [True, False], "This controls whether Khatauni 220 belongs under the preceding Khewat.",
    )

    result = assemble_page_observations([page_observation(6, document, [observed], [verification])])

    assert result.unresolved_critical_issues[0].reason == VerificationReason.STRUCTURAL_CONFLICT


def malformed_owner_page():
    document = make_document(khewats=[make_khewat("KHW-1", khewat_number="10")])
    payload = document.model_dump(mode="json")
    payload["khewats"][0]["owners"] = [{
        "owner_id": "OWN-1",
        "khewat_id": "KHW-1",
        "raw_owner_name_parentage": "Citizen Owner",
        "raw_share_fraction": "1/4,20/65,20/220",
        "share_fraction": "1/4,20/65,20/220",
    }]
    observed = field(
        "owner-share", ["khewats", 0, "owners", 0, "share_fraction"],
        "1/4,20/65,20/220", "1/4,20/65,20/220", 1, "3", "INVALID_FORMAT",
    )
    verification = issue(
        "verify-owner-share", "owner-share", "INVALID_FORMAT",
        "What is Citizen Owner's fractional share?", None, ["1/4", "20/65", "20/220"],
        "Ownership-share and land-entitlement calculations depend on this value.",
    )
    return page_observation(1, document, [observed], [verification], payload)


def test_malformed_share_preserves_owner_row_and_excludes_only_calculation():
    page = malformed_owner_page()

    result = assemble_page_observation(page)

    owner = result.document.khewats[0].owners[0]
    assert owner.raw_owner_name_parentage == "Citizen Owner"
    assert owner.raw_share_fraction == "1/4,20/65,20/220"
    assert owner.share_fraction is None
    assert owner.status.value == "uncertain"
    assert result.verification_issues[0].reason == VerificationReason.INVALID_FORMAT
    report = run_axiom_gates(result.document)
    ag01 = next(gate for gate in report.gates if gate.gate_id == "AG-01")
    assert any("excluded this owner" in found.message for found in ag01.issues)
    derived = derive_document_ownership(result.document)
    assert next(iter(derived.values())).positions[0].derivation_failed


def test_invalid_repeated_header_does_not_discard_valid_page_body():
    first = page_observation(1, make_document(khewats=[make_khewat("KHW-1", khewat_number="198/185")]))
    continuation_document = make_document(khewats=[make_khewat(
        "KHW-2", khewat_number=None, continued_from_previous_page=True,
        khataunis=[make_khatauni("KHT-2", "KHW-2", khatauni_number="220")],
    )])
    bad_payload = continuation_document.model_dump(mode="json")
    bad_payload["document_header"] = {"village": "unreadable"}
    raw_header = field("page2-header", ["document_header"], None, "ਧੁੰਦਲਾ header", 2, "header", "UNREADABLE")
    second = page_observation(2, continuation_document, [raw_header], payload=bad_payload)

    result = assemble_page_observations([first, second])

    assert result.document.document_header.village == "Test Village"
    assert result.successful_pages == (1, 2)
    assert result.document.khewats[0].khataunis[0].khatauni_number == "220"
    assert second.fields[0].raw_text == "ਧੁੰਦਲਾ header"
    assert any("repeated header missing/invalid" in warning for warning in result.warnings)


def test_correction_reassembles_without_ai_and_preserves_audit_evidence():
    original = malformed_owner_page()
    response = VerificationResponse(
        issue_id="verify-owner-share",
        action=VerificationAction.SELECT_ALTERNATIVE,
        selected_alternative="1/4",
        verifier_id="citizen-7",
        verification_session_id="session-9",
    )

    applied = apply_verification_response([original], response)

    owner = applied.assembly.document.khewats[0].owners[0]
    assert owner.share_fraction == "1/4"
    assert owner.status.value == "present"
    corrected_field = applied.observations[0].fields[0]
    assert corrected_field.extracted_value == "1/4,20/65,20/220"
    assert corrected_field.corrected_value == "1/4"
    assert corrected_field.verification_status == VerificationStatus.CORRECTED
    assert applied.record.original_value == "1/4,20/65,20/220"
    assert applied.record.verifier_id == "citizen-7"
    assert applied.observations[0].verification_history[0].timestamp is not None
    assert applied.assembly.unresolved_critical_issues == ()


class Provider:
    cache_identity = "offline-provider"

    def __init__(self, page):
        self.page = page

    def extract_structured(self, **kwargs):
        return self.page.model_dump(mode="json")


def test_unresolved_critical_issue_prevents_complete_status(tmp_path):
    image = tmp_path / "fard_1.png"
    image.write_bytes(b"\x89PNG\r\n")
    page = malformed_owner_page()

    result = FardExtractionParser(provider=Provider(page), max_page_retries=0).extract([image])

    assert result.status == DocumentStatus.PARTIAL
    assert result.status not in {DocumentStatus.COMPLETE, DocumentStatus.COMPLETE_WITH_WARNINGS}
    assert result.verification_issues[0].critical


def test_no_trustworthy_header_keeps_body_but_marks_document_partial(tmp_path):
    image = tmp_path / "fard_1.png"
    image.write_bytes(b"\x89PNG\r\n")
    document = make_document(khewats=[make_khewat("KHW-1", khewat_number="77")])
    bad_payload = document.model_dump(mode="json")
    bad_payload["document_header"] = {"village": "only-one-field"}
    page = page_observation(1, document, payload=bad_payload)

    result = FardExtractionParser(provider=Provider(page), max_page_retries=0).extract([image])

    assert result.status == DocumentStatus.PARTIAL
    assert result.document.khewats[0].khewat_number == "77"
    assert result.document.document_header.village == "[verification required]"
    assert any(issue.issue_id == "verify-document-header" for issue in result.verification_issues)
