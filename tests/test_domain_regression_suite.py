"""TEST 1, 2, 3, 4, 5, 17, 18 from the domain-model incorporation request.
Generic structural regressions -- no real Fard names or numbers are
hard-coded; the Chaman Lal case is used only as the structural pattern
that motivated TEST 3/4 (rules 6, 7, 25, 30)."""
from patwari_agent import (
    FardQueryEngine,
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
    make_owner,
    make_remark,
)


def _engine(document):
    return FardQueryEngine(reconcile(document, run_axiom_gates(document)))


# ---------------------------------------------------------------------
# TEST 1 -- one Khewat, one Khatauni, one Khasra: the simplest case.
# ---------------------------------------------------------------------

def test_1_simplest_single_khewat_khatauni_khasra():
    khasra = make_khasra("KHS-1", "KHT-1", kanal=5)
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra], recorded_area=make_area(kanal=5))
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    document = make_document(khewats=[khewat])

    report = run_axiom_gates(document)
    assert report.passed
    answer = _engine(document).owner_land("OWN-1")
    assert "5 kanal" in answer.calculated.lower()


# ---------------------------------------------------------------------
# TEST 2 -- one Khewat, multiple Khataunis: no double counting.
# ---------------------------------------------------------------------

def test_2_multiple_khataunis_no_double_counting():
    khatauni_a = make_khatauni("KHT-A", "KHW-1", recorded_area=make_area(kanal=6))
    khatauni_b = make_khatauni("KHT-B", "KHW-1", recorded_area=make_area(kanal=9))
    owner = make_owner("OWN-1", "KHW-1", "1/1")
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni_a, khatauni_b])
    document = make_document(khewats=[khewat])

    answer = _engine(document).owner_land("OWN-1")
    assert "15 kanal" in answer.calculated.lower()  # 6+9, not 6*2 or 9*2
    assert "18 kanal" not in answer.calculated.lower()


# ---------------------------------------------------------------------
# TEST 3 -- omitting a Khatauni would understate the Khewat area. Proves
# the fix in the same direction as the double-count guard: traversing
# ALL Khataunis is required, not just convenient.
# ---------------------------------------------------------------------

def test_3_omitting_a_khatauni_understates_total_area():
    khatauni_a = make_khatauni("KHT-A", "KHW-1", recorded_area=make_area(kanal=7))
    khatauni_b = make_khatauni("KHT-B", "KHW-1", recorded_area=make_area(kanal=4))

    complete_khewat = make_khewat("KHW-1", khataunis=[khatauni_a, khatauni_b])
    incomplete_khewat = make_khewat("KHW-1", khataunis=[khatauni_a])  # KHT-B omitted

    complete_engine = _engine(make_document(khewats=[complete_khewat]))
    incomplete_engine = _engine(make_document(khewats=[incomplete_khewat]))

    complete_total = complete_engine.total_area("KHW-1").calculated
    incomplete_total = incomplete_engine.total_area("KHW-1").calculated

    assert "11 kanal" in complete_total.lower()
    assert "7 kanal" in incomplete_total.lower()
    assert complete_total != incomplete_total  # the omission is not silently absorbed


# ---------------------------------------------------------------------
# TEST 4 -- one owner across multiple Khewats: total must include every
# Khewat (rule 25), generalized from the Chaman Lal case. No hard-coded
# name or expected figure from that real case.
# ---------------------------------------------------------------------

def test_4_owner_total_sums_every_khewat_they_appear_in():
    same_name = "Generic Owner s/o Generic Father"
    khewat_a = make_khewat("KHW-A", owners=[make_owner("OWN-A", "KHW-A", "1/2", raw_owner_name_parentage=same_name)],
                            khataunis=[make_khatauni("KHT-A", "KHW-A", recorded_area=make_area(kanal=10))])
    khewat_b = make_khewat("KHW-B", owners=[make_owner("OWN-B", "KHW-B", "1/4", raw_owner_name_parentage=same_name)],
                            khataunis=[make_khatauni("KHT-B", "KHW-B", recorded_area=make_area(kanal=8))])
    khewat_c = make_khewat("KHW-C", owners=[make_owner("OWN-C", "KHW-C", "1/1", raw_owner_name_parentage=same_name)],
                            khataunis=[make_khatauni("KHT-C", "KHW-C", recorded_area=make_area(kanal=3))])
    document = make_document(khewats=[khewat_a, khewat_b, khewat_c])

    answer = _engine(document).owner_total_across_khewats("Generic Owner")
    assert not answer.uncertain, answer.uncertainty_reason
    # 1/2*10 + 1/4*8 + 1/1*3 = 5 + 2 + 3 = 10 Kanal
    assert "10 kanal" in answer.calculated.lower()
    assert "khewat khw-a" in answer.record_says.lower()
    assert "khewat khw-b" in answer.record_says.lower()
    assert "khewat khw-c" in answer.record_says.lower()

    # owner_land (single-Khewat lookup) must still abstain by default --
    # this new method is opt-in, it does not change owner_land's safety.
    single_answer = _engine(document).owner_land("Generic Owner")
    assert single_answer.uncertain


