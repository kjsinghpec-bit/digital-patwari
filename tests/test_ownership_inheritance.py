"""Regression suite for the Khewat-default / Khatauni-override ownership
resolution rule (digital_patwari/ownership.py).

Domain rule, generalized from the real Fard finding (Khewat 219 of
samples/real_fard/Chaman Lal Sanghol.pdf had two Khataunis with disjoint
owner groups) -- no expected numbers or names from that real case are
hard-coded here, only the structural pattern:

  1. Khewat-level ownership (Owner.khatauni_id is None) is the DEFAULT.
  2. Khatauni-level ownership (Owner.khatauni_id set) is an OVERRIDE for
     that specific Khatauni.
  3. A Khatauni with no owner row of its own INHERITS the Khewat-level
     default -- it is not "unknown" or "zero ownership".
  4. Precedence: explicit Khatauni ownership overrides the Khewat default,
     but only where it actually exists.
  5/6. Area calculation must traverse every Khatauni, resolve exactly one
     governing owner-group per Khatauni, and never count a Khatauni's area
     under two different owner-groups (omission and double-counting are
     both failures).
"""
from __future__ import annotations

from patwari_agent import (
    FardQueryEngine,
    OwnershipScope,
    inheriting_khataunis,
    khatauni_governance,
    reconcile,
    resolve_owner_entitlements,
    run_axiom_gates,
)
from tests.factories import make_area, make_document, make_khatauni, make_khewat, make_owner


def _engine(document):
    return FardQueryEngine(reconcile(document, run_axiom_gates(document)))


# ---------------------------------------------------------------------
# TEST A -- pure Khewat ownership, multiple Khataunis, no Khatauni-level
# owners at all. Expected: Khewat ownership applies normally, and the
# whole Khewat area is counted exactly once (not once per Khatauni).
# ---------------------------------------------------------------------

def test_a_pure_khewat_ownership_applies_to_whole_khewat_once():
    khatauni_1 = make_khatauni("KHT-1", "KHW-A", recorded_area=make_area(kanal=6))
    khatauni_2 = make_khatauni("KHT-2", "KHW-A", recorded_area=make_area(kanal=4))
    owner = make_owner("OWN-1", "KHW-A", "1/2")  # no khatauni_id -> Khewat-level default
    khewat = make_khewat("KHW-A", owners=[owner], khataunis=[khatauni_1, khatauni_2])
    document = make_document(khewats=[khewat])

    governance = khatauni_governance(khewat)
    assert governance == {"KHT-1": OwnershipScope.KHEWAT, "KHT-2": OwnershipScope.KHEWAT}
    assert {k.khatauni_id for k in inheriting_khataunis(khewat)} == {"KHT-1", "KHT-2"}

    answer = _engine(document).owner_land("OWN-1")
    assert not answer.uncertain, answer.uncertainty_reason
    # 1/2 of (6+4)=10 Kanal = 5 Kanal -- counted once, not per-Khatauni.
    assert "5 kanal" in answer.calculated.lower()


# ---------------------------------------------------------------------
# TEST B -- Chaman-Lal structural pattern: at least one Khatauni has its
# own explicit owner/share. Expected: that specific relationship governs
# the Khatauni's area, overriding what a broad Khewat-wide calculation
# would have produced.
# ---------------------------------------------------------------------

def test_b_explicit_khatauni_ownership_overrides_broad_khewat_calculation():
    khatauni_override = make_khatauni("KHT-OVERRIDE", "KHW-B", recorded_area=make_area(kanal=8))
    khatauni_other = make_khatauni("KHT-OTHER", "KHW-B", recorded_area=make_area(kanal=12))
    owner_scoped = make_owner("OWN-SCOPED", "KHW-B", "1/4", khatauni_id="KHT-OVERRIDE")
    owner_other = make_owner("OWN-OTHER", "KHW-B", "1/1", khatauni_id="KHT-OTHER")
    khewat = make_khewat("KHW-B", owners=[owner_scoped, owner_other],
                          khataunis=[khatauni_override, khatauni_other])
    document = make_document(khewats=[khewat])

    answer = _engine(document).owner_land("OWN-SCOPED")
    assert not answer.uncertain, answer.uncertainty_reason
    # Correct: 1/4 of KHT-OVERRIDE's own 8 Kanal = 2 Kanal.
    assert "2 kanal" in answer.calculated.lower()
    # A broad Khewat-wide calculation (1/4 of the whole 20 Kanal = 5 Kanal)
    # must NOT appear -- the explicit override, not the whole Khewat, governs.
    assert "5 kanal" not in answer.calculated.lower()


