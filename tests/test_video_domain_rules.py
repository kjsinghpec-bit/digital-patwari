"""Regression suite for the consolidated domain-intelligence upgrade
(Videos 2/3 + Nirmal Patwari lesson), numbered to match the requested
TEST 1-50 list.

Nothing here hard-codes a real person, a real Khewat number, or a known
real-world answer. Where a real case motivated a test (the multi-Khewat /
multi-Khatauni traversal failure), only its STRUCTURAL PATTERN is
reproduced with synthetic values.
"""
from fractions import Fraction

import pytest

from patwari_agent import (
    AreaScope,
    CultivationRelationship,
    DocumentLayout,
    ExtractionStatus,
    FardQueryEngine,
    InterestScope,
    Khasra,
    MutationStatus,
    MutationType,
    PartyRole,
    RemarkTarget,
    add_shares,
    area_from_share,
    classify_person_interest_scope,
    cultivation_share_reconciliation,
    decimal_kanal_to_kanal_marla,
    decimal_marla_to_marla_sarsahi,
    derive_khewat_ownership,
    format_fraction,
    is_khud_kasht,
    is_operative_for_derived_ownership,
    reconcile,
    resolve_parcel_interests,
    run_axiom_gates,
    share_denominator_matches_total_marla,
    subtract_shares,
    validate_ag05_mutation_share_area_consistency,
    validate_ag06_area_observation_scopes,
    validate_ag07_parcel_interest_resolution,
)
from tests.factories import (
    make_area,
    make_area_observation,
    make_cultivation_interest,
    make_document,
    make_khasra,
    make_khatauni,
    make_khewat,
    make_mutation,
    make_owner,
    make_parcel_interest,
    make_source,
)


def _engine(document):
    return FardQueryEngine(reconcile(document, run_axiom_gates(document)))


# =====================================================================
# TESTS 1-2 : document layout
# =====================================================================

def test_1_modern_8_column_layout_is_representable():
    document = make_document(layout=DocumentLayout.MODERN_8_COLUMN)
    assert document.layout == DocumentLayout.MODERN_8_COLUMN


def test_2_legacy_layout_is_not_forced_into_modern_semantics():
    document = make_document(layout=DocumentLayout.LEGACY_12_COLUMN)
    assert document.layout == DocumentLayout.LEGACY_12_COLUMN
    # Default must be UNKNOWN, never an assumed modern 8-column reading.
    assert make_document().layout == DocumentLayout.UNKNOWN_LAYOUT


# =====================================================================
# TESTS 3-8 : multi-page / multi-Khewat scoping
# =====================================================================

def test_3_khewat_spanning_multiple_pages_keeps_one_identity():
    kht_a = make_khatauni("KHT-A", "KHW-1", recorded_area=make_area(kanal=5),
                           source=make_source(page=1))
    kht_b = make_khatauni("KHT-B", "KHW-1", recorded_area=make_area(kanal=5),
                           source=make_source(page=2))
    khewat = make_khewat("KHW-1", owners=[make_owner("OWN-1", "KHW-1", "1/1")],
                          khataunis=[kht_a, kht_b])
    answer = _engine(make_document(khewats=[khewat])).total_area("KHW-1")
    assert "10 kanal" in answer.calculated.lower()  # one Khewat, both pages


def test_4_khatauni_change_across_pages_does_not_merge_khataunis():
    kht_a = make_khatauni("KHT-A", "KHW-1", recorded_area=make_area(kanal=5), source=make_source(page=1))
    kht_b = make_khatauni("KHT-B", "KHW-1", recorded_area=make_area(kanal=7), source=make_source(page=2))
    khewat = make_khewat("KHW-1", khataunis=[kht_a, kht_b])
    document = make_document(khewats=[khewat])
    report = run_axiom_gates(document)
    assert report.passed
    assert len(khewat.khataunis) == 2