# ---------------------------------------------------------------------
# TEST 5 -- similar owner names with different parentage must not merge,
# whether looked up via owner_land or the new multi-Khewat tracer.
# ---------------------------------------------------------------------

def test_5_similar_names_different_parentage_not_merged():
    owner_a = make_owner("OWN-A", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh s/o Fateh Singh")
    owner_b = make_owner("OWN-B", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh s/o Gurdev Singh")
    khewat = make_khewat("KHW-1", owners=[owner_a, owner_b],
                          khataunis=[make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))])
    document = make_document(khewats=[khewat])

    engine = _engine(document)
    assert engine.owner_share("Ram Singh").uncertain  # ambiguous, correctly refuses to guess
    assert engine.owner_total_across_khewats("Ram Singh").uncertain


# ---------------------------------------------------------------------
# TEST 17 -- Khewat, Khatauni, Khasra, and Mutation numbers must never be
# confused even when the printed digits coincide.
# ---------------------------------------------------------------------

def test_17_same_numeric_id_across_entity_types_is_not_confused():
    from patwari_agent import MutationStatus, validate_ag02_linkage_and_integrity
    from tests.factories import make_mutation

    # Khewat, Khatauni, Khasra, and Mutation all happen to be labeled "44"
    # (a real, common situation -- Fards reuse small integers across
    # different number series). A Remark/Mutation declaring target_type
    # KHATAUNI with target_id "44" must resolve against the KHATAUNI id
    # space only, never accidentally match the KHEWAT or KHASRA sharing
    # that same digit string.
    khasra = make_khasra("44", "44", kanal=5)  # khasra_id "44" under khatauni_id "44"
    khatauni = make_khatauni("44", "44", khasras=[khasra])  # khatauni_id "44" under khewat_id "44"
    khewat = make_khewat("44", khataunis=[khatauni])  # khewat_id "44"
    mutation = make_mutation("44", RemarkTarget.KHATAUNI, "44", MutationStatus.APPROVED)  # mutation_id "44"
    document = make_document(khewats=[khewat], mutations=[mutation])

    result = validate_ag02_linkage_and_integrity(document)
    # The Khatauni-targeted mutation correctly resolves against Khatauni "44"
    # specifically (not a false collision across the other entity types).
    assert result.passed

    # Now point a mutation at target_type KHEWAT with target_id "44" -- it
    # must resolve against the KHEWAT id space (which also happens to
    # contain "44"), not be confused with the Khatauni/Khasra/Mutation
    # sharing that digit string. This should also pass, proving each
    # id-space is checked independently rather than one pooled string set.
    mutation_khewat = make_mutation("45", RemarkTarget.KHEWAT, "44", MutationStatus.APPROVED)
    document_2 = make_document(khewats=[khewat], mutations=[mutation, mutation_khewat])
    result_2 = validate_ag02_linkage_and_integrity(document_2)
    assert result_2.passed


# ---------------------------------------------------------------------
# TEST 18 -- a duplicated physical Khasra (same khasra_id appearing under
# two Khataunis) must be caught, not silently double-counted.
# ---------------------------------------------------------------------

def test_18_duplicated_khasra_id_across_khataunis_is_flagged_not_double_counted():
    from patwari_agent import validate_ag02_linkage_and_integrity

    khasra = make_khasra("KHS-DUP", "KHT-A", kanal=5)
    khasra_again = make_khasra("KHS-DUP", "KHT-B", kanal=5)  # same khasra_id, different Khatauni -- a bug
    khatauni_a = make_khatauni("KHT-A", "KHW-1", khasras=[khasra])
    khatauni_b = make_khatauni("KHT-B", "KHW-1", khasras=[khasra_again])
    khewat = make_khewat("KHW-1", khataunis=[khatauni_a, khatauni_b])
    document = make_document(khewats=[khewat])

    result = validate_ag02_linkage_and_integrity(document)
    assert not result.passed
    assert any("Duplicate" in i.message and i.entity_type == "Khasra" for i in result.issues)