# ---------------------------------------------------------------------
# TEST C -- mixed inheritance: some Khataunis have explicit ownership,
# another has no owner entry at all. Expected: the ownerless Khatauni
# correctly inherits the Khewat-level ownership -- not "unknown" or zero.
# ---------------------------------------------------------------------

def test_c_khatauni_with_no_owner_entry_inherits_khewat_default():
    khatauni_explicit = make_khatauni("KHT-EXPLICIT", "KHW-C", recorded_area=make_area(kanal=8))
    khatauni_bare = make_khatauni("KHT-BARE", "KHW-C", recorded_area=make_area(kanal=6))  # no owner of its own
    owner_explicit = make_owner("OWN-EXPLICIT", "KHW-C", "1/1", khatauni_id="KHT-EXPLICIT")
    owner_default = make_owner("OWN-DEFAULT", "KHW-C", "1/2")  # Khewat-level default
    khewat = make_khewat("KHW-C", owners=[owner_explicit, owner_default],
                          khataunis=[khatauni_explicit, khatauni_bare])
    document = make_document(khewats=[khewat])

    governance = khatauni_governance(khewat)
    assert governance["KHT-EXPLICIT"] == OwnershipScope.KHATAUNI
    assert governance["KHT-BARE"] == OwnershipScope.KHEWAT  # inherited, not "unknown"

    answer = _engine(document).owner_land("OWN-DEFAULT")
    assert not answer.uncertain, answer.uncertainty_reason
    # OWN-DEFAULT inherits ONLY KHT-BARE (6 Kanal), not KHT-EXPLICIT (which
    # has its own owner): 1/2 of 6 Kanal = 3 Kanal.
    assert "3 kanal" in answer.calculated.lower()


# ---------------------------------------------------------------------
# TEST D -- no double counting: multiple Khataunis all inherit the
# Khewat-level ownership. The Khewat total must not be multiplied by the
# number of Khataunis.
# ---------------------------------------------------------------------

def test_d_multiple_inheriting_khataunis_not_multiplied():
    khataunis = [make_khatauni(f"KHT-{i}", "KHW-D", recorded_area=make_area(kanal=5)) for i in range(4)]
    owner = make_owner("OWN-1", "KHW-D", "1/1")  # Khewat-level default, inherited by all 4
    khewat = make_khewat("KHW-D", owners=[owner], khataunis=khataunis)
    document = make_document(khewats=[khewat])

    interests = resolve_owner_entitlements([owner], khewat)
    assert len(interests) == 1
    # 4 Khataunis x 5 Kanal each = 20 Kanal total, summed once each --
    # NOT 20 Kanal x 4 Khataunis = 80 Kanal.
    assert interests[0].area_sarsahi == 20 * 20 * 9  # 20 Kanal in sarsahi

    answer = _engine(document).owner_land("OWN-1")
    assert "20 kanal" in answer.calculated.lower()
    assert "80 kanal" not in answer.calculated.lower()


# ---------------------------------------------------------------------
# TEST E -- multiple explicit Khatauni interests: one real owner has
# different relevant interests across different Khataunis under the same
# Khewat. Expected: each area is calculated using the appropriate share
# and summed once, with no overlap.
# ---------------------------------------------------------------------

def test_e_same_owner_multiple_explicit_khatauni_interests_summed_once():
    khatauni_a = make_khatauni("KHT-A", "KHW-E", recorded_area=make_area(kanal=8))
    khatauni_b = make_khatauni("KHT-B", "KHW-E", recorded_area=make_area(kanal=12))
    same_name = "Owner Z s/o Test Father"
    owner_in_a = make_owner("OWN-Z-A", "KHW-E", "1/2", khatauni_id="KHT-A",
                             raw_owner_name_parentage=same_name)
    owner_in_b = make_owner("OWN-Z-B", "KHW-E", "1/3", khatauni_id="KHT-B",
                             raw_owner_name_parentage=same_name)
    khewat = make_khewat("KHW-E", owners=[owner_in_a, owner_in_b],
                          khataunis=[khatauni_a, khatauni_b])
    document = make_document(khewats=[khewat])

    interests = resolve_owner_entitlements([owner_in_a, owner_in_b], khewat)
    assert len(interests) == 2
    assert {i.khatauni_ids for i in interests} == {("KHT-A",), ("KHT-B",)}

    answer = _engine(document).owner_land("Owner Z")
    assert not answer.uncertain, answer.uncertainty_reason
    # 1/2 of 8 Kanal (KHT-A) + 1/3 of 12 Kanal (KHT-B) = 4 + 4 = 8 Kanal.
    assert "8 kanal" in answer.calculated.lower()
    # Neither sub-figure should be silently dropped -- both interests appear.
    assert "khatauni kht-a" in answer.record_says.lower()
    assert "khatauni kht-b" in answer.record_says.lower()