def test_5_khewat_change_across_pages_prevents_owner_bleed():
    khewat_a = make_khewat("KHW-A", owners=[make_owner("OWN-A", "KHW-A", "1/1")],
                            khataunis=[make_khatauni("KHT-A", "KHW-A", recorded_area=make_area(kanal=4))])
    khewat_b = make_khewat("KHW-B", owners=[make_owner("OWN-B", "KHW-B", "1/1")],
                            khataunis=[make_khatauni("KHT-B", "KHW-B", recorded_area=make_area(kanal=6))])
    engine = _engine(make_document(khewats=[khewat_a, khewat_b]))
    # OWN-A's land must come only from KHW-A, never bleed KHW-B's area in.
    assert "4 kanal" in engine.owner_land("OWN-A").calculated.lower()
    assert "6 kanal" in engine.owner_land("OWN-B").calculated.lower()


def test_6_owner_share_stays_scoped_to_its_own_khewat():
    khewat_a = make_khewat("KHW-A", owners=[make_owner("OWN-A", "KHW-A", "1/2")],
                            khataunis=[make_khatauni("KHT-A", "KHW-A", recorded_area=make_area(kanal=10))])
    khewat_b = make_khewat("KHW-B", owners=[make_owner("OWN-B", "KHW-B", "1/2")],
                            khataunis=[make_khatauni("KHT-B", "KHW-B", recorded_area=make_area(kanal=100))])
    engine = _engine(make_document(khewats=[khewat_a, khewat_b]))
    answer = engine.owner_land("OWN-A")
    assert "5 kanal" in answer.calculated.lower()      # 1/2 of KHW-A's 10
    assert "50 kanal" not in answer.calculated.lower()  # never KHW-B's 100


def test_7_same_person_in_multiple_khewats_is_found_in_all():
    same = "Person X s/o Y"
    khewats = [
        make_khewat(f"KHW-{i}", owners=[make_owner(f"OWN-{i}", f"KHW-{i}", "1/1", raw_owner_name_parentage=same)],
                     khataunis=[make_khatauni(f"KHT-{i}", f"KHW-{i}", recorded_area=make_area(kanal=2))])
        for i in range(1, 4)
    ]
    engine = _engine(make_document(khewats=khewats))
    assert len(engine.find_owners("Person X")) == 3


def test_8_owner_total_includes_every_khewat():
    same = "Person X s/o Y"
    khewats = [
        make_khewat(f"KHW-{i}", owners=[make_owner(f"OWN-{i}", f"KHW-{i}", "1/1", raw_owner_name_parentage=same)],
                     khataunis=[make_khatauni(f"KHT-{i}", f"KHW-{i}", recorded_area=make_area(kanal=2))])
        for i in range(1, 4)
    ]
    answer = _engine(make_document(khewats=khewats)).owner_total_across_khewats("Person X")
    assert "6 kanal" in answer.calculated.lower()  # 2+2+2, each Khewat once


# =====================================================================
# TESTS 9-14 : area scope, double counting, omission
# =====================================================================

def test_9_multiple_khataunis_do_not_double_count_khewat_area():
    khataunis = [make_khatauni(f"KHT-{i}", "KHW-1", recorded_area=make_area(kanal=20)) for i in range(3)]
    khewat = make_khewat("KHW-1", owners=[make_owner("OWN-1", "KHW-1", "1/1")], khataunis=khataunis)
    answer = _engine(make_document(khewats=[khewat])).owner_land("OWN-1")
    assert "60 kanal" in answer.calculated.lower()   # 20+20+20 real distinct land
    # The classic bug is 20 x 3 khataunis applied to a 20-Kanal Khewat.
    khewat_single = make_khewat("KHW-2", owners=[make_owner("OWN-2", "KHW-2", "1/1")],
                                 khataunis=[make_khatauni("KHT-S", "KHW-2", recorded_area=make_area(kanal=20))])
    single = _engine(make_document(khewats=[khewat_single])).owner_land("OWN-2")
    assert "20 kanal" in single.calculated.lower()
    assert "60 kanal" not in single.calculated.lower()


