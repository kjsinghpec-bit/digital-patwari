import pytest

from digital_patwari.assembly import (
    apply_structural_correction,
    confirm_structural_correction,
)
from digital_patwari.observations import (
    FieldObservation,
    PageObservation,
    StructuralConfirmation,
    StructuralCorrectionRequest,
    StructuralOperationType,
    VerificationStatus,
)
from tests.factories import make_document, make_khewat, make_owner


OWNERS_PATH = ["khewats", 0, "owners"]


def page_with_owner_rows(rows, raw_text=None):
    document = make_document(khewats=[make_khewat("KHW-1", khewat_number="10")])
    payload = document.model_dump(mode="json")
    payload["khewats"][0]["owners"] = rows
    fields = []
    if raw_text is not None:
        fields.append(FieldObservation(
            observation_id="combined-owner-evidence",
            field_path=[*OWNERS_PATH, 0, "share_fraction"],
            entity_type="Owner",
            entity_id="AI-COMBINED",
            extracted_value=raw_text,
            raw_text=raw_text,
            confidence="low",
            page_number=1,
            column_ref="3",
            evidence_region="column-3-owner-block",
            verification_status="NEEDS_REVIEW",
            verification_reason="STRUCTURAL_CONFLICT",
            uncertainty_reason="Several owners and shares appear combined into one AI row.",
        ))
    return PageObservation(page_number=1, fields=fields, canonical_payload=payload)


def owner_row(owner_id, name, share):
    return {
        "owner_id": owner_id,
        "khewat_id": "KHW-1",
        "raw_owner_name_parentage": name,
        "raw_share_fraction": share,
        "share_fraction": share,
    }


def request(operation_id, operation, **overrides):
    values = dict(
        operation_id=operation_id,
        operation=operation,
        page_number=1,
        target_list_path=OWNERS_PATH,
        operator_id="reviewer-1",
        verification_session_id="structural-session-1",
        human_reason="The source geometry shows a different row structure.",
    )
    values.update(overrides)
    return StructuralCorrectionRequest(**values)


def test_split_combined_owner_share_evidence_into_typed_rows_and_confirm():
    combined_raw = "1/4,20/65,20/220"
    original = page_with_owner_rows([owner_row(
        "AI-COMBINED", "Owner A; Owner B; Owner C", combined_raw,
    )], raw_text=combined_raw)
    command = request(
        "split-owner-1",
        StructuralOperationType.SPLIT_ROW,
        row_indices=[0],
        corrected_rows=[
            owner_row("OWN-A", "Owner A", "1/4"),
            owner_row("OWN-B", "Owner B", "20/65"),
            owner_row("OWN-C", "Owner C", "20/220"),
        ],
    )

    applied = apply_structural_correction([original], command)

    assert original.canonical_payload["khewats"][0]["owners"][0]["share_fraction"] == combined_raw
    assert original.structural_history == []
    assert [owner.share_fraction for owner in applied.assembly.document.khewats[0].owners] == ["1/4", "4/13", "1/11"]
    assert applied.record.original_rows[0]["raw_share_fraction"] == combined_raw
    assert combined_raw in applied.record.original_raw_evidence
    assert applied.record.verification_status == VerificationStatus.NEEDS_REVIEW
    assert applied.assembly.unresolved_critical_issues[0].issue_id == "confirm-structural-split-owner-1"
    assert applied.affected_pages == (1,)

    confirmed = confirm_structural_correction(
        applied.observations,
        StructuralConfirmation(
            operation_id="split-owner-1",
            verifier_id="reviewer-2",
            verification_session_id="confirmation-session",
        ),
    )
    assert confirmed.record.verification_status == VerificationStatus.CONFIRMED
    assert confirmed.record.confirmed_by == "reviewer-2"
    assert confirmed.assembly.unresolved_critical_issues == ()
    assert combined_raw in confirmed.observations[0].structural_history[0].original_raw_evidence


