from patwari_agent import (
    ExtractionStatus,
    FardQueryEngine,
    MutationStatus,
    MutationType,
    RemarkCategory,
    RemarkTarget,
    reconcile,
    run_axiom_gates,
)
from tests.factories import (
    make_area,
    make_document,
    make_khasra,
    make_khatauni,
    make_khewat,
    make_mutation,
    make_owner,
    make_remark,
)


def _engine(document):
    return FardQueryEngine(reconcile(document, run_axiom_gates(document)))


# ---------------------------------------------------------------------
# owners
# ---------------------------------------------------------------------

def test_list_owners_reports_all_owners():
    owner_a = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Ram s/o Shyam")
    owner_b = make_owner("OWN-2", "KHW-1", "1/2", raw_owner_name_parentage="Sita d/o Ram")
    khewat = make_khewat("KHW-1", owners=[owner_a, owner_b])
    answer = _engine(make_document(khewats=[khewat])).list_owners()
    assert "Ram s/o Shyam" in answer.record_says
    assert "Sita d/o Ram" in answer.record_says
    assert not answer.uncertain


def test_list_owners_abstains_when_none_present():
    answer = _engine(make_document()).list_owners()
    assert answer.uncertain


def test_find_owners_case_insensitive_substring():
    owner = make_owner("OWN-1", "KHW-1", "1/1", raw_owner_name_parentage="Gurpreet Singh s/o Jagtar Singh")
    khewat = make_khewat("KHW-1", owners=[owner])
    engine = _engine(make_document(khewats=[khewat]))
    assert engine.find_owners("gurpreet") == [owner]
    assert engine.find_owners("nonexistent") == []


def test_owner_share_abstains_on_no_match():
    answer = _engine(make_document()).owner_share("Nobody")
    assert answer.uncertain
    assert "No owner matching" in answer.record_says


def test_owner_share_abstains_on_ambiguous_match():
    owner_a = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh")
    owner_b = make_owner("OWN-2", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh Jr")
    khewat = make_khewat("KHW-1", owners=[owner_a, owner_b])
    answer = _engine(make_document(khewats=[khewat])).owner_share("Ram Singh")
    assert answer.uncertain
    assert "more than one owner" in answer.record_says


def test_owner_share_reports_record_and_calculated_separately():
    owner = make_owner("OWN-1", "KHW-1", "2/4", raw_owner_name_parentage="Ram Singh")
    khewat = make_khewat("KHW-1", owners=[owner])
    answer = _engine(make_document(khewats=[khewat])).owner_share("Ram Singh")
    assert "2/4" in answer.record_says
    assert "1/2" in answer.calculated  # normalized by parse_fraction
    assert not answer.uncertain


def test_owner_share_flags_uncertain_status():
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh", status=ExtractionStatus.UNCERTAIN)
    khewat = make_khewat("KHW-1", owners=[owner])
    answer = _engine(make_document(khewats=[khewat])).owner_share("Ram Singh")
    assert answer.uncertain


# ---------------------------------------------------------------------
# land / area, including the multi-Khatauni non-double-counting rule
# ---------------------------------------------------------------------

def test_owner_land_calculates_proportional_share_of_khewat_total():
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    answer = _engine(make_document(khewats=[khewat])).owner_land("Ram Singh")
    assert not answer.uncertain
    assert "5 kanal 0 marla 0 sarsahi" in answer.calculated


def test_owner_land_never_double_counts_across_multiple_khataunis():
    """The same rule enforced at AG-03, re-verified at the query layer:
    a Khewat with two Khataunis (5 kanal each) must report 10 kanal
    total, not 20, and an owner's 1/2 share must be 5 kanal, not 10."""
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh")
    khatauni_a = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=5))
    khatauni_b = make_khatauni("KHT-2", "KHW-1", recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni_a, khatauni_b])
    answer = _engine(make_document(khewats=[khewat])).owner_land("Ram Singh")
    assert "10 kanal 0 marla 0 sarsahi" in answer.record_says
    assert "5 kanal 0 marla 0 sarsahi" in answer.calculated


def test_owner_share_flags_verification_required_when_approved_mutation_supersedes():
    """Regression: found via the offline demo run. owner_share's calculated
    value is arithmetically correct 'as recorded', but if an approved
    mutation supersedes that record, the answer must be flagged uncertain
    -- not just mention it in prose -- so a UI can key off it."""
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Sample Owner")
    khewat = make_khewat("KHW-1", owners=[owner])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED)
    answer = _engine(make_document(khewats=[khewat], mutations=[mutation])).owner_share("Sample Owner")
    assert answer.uncertain
    assert "approved mutation" in answer.uncertainty_reason.lower()
    # The calculation itself is still shown -- it's correct "as recorded".
    assert answer.calculated is not None