def test_10_later_khatauni_cannot_be_omitted():
    full = make_khewat("KHW-1", khataunis=[
        make_khatauni("KHT-A", "KHW-1", recorded_area=make_area(kanal=6)),
        make_khatauni("KHT-B", "KHW-1", recorded_area=make_area(kanal=9)),
    ])
    partial = make_khewat("KHW-1", khataunis=[make_khatauni("KHT-A", "KHW-1", recorded_area=make_area(kanal=6))])
    assert "15 kanal" in _engine(make_document(khewats=[full])).total_area("KHW-1").calculated.lower()
    assert "6 kanal" in _engine(make_document(khewats=[partial])).total_area("KHW-1").calculated.lower()


def test_11_repeated_printed_total_is_flagged_not_added():
    observations = [
        make_area_observation("OBS-1", AreaScope.KHEWAT_TOTAL, kanal=20, khewat_id="KHW-1"),
        make_area_observation("OBS-2", AreaScope.KHEWAT_TOTAL, kanal=20, khewat_id="KHW-1"),  # restated
    ]
    document = make_document(area_observations=observations)
    result = validate_ag06_area_observation_scopes(document)
    assert any("Repeated identical area total" in i.message for i in result.issues)


def test_12_khasra_areas_reconcile_with_khatauni_total():
    khasras = [make_khasra("KHS-1", "KHT-1", kanal=3), make_khasra("KHS-2", "KHT-1", kanal=2)]
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=khasras, recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    report = run_axiom_gates(make_document(khewats=[khewat]))
    ag03 = next(g for g in report.gates if g.gate_id == "AG-03")
    assert ag03.passed


def test_13_khasra_total_mismatch_raises_warning():
    khasras = [make_khasra("KHS-1", "KHT-1", kanal=3)]
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=khasras, recorded_area=make_area(kanal=9))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    report = run_axiom_gates(make_document(khewats=[khewat]))
    ag03 = next(g for g in report.gates if g.gate_id == "AG-03")
    assert not ag03.passed


def test_14_khasra_area_scope_is_distinct_from_khewat_total_scope():
    observations = [
        make_area_observation("OBS-KHASRA", AreaScope.KHASRA_AREA, kanal=5, khasra_id="KHS-1"),
        make_area_observation("OBS-TOTAL", AreaScope.KHEWAT_TOTAL, kanal=5, khewat_id="KHW-1"),
    ]
    result = validate_ag06_area_observation_scopes(make_document(area_observations=observations))
    # Same numeric value, different scope -> NOT a duplicate, and never summed.
    assert not result.issues


# =====================================================================
# TESTS 15-17 : Murabba, ownership vs cultivation, Khud Kasht
# =====================================================================

def test_15_murabba_and_khasra_remain_distinct():
    khasra = Khasra(khasra_id="KHS-1", khasra_number="18", murabba_number="31",
                     khatauni_id="KHT-1", area_kanal_marla=make_area(kanal=8))
    assert khasra.murabba_number == "31"
    assert khasra.khasra_number == "18"
    assert khasra.murabba_number != khasra.khasra_number


def test_16_ownership_and_cultivation_remain_separate():
    owner = make_owner("OWN-1", "KHW-1", "1/1", raw_owner_name_parentage="Owner Person")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    cultivation = make_cultivation_interest("CUL-1", "Tenant Person", "KHW-1", "KHT-1",
                                             relationship=CultivationRelationship.MUZARA)
    document = make_document(khewats=[khewat], cultivation_interests=[cultivation])

    # The tenant is NOT an owner...
    assert classify_person_interest_scope(document, "Tenant Person") == InterestScope.CULTIVATION_POSSESSION_ONLY
    # ...and the owner is not automatically the cultivator.
    assert classify_person_interest_scope(document, "Owner Person") == InterestScope.UNDIVIDED_KHEWAT_SHARE


