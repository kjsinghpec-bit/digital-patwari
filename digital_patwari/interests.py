"""Person-land relationships that are NOT undivided Khewat ownership.

A person's relationship to land is not one-dimensional. Digital Patwari
must keep these distinct, because each is calculated completely
differently:

  A. KHEWAT-SCOPED OWNERSHIP      -> ownership.py (fraction x scope area)
  B. CULTIVATION / POSSESSION     -> resolve_cultivation_interests (this module)
  C. SPECIFIC-KHASRA INTEREST     -> resolve_parcel_interests (this module)
  D. MUTATION-DERIVED OWNERSHIP   -> derived_ownership.py

One person may appear in several capacities at once (owner AND cultivator,
or owner in one Khewat AND purchaser of specific parcels in another). Those
appearances are different interests, and must never be silently summed as
if each were separate land.

Two errors this module exists to prevent:

  1. Multiplying a specific-Khasra purchaser's interest against the WHOLE
     Khewat. Someone who bought named Khasras holds those parcels' areas --
     not a fraction of everything in the Khewat.

  2. Inferring ownership from possession or possession from ownership.
     Khud Kasht means the owner is recorded as cultivating; a tenant
     (muzara) cultivating is not thereby an owner; and an owner whose
     purchase has not yet reached the possession column is still an owner.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from digital_patwari.models import (
    CultivationInterest,
    CultivationRelationship,
    DigitalPatwariDocument,
    InterestScope,
    Khasra,
    Khewat,
    MutationStatus,
    ParcelInterest,
)


@dataclass(frozen=True)
class ResolvedParcelInterest:
    """A specific-parcel interest with its area computed from the named
    parcels only -- never from the enclosing Khewat's total."""
    interest: ParcelInterest
    resolved_khasras: tuple[Khasra, ...]
    area_sarsahi: int
    area_complete: bool
    unresolved_khasra_ids: tuple[str, ...]
    # Set when the interest came from a mutation that is not sanctioned --
    # the parcels are claimed, not confirmed.
    mutation_status: MutationStatus | None = None

    @property
    def is_operative(self) -> bool:
        return self.mutation_status is None or self.mutation_status == MutationStatus.APPROVED


def _khasra_index(khewat: Khewat) -> dict[str, Khasra]:
    return {
        khasra.khasra_id: khasra
        for khatauni in khewat.khataunis
        for khasra in khatauni.khasras
    }


def resolve_parcel_interests(
    document: DigitalPatwariDocument,
    person_name: str | None = None,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> list[ResolvedParcelInterest]:
    """Resolve specific-Khasra interests to their own parcel areas.

    The area is the SUM OF THE NAMED PARCELS, each counted exactly once --
    the whole-Khewat total never enters this calculation at all."""
    khewats_by_id = {k.khewat_id: k for k in document.khewats}
    mutations_by_id = {m.mutation_id: m for m in document.mutations}

    resolved: list[ResolvedParcelInterest] = []
    for interest in document.parcel_interests:
        if person_name is not None and person_name.strip().lower() not in interest.person_name.strip().lower():
            continue

        khewat = khewats_by_id.get(interest.khewat_id)
        index = _khasra_index(khewat) if khewat else {}

        found: list[Khasra] = []
        unresolved: list[str] = []
        seen_ids: set[str] = set()
        for khasra_id in interest.khasra_ids:
            khasra = index.get(khasra_id)
            if khasra is None:
                unresolved.append(khasra_id)
                continue
            # Guard the physical-area-uniqueness invariant even against a
            # duplicated id inside a single interest's own list.
            if khasra.khasra_id in seen_ids:
                continue
            seen_ids.add(khasra.khasra_id)
            found.append(khasra)

        calculable_found = [k for k in found if k.area_kanal_marla.calculable]
        area_sarsahi = sum(
            value for value in (
                k.area_kanal_marla.total_sarsahi(marla_per_kanal, sarsahi_per_marla)
                for k in calculable_found
            ) if value is not None
        )
        mutation = mutations_by_id.get(interest.mutation_id) if interest.mutation_id else None

        resolved.append(ResolvedParcelInterest(
            interest=interest,
            resolved_khasras=tuple(found),
            area_sarsahi=area_sarsahi,
            area_complete=not unresolved and len(calculable_found) == len(found) and bool(found),
            unresolved_khasra_ids=tuple(unresolved),
            mutation_status=mutation.status if mutation else None,
        ))
    return resolved


def resolve_cultivation_interests(
    document: DigitalPatwariDocument, person_name: str | None = None
) -> list[CultivationInterest]:
    if person_name is None:
        return list(document.cultivation_interests)
    needle = person_name.strip().lower()
    return [c for c in document.cultivation_interests if needle in c.person_name.strip().lower()]


def is_khud_kasht(interest: CultivationInterest) -> bool:
    """Khud Kasht = the owner is recorded as self-cultivating.

    Only true when the record explicitly says so. Absence of a Khud Kasht
    marking must never be read as "not self-cultivated", and ownership must
    never be read as implying Khud Kasht."""
    return interest.relationship == CultivationRelationship.KHUD_KASHT


def classify_person_interest_scope(
    document: DigitalPatwariDocument, person_name: str
) -> InterestScope:
    """Classify how a named person holds land, across all evidence.

    Returns UNKNOWN_REQUIRES_VERIFICATION rather than guessing when the
    record supports no clear classification."""
    needle = person_name.strip().lower()

    has_ownership = any(
        needle in owner.raw_owner_name_parentage.strip().lower()
        for khewat in document.khewats
        for owner in khewat.owners
    )
    has_parcel = any(needle in p.person_name.strip().lower() for p in document.parcel_interests)
    has_cultivation = any(needle in c.person_name.strip().lower() for c in document.cultivation_interests)
    has_operative_mutation_gain = any(
        m.transferee_name and needle in m.transferee_name.strip().lower() and m.is_operative
        for m in document.mutations
    )

    signals = [has_ownership, has_parcel, has_cultivation or has_operative_mutation_gain]
    if sum(1 for s in signals if s) > 1:
        return InterestScope.MIXED_INTEREST
    if has_parcel:
        return InterestScope.SPECIFIC_KHASRA_INTEREST
    if has_ownership:
        return InterestScope.UNDIVIDED_KHEWAT_SHARE
    if has_operative_mutation_gain:
        return InterestScope.MUTATION_DERIVED_OWNERSHIP
    if has_cultivation:
        return InterestScope.CULTIVATION_POSSESSION_ONLY
    return InterestScope.UNKNOWN_REQUIRES_VERIFICATION


def cultivation_share_reconciliation(
    document: DigitalPatwariDocument, khatauni_id: str
) -> tuple[Fraction, bool]:
    """Sum the stated cultivation shares for one Khatauni.

    Reconciled INDEPENDENTLY of ownership shares. A cultivation total that
    differs from the ownership total is not automatically an error --
    ownership and possession are genuinely different things and may
    legitimately differ."""
    total = Fraction(0)
    found_any = False
    for interest in document.cultivation_interests:
        if interest.khatauni_id != khatauni_id:
            continue
        fraction = interest.fraction
        if fraction is not None:
            total += fraction
            found_any = True
    return total, found_any