def test_owner_land_flags_verification_required_when_approved_mutation_supersedes():
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Sample Owner")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED)
    answer = _engine(make_document(khewats=[khewat], mutations=[mutation])).owner_land("Sample Owner")
    assert answer.uncertain
    assert "approved mutation" in answer.uncertainty_reason.lower()
    assert answer.calculated is not None  # still shown, just flagged


def test_owner_land_not_flagged_uncertain_when_only_pending_mutation_exists():
    """A pending (unsanctioned) mutation must NOT flip the verification
    flag -- the Pending Mutation Rule says active ownership is unchanged."""
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Sample Owner")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.PENDING)
    answer = _engine(make_document(khewats=[khewat], mutations=[mutation])).owner_land("Sample Owner")
    assert not answer.uncertain


def test_owner_land_abstains_when_khatauni_area_incomplete():
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh")
    khatauni_a = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=5))
    khatauni_b = make_khatauni("KHT-2", "KHW-1", recorded_area=None)  # missing
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni_a, khatauni_b])
    answer = _engine(make_document(khewats=[khewat])).owner_land("Ram Singh")
    assert answer.uncertain
    assert answer.calculated is None


def test_total_area_for_specific_khewat():
    khatauni_a = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=3))
    khatauni_b = make_khatauni("KHT-2", "KHW-1", recorded_area=make_area(kanal=4))
    khewat = make_khewat("KHW-1", khataunis=[khatauni_a, khatauni_b])
    answer = _engine(make_document(khewats=[khewat])).total_area("KHW-1")
    assert "7 kanal 0 marla 0 sarsahi" in answer.calculated


def test_total_area_across_whole_document():
    khatauni_1 = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=2))
    khewat_1 = make_khewat("KHW-1", khataunis=[khatauni_1])
    khatauni_2 = make_khatauni("KHT-2", "KHW-2", recorded_area=make_area(kanal=3))
    khewat_2 = make_khewat("KHW-2", khataunis=[khatauni_2])
    answer = _engine(make_document(khewats=[khewat_1, khewat_2])).total_area()
    assert "5 kanal 0 marla 0 sarsahi" in answer.calculated


# ---------------------------------------------------------------------
# khasra context
# ---------------------------------------------------------------------

def test_owner_khasra_context_lists_khasras_with_caveat():
    owner = make_owner("OWN-1", "KHW-1", "1/1", raw_owner_name_parentage="Ram Singh")
    khasra = make_khasra("KHS-1", "KHT-1")
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra])
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    answer = _engine(make_document(khewats=[khewat])).owner_khasra_context("Ram Singh")
    assert "1" in answer.record_says
    assert "not a direct owner-to-parcel assignment" in answer.interpretation


# ---------------------------------------------------------------------
# mutations
# ---------------------------------------------------------------------

def test_mutations_for_owner_reports_sale_with_scope():
    owner = make_owner("OWN-1", "KHW-1", "1/1", raw_owner_name_parentage="Ram Singh")
    khewat = make_khewat("KHW-1", owners=[owner])
    mutation = make_mutation(
        "MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
        mutation_type=MutationType.SALE, raw_text="sold 1/4 share to Sita",
    )
    answer = _engine(make_document(khewats=[khewat], mutations=[mutation])).mutations_for("Ram Singh")
    assert "Sale" in answer.record_says
    assert "sold 1/4 share to Sita" in answer.record_says
    assert "CAUTION" in answer.interpretation


def test_mutations_for_owner_reports_none_recorded():
    owner = make_owner("OWN-1", "KHW-1", "1/1", raw_owner_name_parentage="Ram Singh")
    khewat = make_khewat("KHW-1", owners=[owner])
    answer = _engine(make_document(khewats=[khewat])).mutations_for("Ram Singh")
    assert not answer.uncertain
    assert "No mutation" in answer.record_says


# ---------------------------------------------------------------------
# remarks / Column 8
# ---------------------------------------------------------------------

def test_remarks_for_khewat_returns_column8_text():
    khewat = make_khewat("KHW-1")
    remark = make_remark(RemarkTarget.KHEWAT, "KHW-1", RemarkCategory.INFORMATIONAL, text="boundary dispute noted")
    answer = _engine(make_document(khewats=[khewat], remarks=[remark])).remarks_for(RemarkTarget.KHEWAT, "KHW-1")
    assert "boundary dispute noted" in answer.record_says


# ---------------------------------------------------------------------
# simple-English explanation
# ---------------------------------------------------------------------

def test_explain_fard_simple_english_uses_only_structured_data():
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    answer = _engine(make_document(khewats=[khewat], village="Chak 5")).explain_fard_simple_english()
    assert "Chak 5" in answer.record_says
    assert "PASSED" in answer.record_says
    assert not answer.uncertain