def test_17_khud_kasht_recognised_only_when_explicitly_recorded():
    khud = make_cultivation_interest("CUL-1", "P", "KHW-1", "KHT-1",
                                      relationship=CultivationRelationship.KHUD_KASHT)
    unknown = make_cultivation_interest("CUL-2", "Q", "KHW-1", "KHT-1")
    assert is_khud_kasht(khud)
    assert not is_khud_kasht(unknown)  # absence is not evidence of the opposite


# =====================================================================
# TESTS 18-23 : undivided share vs specific parcel
# =====================================================================

def test_18_undivided_khewat_share_calculation():
    owner = make_owner("OWN-1", "KHW-1", "1/4")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=20))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    answer = _engine(make_document(khewats=[khewat])).owner_land("OWN-1")
    assert "5 kanal" in answer.calculated.lower()


def test_19_specific_khasra_purchaser_area_is_sum_of_named_parcels():
    khasras = [make_khasra("KHS-1", "KHT-1", kanal=3), make_khasra("KHS-2", "KHT-1", kanal=2),
                make_khasra("KHS-3", "KHT-1", kanal=15)]
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=khasras, recorded_area=make_area(kanal=20))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    interest = make_parcel_interest("PI-1", "Buyer Person", "KHW-1", ["KHS-1", "KHS-2"])
    document = make_document(khewats=[khewat], parcel_interests=[interest])

    resolved = resolve_parcel_interests(document, "Buyer Person")
    assert len(resolved) == 1
    assert resolved[0].area_sarsahi == make_area(kanal=5).total_sarsahi()  # 3+2, named parcels only


def test_20_specific_khasra_purchase_not_multiplied_against_whole_khewat():
    khasras = [make_khasra("KHS-1", "KHT-1", kanal=2), make_khasra("KHS-2", "KHT-1", kanal=98)]
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=khasras, recorded_area=make_area(kanal=100))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    interest = make_parcel_interest("PI-1", "Buyer Person", "KHW-1", ["KHS-1"])
    document = make_document(khewats=[khewat], parcel_interests=[interest])

    answer = _engine(document).parcel_interests_for("Buyer Person")
    assert "2 kanal" in answer.calculated.lower()
    assert "100 kanal" not in answer.calculated.lower()
    assert "not a fraction of the whole khewat" in answer.interpretation.lower()


def test_21_mushtari_is_purchaser_not_automatically_whole_khewat_owner():
    from patwari_agent import lookup_term

    term = lookup_term("Mushtari")
    assert term is not None
    assert "purchaser" in term.meaning.lower()
    assert "does not establish that the person owns the whole khewat" in term.caution.lower()

    khasra = make_khasra("KHS-1", "KHT-1", kanal=2)
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra], recorded_area=make_area(kanal=50))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    interest = make_parcel_interest("PI-1", "Buyer", "KHW-1", ["KHS-1"], role=PartyRole.TRANSFEREE)
    document = make_document(khewats=[khewat], parcel_interests=[interest])
    assert classify_person_interest_scope(document, "Buyer") == InterestScope.SPECIFIC_KHASRA_INTEREST


def test_22_cultivator_without_ownership_evidence_is_not_an_owner():
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    cultivation = make_cultivation_interest("CUL-1", "Only Cultivator", "KHW-1", "KHT-1",
                                             relationship=CultivationRelationship.MUZARA)
    document = make_document(khewats=[khewat], cultivation_interests=[cultivation])
    assert classify_person_interest_scope(document, "Only Cultivator") == InterestScope.CULTIVATION_POSSESSION_ONLY
    # And they have no Owner row at all.
    assert _engine(document).owner_land("Only Cultivator").uncertain


def test_23_same_transaction_in_multiple_places_is_not_counted_repeatedly():
    khasra = make_khasra("KHS-1", "KHT-1", kanal=4)
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra], recorded_area=make_area(kanal=4))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    mutation = make_mutation("MUT-1", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
                              mutation_type=MutationType.SALE, raw_text="sale of KHS-1")
    # The SAME purchase, named once as a parcel interest that points back at
    # the mutation. Resolution must yield the parcel area once, not twice.
    interest = make_parcel_interest("PI-1", "Buyer", "KHW-1", ["KHS-1"], mutation_id="MUT-1")
    document = make_document(khewats=[khewat], mutations=[mutation], parcel_interests=[interest])
    resolved = resolve_parcel_interests(document, "Buyer")
    assert sum(r.area_sarsahi for r in resolved) == make_area(kanal=4).total_sarsahi()


