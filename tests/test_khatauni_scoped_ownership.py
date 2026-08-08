"""Regression suite for the Khatauni-scoped ownership bug found while
manually reconciling a real Fard (Khewat 219, samples/real_fard/Chaman
Lal Sanghol.pdf): a Khewat can be split into Khataunis with entirely
DISJOINT owner groups, each independently summing to 1 within its own
Khatauni -- not one owner pool spanning the whole Khewat.

This fixture is anonymized/generalized from that structural pattern
(no real names, no expected-answer numbers hard-coded from the real
Fard). The bug and the fix are both about the general rule, not about
reproducing one specific person's figure.

Structural pattern:
  Khewat KHW-DUAL
    Khatauni KHT-A (10 Kanal): Owner P (1/2, scoped to A), Owner Q (1/2, scoped to A)
    Khatauni KHT-B (6 Kanal):  Owner R (1/1, scoped to B)

  Owner P has ZERO stake in Khatauni B. Correct land for P is
  1/2 x 10 Kanal = 5 Kanal -- not 1/2 x (10+6) Kanal = 8 Kanal.
"""
from __future__ import annotations

from patwari_agent import (
    FardQueryEngine,
    reconcile,
    run_axiom_gates,
)
from tests.factories import make_area, make_document, make_khatauni, make_khewat, make_owner


def _build_dual_khatauni_khewat():
    khatauni_a = make_khatauni("KHT-A", "KHW-DUAL", recorded_area=make_area(kanal=10))
    khatauni_b = make_khatauni("KHT-B", "KHW-DUAL", recorded_area=make_area(kanal=6))

    owner_p = make_owner("OWN-P", "KHW-DUAL", "1/2", khatauni_id="KHT-A",
                          raw_owner_name_parentage="Owner P (scoped to Khatauni A)")
    owner_q = make_owner("OWN-Q", "KHW-DUAL", "1/2", khatauni_id="KHT-A",
                          raw_owner_name_parentage="Owner Q (scoped to Khatauni A)")
    owner_r = make_owner("OWN-R", "KHW-DUAL", "1/1", khatauni_id="KHT-B",
                          raw_owner_name_parentage="Owner R (scoped to Khatauni B)")

    khewat = make_khewat("KHW-DUAL", owners=[owner_p, owner_q, owner_r],
                          khataunis=[khatauni_a, khatauni_b])
    return make_document(khewats=[khewat])


def test_owner_land_uses_only_the_owners_own_khatauni_not_the_whole_khewat():
    """THE regression: Owner P's share (1/2) is scoped to Khatauni A (10
    Kanal) only. Correct land = 5 Kanal. Before the fix, owner_land()
    multiplied the fraction against khewat_total_area_sarsahi() -- the
    WHOLE Khewat (10+6=16 Kanal) -- giving a wrong 8 Kanal, silently
    attributing land from Khatauni B that Owner P has no stake in."""
    document = _build_dual_khatauni_khewat()
    record = reconcile(document, run_axiom_gates(document))
    engine = FardQueryEngine(record)

    answer = engine.owner_land("Owner P")

    assert not answer.uncertain, answer.uncertainty_reason
    assert "5 kanal" in answer.calculated.lower(), (
        f"Expected Owner P's land to be scoped to Khatauni A's own 10 Kanal "
        f"(1/2 = 5 Kanal), got: {answer.calculated!r}"
    )
    assert "16 kanal" not in answer.record_says.lower(), (
        "Owner P's answer should not present the whole-Khewat 16 Kanal total "
        "as if it were the relevant base for a Khatauni-scoped owner."
    )


def test_owner_land_for_second_khatauni_scoped_owner_is_also_correct():
    document = _build_dual_khatauni_khewat()
    record = reconcile(document, run_axiom_gates(document))
    engine = FardQueryEngine(record)

    answer = engine.owner_land("Owner R")
    assert not answer.uncertain, answer.uncertainty_reason
    assert "6 kanal" in answer.calculated.lower()


