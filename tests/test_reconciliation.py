import pytest

from patwari_agent import (
    ExtractionResult,
    MutationStatus,
    OwnershipStatus,
    RemarkTarget,
    reconcile,
    run_axiom_gates,
)
from digital_patwari.reconciliation import reconcile_extraction_result
from tests.factories import make_document, make_khewat, make_mutation, make_owner


def test_owner_with_no_mutation_is_as_recorded_active():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    document = make_document(khewats=[khewat])
    record = reconcile(document, run_axiom_gates(document))
    r = record.reconciliation_for_owner("OWN-1")
    assert r.status == OwnershipStatus.AS_RECORDED_ACTIVE
    assert r.mutation_ids == []


def test_approved_mutation_supersedes_owner_ownership():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED)
    document = make_document(khewats=[khewat], mutations=[mutation])
    record = reconcile(document, run_axiom_gates(document))
    r = record.reconciliation_for_owner("OWN-1")
    assert r.status == OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION
    assert r.mutation_ids == ["MUT-1"]


def test_pending_mutation_does_not_alter_active_ownership():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.PENDING)
    document = make_document(khewats=[khewat], mutations=[mutation])
    record = reconcile(document, run_axiom_gates(document))
    r = record.reconciliation_for_owner("OWN-1")
    assert r.status == OwnershipStatus.PENDING_MUTATION_NOTED
    # Crucially: the owner's recorded share is untouched -- reconciliation
    # never invents/rewrites a share value.
    assert owner.share_fraction == "1/1"


def test_khewat_level_approved_mutation_supersedes_all_its_owners():
    owner_a = make_owner("OWN-1", "KHW-1", "1/2")
    owner_b = make_owner("OWN-2", "KHW-1", "1/2")
    khewat = make_khewat("KHW-1", owners=[owner_a, owner_b])
    mutation = make_mutation("MUT-1", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED)
    document = make_document(khewats=[khewat], mutations=[mutation])
    record = reconcile(document, run_axiom_gates(document))
    assert record.reconciliation_for_owner("OWN-1").status == OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION
    assert record.reconciliation_for_owner("OWN-2").status == OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION
    assert record.reconciliation_for_khewat("KHW-1").status == OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION


def test_approved_mutation_takes_precedence_over_pending_when_both_present():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    approved = make_mutation("MUT-A", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED)
    pending = make_mutation("MUT-P", RemarkTarget.OWNER, "OWN-1", MutationStatus.PENDING)
    document = make_document(khewats=[khewat], mutations=[approved, pending])
    record = reconcile(document, run_axiom_gates(document))
    r = record.reconciliation_for_owner("OWN-1")
    assert r.status == OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION
    assert "MUT-A" in r.mutation_ids


def test_reconcile_extraction_result_rejects_failed_extraction():
    failed = ExtractionResult(document=None, validation_report=None, raw_llm_output=None, parser_errors=["boom"])
    with pytest.raises(ValueError):
        reconcile_extraction_result(failed)


def test_reconcile_extraction_result_succeeds_for_valid_extraction():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    document = make_document(khewats=[khewat])
    report = run_axiom_gates(document)
    result = ExtractionResult(document=document, validation_report=report, raw_llm_output="{}", parser_errors=[])
    record = reconcile_extraction_result(result)
    assert record.document is document