# =====================================================================
# TESTS 24-32 : base vs mutation vs derived ownership
# =====================================================================

def _khewat_with(owner_share: str, kanal: int = 20, owner_id: str = "OWN-1"):
    owner = make_owner(owner_id, "KHW-1", owner_share, raw_owner_name_parentage="Base Owner")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=kanal))
    return make_khewat("KHW-1", owners=[owner], khataunis=[khatauni]), owner


def test_24_base_jamabandi_ownership_preserved_after_mutation():
    khewat, owner = _khewat_with("1/4")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              mutation_type=MutationType.SALE, share_transferred="1/4",
                              transferee_name="Buyer", raw_text="sold entire share")
    document = make_document(khewats=[khewat], mutations=[mutation])
    result = derive_khewat_ownership(document, khewat)
    position = result.position_for_owner("OWN-1")
    assert position.base_share == Fraction(1, 4)      # history intact
    assert owner.share_fraction == "1/4"               # model untouched
    assert position.derived_share == Fraction(0)       # derived differs


def test_25_full_sanctioned_transfer_makes_derived_share_zero():
    khewat, _ = _khewat_with("1/4")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              share_transferred="1/4", transferee_name="Buyer", raw_text="whole share sold")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[mutation]), khewat)
    assert result.position_for_owner("OWN-1").derived_share == Fraction(0)


def test_26_partial_sanctioned_transfer_leaves_exact_remainder():
    khewat, _ = _khewat_with("404/934")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              share_transferred="200/934", transferee_name="Buyer", raw_text="part sold")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[mutation]), khewat)
    # 404/934 - 200/934 = 204/934, exactly (reduces to 102/467).
    assert result.position_for_owner("OWN-1").derived_share == Fraction(204, 934)


def test_27_purchaser_acquired_share_recorded():
    khewat, _ = _khewat_with("404/934")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              share_transferred="200/934", transferee_name="Acquirer", raw_text="part sold")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[mutation]), khewat)
    assert len(result.acquisitions) == 1
    assert result.acquisitions[0].acquired_share == Fraction(200, 934)


@pytest.mark.parametrize("status", [
    MutationStatus.ENTERED,
    MutationStatus.PRESENTED_FOR_VERIFICATION,
    MutationStatus.PENDING,
])
def test_28_non_sanctioned_mutation_is_not_applied(status):
    khewat, _ = _khewat_with("1/4")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", status,
                              share_transferred="1/4", raw_text="not yet sanctioned")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[mutation]), khewat)
    position = result.position_for_owner("OWN-1")
    assert position.derived_share == Fraction(1, 4)      # unchanged
    assert "MUT-1" in position.unapplied_mutation_ids


def test_29_presented_for_sanction_is_distinct_from_sanctioned():
    assert MutationStatus.PRESENTED_FOR_SANCTION != MutationStatus.APPROVED
    assert not is_operative_for_derived_ownership(MutationStatus.PRESENTED_FOR_SANCTION)
    assert is_operative_for_derived_ownership(MutationStatus.APPROVED)


def test_30_sanctioned_mutation_affects_derived_ownership():
    khewat, _ = _khewat_with("1/2")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              share_transferred="1/4", transferee_name="B", raw_text="sanctioned")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[mutation]), khewat)
    assert result.position_for_owner("OWN-1").derived_share == Fraction(1, 4)


def test_31_rejected_mutation_does_not_alter_derived_ownership():
    khewat, _ = _khewat_with("1/2")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.REJECTED,
                              share_transferred="1/4", raw_text="rejected")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[mutation]), khewat)
    assert result.position_for_owner("OWN-1").derived_share == Fraction(1, 2)