def test_merge_separated_fragments_into_one_valid_owner_row():
    original = page_with_owner_rows([
        owner_row("FRAGMENT-1", "Harjit Singh", "1/2"),
        owner_row("FRAGMENT-2", "s/o Mohan Singh", "1/2"),
    ])
    command = request(
        "merge-owner-1",
        StructuralOperationType.MERGE_ROWS,
        row_indices=[0, 1],
        corrected_rows=[owner_row("OWN-1", "Harjit Singh s/o Mohan Singh", "1/2")],
    )

    applied = apply_structural_correction([original], command)

    owners = applied.assembly.document.khewats[0].owners
    assert len(owners) == 1
    assert owners[0].raw_owner_name_parentage == "Harjit Singh s/o Mohan Singh"
    assert len(applied.record.original_rows) == 2
    assert len(original.canonical_payload["khewats"][0]["owners"]) == 2


def test_add_row_requires_reason_and_adds_validated_row():
    original = page_with_owner_rows([owner_row("OWN-1", "Owner One", "1/2")])
    with pytest.raises(ValueError, match="human_reason"):
        request(
            "add-owner-invalid",
            StructuralOperationType.ADD_ROW,
            corrected_rows=[owner_row("OWN-2", "Owner Two", "1/2")],
            human_reason=None,
        )

    applied = apply_structural_correction([original], request(
        "add-owner-1",
        StructuralOperationType.ADD_ROW,
        corrected_rows=[owner_row("OWN-2", "Owner Two", "1/2")],
        human_reason="The second ruled owner row was missed by extraction.",
    ))

    assert [owner.raw_owner_name_parentage for owner in applied.assembly.document.khewats[0].owners] == [
        "Owner One", "Owner Two",
    ]
    assert applied.record.human_reason.startswith("The second ruled")


def test_delete_excludes_canonical_row_but_preserves_evidence_and_original():
    original = page_with_owner_rows([
        owner_row("OWN-1", "Real Owner", "1/1"),
        owner_row("DUPLICATE", "Repeated OCR Owner", "1/1"),
    ])
    applied = apply_structural_correction([original], request(
        "delete-owner-1",
        StructuralOperationType.DELETE_ROW,
        row_indices=[1],
        human_reason="This is an OCR duplicate of the preceding ruled row.",
    ))

    assert [owner.owner_id for owner in applied.assembly.document.khewats[0].owners] == ["OWN-1"]
    assert [row["owner_id"] for row in original.canonical_payload["khewats"][0]["owners"]] == ["OWN-1", "DUPLICATE"]
    assert applied.record.original_rows[0]["owner_id"] == "DUPLICATE"
    assert "Repeated OCR Owner" in applied.record.original_raw_evidence
    assert applied.record.corrected_rows == []


def test_update_field_is_audited_and_schema_validated():
    original = page_with_owner_rows([owner_row("OWN-1", "Mistyped Name", "1/1")])
    applied = apply_structural_correction([original], request(
        "update-owner-1",
        StructuralOperationType.UPDATE_FIELD,
        row_indices=[0],
        field_path=["raw_owner_name_parentage"],
        corrected_value="Correct Name",
    ))

    assert applied.assembly.document.khewats[0].owners[0].raw_owner_name_parentage == "Correct Name"
    assert applied.record.original_rows[0]["raw_owner_name_parentage"] == "Mistyped Name"


def test_invalid_corrected_row_is_rejected_before_assembly():
    original = page_with_owner_rows([owner_row("OWN-1", "Owner One", "1/1")])
    command = request(
        "add-invalid-owner",
        StructuralOperationType.ADD_ROW,
        corrected_rows=[{"owner_id": "missing-everything"}],
        human_reason="Testing schema rejection.",
    )

    with pytest.raises(ValueError, match="corrected owners row is invalid"):
        apply_structural_correction([original], command)