def test_khatauni_scoped_ag01_validates_each_khatauni_independently():
    """AG-01 must check each Khatauni's owner subset against that
    Khatauni's own total_share (both default to 1/1 here), NOT pool
    every owner in the Khewat together (which would wrongly expect
    1/2+1/2+1/1 = 2 to equal 1 and fail everything)."""
    document = _build_dual_khatauni_khewat()
    report = run_axiom_gates(document)
    ag01 = next(g for g in report.gates if g.gate_id == "AG-01")

    assert ag01.passed, [i.message for i in ag01.issues]
    assert ag01.checked_entities == 2  # one check per Khatauni-scoped group


def test_khatauni_scoped_ag01_still_catches_a_real_mismatch_within_one_khatauni():
    khatauni_a = make_khatauni("KHT-A", "KHW-DUAL", recorded_area=make_area(kanal=10))
    owner_p = make_owner("OWN-P", "KHW-DUAL", "1/2", khatauni_id="KHT-A")
    owner_q = make_owner("OWN-Q", "KHW-DUAL", "1/4", khatauni_id="KHT-A")  # shares don't sum to 1
    khewat = make_khewat("KHW-DUAL", owners=[owner_p, owner_q], khataunis=[khatauni_a])
    document = make_document(khewats=[khewat])

    report = run_axiom_gates(document)
    ag01 = next(g for g in report.gates if g.gate_id == "AG-01")
    assert not ag01.passed
    assert ag01.issues[0].entity_type == "Khatauni"
    assert ag01.issues[0].entity_id == "KHT-A"


def test_double_counting_safeguard_still_holds_for_pooled_khewat_wide_owners():
    """The OPPOSITE safeguard, unchanged: an owner with no khatauni_id
    (pooled across the whole Khewat) must still see the whole Khewat's
    area computed by summing each Khatauni's own area exactly once --
    never doubled just because there are multiple Khataunis."""
    khatauni_a = make_khatauni("KHT-A", "KHW-POOL", recorded_area=make_area(kanal=5))
    khatauni_b = make_khatauni("KHT-B", "KHW-POOL", recorded_area=make_area(kanal=5))
    owner = make_owner("OWN-1", "KHW-POOL", "1/1")  # no khatauni_id -> pooled, whole-Khewat
    khewat = make_khewat("KHW-POOL", owners=[owner], khataunis=[khatauni_a, khatauni_b])
    document = make_document(khewats=[khewat])

    record = reconcile(document, run_axiom_gates(document))
    engine = FardQueryEngine(record)
    answer = engine.owner_land("Owner OWN-1")

    assert "10 kanal" in answer.calculated.lower()  # 5+5, not 5*2 khataunis*2 = 20
    assert "20 kanal" not in answer.calculated.lower()


def test_owner_khasra_context_scoped_to_owners_own_khatauni_only():
    """A Khatauni-scoped owner should not be told about Khasras under a
    Khatauni they hold no share in."""
    from patwari_agent import Khasra

    khasra_a = Khasra(khasra_id="KHS-A1", khasra_number="A1", khatauni_id="KHT-A",
                       area_kanal_marla=make_area(kanal=10))
    khasra_b = Khasra(khasra_id="KHS-B1", khasra_number="B1", khatauni_id="KHT-B",
                       area_kanal_marla=make_area(kanal=6))
    khatauni_a = make_khatauni("KHT-A", "KHW-DUAL", khasras=[khasra_a], recorded_area=make_area(kanal=10))
    khatauni_b = make_khatauni("KHT-B", "KHW-DUAL", khasras=[khasra_b], recorded_area=make_area(kanal=6))
    owner_p = make_owner("OWN-P", "KHW-DUAL", "1/2", khatauni_id="KHT-A")
    owner_q = make_owner("OWN-Q", "KHW-DUAL", "1/2", khatauni_id="KHT-A")
    khewat = make_khewat("KHW-DUAL", owners=[owner_p, owner_q], khataunis=[khatauni_a, khatauni_b])
    document = make_document(khewats=[khewat])

    record = reconcile(document, run_axiom_gates(document))
    engine = FardQueryEngine(record)
    answer = engine.owner_khasra_context("OWN-P")

    assert "A1" in answer.record_says
    assert "B1" not in answer.record_says