def test_32_multiple_chronological_mutations_apply_in_order():
    khewat, _ = _khewat_with("1/1")
    m1 = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                        share_transferred="1/4", transferee_name="B", sequence_index=1, raw_text="first")
    m2 = make_mutation("MUT-2", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                        share_transferred="1/2", transferee_name="C", sequence_index=2, raw_text="second")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[m2, m1]), khewat)
    position = result.position_for_owner("OWN-1")
    assert position.derived_share == Fraction(1, 4)  # 1 - 1/4 - 1/2
    # Applied in sequence order despite being supplied out of order.
    assert [e.mutation_id for e in position.applied_effects] == ["MUT-1", "MUT-2"]


def test_32b_transfer_exceeding_holding_abstains_instead_of_going_negative():
    khewat, _ = _khewat_with("1/4")
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              share_transferred="1/2", raw_text="impossible transfer")
    result = derive_khewat_ownership(make_document(khewats=[khewat], mutations=[mutation]), khewat)
    position = result.position_for_owner("OWN-1")
    assert position.derivation_failed
    assert position.derived_share == Fraction(1, 4)  # falls back to base, never negative


# =====================================================================
# TESTS 33-35 : reconciliation
# =====================================================================

def test_33_ownership_shares_reconciling_to_one_pass():
    owners = [
        make_owner("OWN-1", "KHW-1", "100/934"), make_owner("OWN-2", "KHW-1", "430/934"),
        make_owner("OWN-3", "KHW-1", "204/934"), make_owner("OWN-4", "KHW-1", "200/934"),
    ]
    khewat = make_khewat("KHW-1", owners=owners)
    report = run_axiom_gates(make_document(khewats=[khewat]))
    ag01 = next(g for g in report.gates if g.gate_id == "AG-01")
    assert ag01.passed
    assert add_shares("100/934", "430/934", "204/934", "200/934") == "1/1"


def test_34_ownership_shares_not_summing_to_one_trigger_reconciliation_failure():
    owners = [make_owner("OWN-1", "KHW-1", "1/2"), make_owner("OWN-2", "KHW-1", "1/4")]
    khewat = make_khewat("KHW-1", owners=owners)
    report = run_axiom_gates(make_document(khewats=[khewat]))
    ag01 = next(g for g in report.gates if g.gate_id == "AG-01")
    assert not ag01.passed
    # Reported as a mathematical inconsistency, not a legal invalidity claim.
    assert "do not sum" in ag01.issues[0].message.lower()


def test_35_ownership_and_girdawari_may_differ_without_forced_correction():
    owner = make_owner("OWN-1", "KHW-1", "1/1", raw_owner_name_parentage="Owner P")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    # Cultivation held by someone else entirely, in a different fraction.
    cultivation = make_cultivation_interest("CUL-1", "Cultivator Q", "KHW-1", "KHT-1",
                                             relationship=CultivationRelationship.MUZARA,
                                             share_fraction="1/2")
    document = make_document(khewats=[khewat], cultivation_interests=[cultivation])

    report = run_axiom_gates(document)
    ag01 = next(g for g in report.gates if g.gate_id == "AG-01")
    assert ag01.passed  # ownership reconciles on its own terms

    total, found = cultivation_share_reconciliation(document, "KHT-1")
    assert found and total == Fraction(1, 2)  # reconciled independently, no forced match


# =====================================================================
# TESTS 36-42 : exact arithmetic
# =====================================================================

def test_36_46k14m_is_934_marla():
    assert make_area(kanal=46, marla=14).total_marla() == 934


def test_37_15k16m_is_316_marla():
    assert make_area(kanal=15, marla=16).total_marla() == 316


def test_38_exact_fraction_multiplication():
    total_sarsahi = make_area(kanal=46, marla=14).total_sarsahi()  # 934 marla
    assert area_from_share(total_sarsahi, "404/934") == Fraction(404 * 9)


