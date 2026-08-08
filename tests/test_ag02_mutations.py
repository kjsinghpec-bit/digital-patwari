from patwari_agent import MutationStatus, RemarkTarget, validate_ag02_linkage_and_integrity
from tests.factories import make_document, make_khewat, make_mutation, make_owner


def test_ag02_passes_when_mutation_target_resolves():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED)
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat], mutations=[mutation]))
    assert result.passed


def test_ag02_flags_unresolved_mutation_target():
    khewat = make_khewat("KHW-1")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-DOES-NOT-EXIST", MutationStatus.PENDING)
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat], mutations=[mutation]))
    assert not result.passed
    assert any(i.entity_type == "Mutation" for i in result.issues)


def test_ag02_flags_duplicate_mutation_ids():
    khewat = make_khewat("KHW-1")
    mutation_a = make_mutation("MUT-DUP", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED)
    mutation_b = make_mutation("MUT-DUP", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.PENDING)
    result = validate_ag02_linkage_and_integrity(make_document(khewats=[khewat], mutations=[mutation_a, mutation_b]))
    assert not result.passed
    assert any("Duplicate" in i.message and i.entity_type == "Mutation" for i in result.issues)