def test_39_exact_fraction_subtraction():
    assert subtract_shares("404/934", "200/934") == "102/467"  # == 204/934 exactly
    assert Fraction(subtract_shares("404/934", "200/934")) == Fraction(204, 934)
    assert subtract_shares("1/4", "1/4") == "0/1"
    with pytest.raises(ValueError):
        subtract_shares("1/4", "1/2")


def test_40_decimal_kanal_conversion():
    kanal, marla = decimal_kanal_to_kanal_marla("10.55")
    assert (kanal, marla) == (10, Fraction(11))


def test_41_fractional_marla_to_sarsahi():
    marla, sarsahi = decimal_marla_to_marla_sarsahi("11.5")
    assert (marla, sarsahi) == (11, Fraction(9, 2))


def test_42_no_floating_point_corruption_in_intermediate_values():
    # A chain that would drift under float arithmetic stays exact.
    total = make_area(kanal=46, marla=14).total_sarsahi()
    third = area_from_share(total, "1/3")
    assert third * 3 == Fraction(total)
    assert isinstance(third, Fraction)


def test_42b_share_denominator_is_never_used_as_the_area_shortcut():
    """The denominator of 404/934 equals the 934-Marla total in one teaching
    example. That coincidence is detectable but must never be generalized."""
    total_sarsahi = make_area(kanal=46, marla=14).total_sarsahi()
    assert share_denominator_matches_total_marla("404/934", total_sarsahi)      # coincidence exists
    assert not share_denominator_matches_total_marla("1/4", total_sarsahi)      # and does not generalize
    # The engine computes area properly regardless of the coincidence.
    assert area_from_share(total_sarsahi, "1/4") == Fraction(total_sarsahi, 4)


# =====================================================================
# TESTS 43-44 : mutation share vs area
# =====================================================================

def test_43_mutation_share_and_area_reconcile():
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=20))
    khewat = make_khewat("KHW-1", owners=[make_owner("OWN-1", "KHW-1", "1/1")], khataunis=[khatauni])
    mutation = make_mutation("MUT-1", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
                              share_transferred="1/4", area_transferred=make_area(kanal=5),
                              raw_text="1/4 = 5 kanal of 20")
    result = validate_ag05_mutation_share_area_consistency(make_document(khewats=[khewat], mutations=[mutation]))
    assert result.passed


def test_44_mutation_share_area_mismatch_triggers_warning():
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=20))
    khewat = make_khewat("KHW-1", owners=[make_owner("OWN-1", "KHW-1", "1/1")], khataunis=[khatauni])
    mutation = make_mutation("MUT-1", RemarkTarget.KHEWAT, "KHW-1", MutationStatus.APPROVED,
                              share_transferred="1/4", area_transferred=make_area(kanal=9),  # should be 5
                              raw_text="inconsistent")
    result = validate_ag05_mutation_share_area_consistency(make_document(khewats=[khewat], mutations=[mutation]))
    assert not result.passed
    assert "MUTATION_SHARE_AREA_MISMATCH" in result.issues[0].message


# =====================================================================
# TESTS 45-49 : completeness, abstention, identifier hygiene
# =====================================================================

def test_45_incomplete_page_set_detected():
    owner = make_owner("OWN-1", "KHW-1", "1/1", source=make_source(page=2, total_pages=8))
    khewat = make_khewat("KHW-1", owners=[owner])
    report = run_axiom_gates(make_document(khewats=[khewat]))
    ag04 = next(g for g in report.gates if g.gate_id == "AG-04")
    assert not ag04.passed


def test_46_unreadable_share_causes_abstention_not_guessing():
    owner = make_owner("OWN-1", "KHW-1", "1/2", raw_owner_name_parentage="Smudged Person",
                        status=ExtractionStatus.ILLEGIBLE)
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    answer = _engine(make_document(khewats=[khewat])).owner_land("Smudged Person")
    assert answer.uncertain
    assert answer.calculated is None


def test_47_similar_names_different_parentage_not_merged():
    owner_a = make_owner("OWN-A", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh s/o Fateh Singh")
    owner_b = make_owner("OWN-B", "KHW-1", "1/2", raw_owner_name_parentage="Ram Singh s/o Gurdev Singh")
    khewat = make_khewat("KHW-1", owners=[owner_a, owner_b],
                          khataunis=[make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))])
    engine = _engine(make_document(khewats=[khewat]))
    assert engine.owner_land("Ram Singh").uncertain
    assert engine.owner_total_across_khewats("Ram Singh").uncertain


def test_48_identifiers_of_different_kinds_are_never_confused():
    # Same digit string "7" used as Khewat, Khatauni, Khasra and Mutation id.
    khasra = make_khasra("7", "7", kanal=5)
    khatauni = make_khatauni("7", "7", khasras=[khasra], recorded_area=make_area(kanal=5))
    khewat = make_khewat("7", khataunis=[khatauni])
    mutation = make_mutation("7", RemarkTarget.KHATAUNI, "7", MutationStatus.APPROVED)
    document = make_document(khewats=[khewat], mutations=[mutation])
    report = run_axiom_gates(document)
    ag02 = next(g for g in report.gates if g.gate_id == "AG-02")
    assert ag02.passed  # each id-space resolved independently


def test_49_one_physical_khasra_cannot_count_twice_in_one_calculation():
    khasra = make_khasra("KHS-1", "KHT-1", kanal=5)
    khatauni = make_khatauni("KHT-1", "KHW-1", khasras=[khasra], recorded_area=make_area(kanal=5))
    khewat = make_khewat("KHW-1", khataunis=[khatauni])
    # An interest naming the same parcel twice must contribute it once...
    interest = make_parcel_interest("PI-1", "Buyer", "KHW-1", ["KHS-1", "KHS-1"])
    document = make_document(khewats=[khewat], parcel_interests=[interest])
    resolved = resolve_parcel_interests(document, "Buyer")
    assert resolved[0].area_sarsahi == make_area(kanal=5).total_sarsahi()
    # ...and the duplication itself must be reported, not silently absorbed.
    ag07 = validate_ag07_parcel_interest_resolution(document)
    assert not ag07.passed
    assert any("more than once" in i.message for i in ag07.issues)


# =====================================================================
# TEST 50 : the "how much do they have NOW?" question
# =====================================================================

def test_50_current_position_distinguishes_base_mutation_and_derived():
    owner = make_owner("OWN-1", "KHW-1", "404/934", raw_owner_name_parentage="Current Owner")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=46, marla=14))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              mutation_type=MutationType.SALE, share_transferred="200/934",
                              transferee_name="Acquirer", raw_text="sanctioned partial sale")
    cultivation = make_cultivation_interest("CUL-1", "Current Owner", "KHW-1", "KHT-1",
                                             relationship=CultivationRelationship.KHUD_KASHT)
    document = make_document(khewats=[khewat], mutations=[mutation], cultivation_interests=[cultivation])

    answer = _engine(document).owner_current_position("Current Owner")

    assert not answer.uncertain
    # All four states present and distinct.
    assert "404/934" in answer.record_says                       # base, as printed
    assert "200/934" in answer.mutation_effect                   # what the mutation did
    assert "204/934" in answer.derived_position                  # derived, over the printed denominator
    assert "khud_kasht" in answer.possession_position.lower()    # possession, separately
    assert "never rewritten" in answer.interpretation.lower()


def test_50b_current_position_abstains_when_derivation_unsafe():
    owner = make_owner("OWN-1", "KHW-1", "1/4", raw_owner_name_parentage="Owner Z")
    khatauni = make_khatauni("KHT-1", "KHW-1", recorded_area=make_area(kanal=10))
    khewat = make_khewat("KHW-1", owners=[owner], khataunis=[khatauni])
    mutation = make_mutation("MUT-1", RemarkTarget.OWNER, "OWN-1", MutationStatus.APPROVED,
                              share_transferred="1/2", raw_text="transfers more than held")
    answer = _engine(make_document(khewats=[khewat], mutations=[mutation])).owner_current_position("Owner Z")
    assert answer.uncertain
    assert answer.derived_position is None
