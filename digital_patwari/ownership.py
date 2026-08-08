"""Ownership resolution: Khewat-level default vs. Khatauni-level override.

Domain rule (verified against a real Fard -- samples/real_fard/Chaman Lal
Sanghol.pdf, Khewat 198/185 with Khatauni 219, and generalized rather than hard-coded):

1. Khewat-level ownership (Owner.khatauni_id is None) is the DEFAULT. It
   applies to every Khatauni in that Khewat that has no owner row of its
   own.
2. Khatauni-level ownership (Owner.khatauni_id set) is an OVERRIDE. When a
   Khatauni has its own owner row(s), those govern that Khatauni's area
   exclusively -- the Khewat-level default does not also apply to it.
3. A Khatauni with no owner rows of its own is not "unknown" or "zero
   ownership" -- it inherits the Khewat-level default.
4. One real person can hold multiple ownership interests in one Khewat
   (a Khewat-level default row AND one or more Khatauni-level override
   rows, each a separate Owner record since owner_id is globally unique).
   Their total entitlement is the sum of each interest's own area,
   computed against the correct scope, with no area counted twice.

This module resolves (2)-(4) once, in one place, so query.py and
validation.py consume the same governance decision instead of each
re-deriving their own fallback logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from digital_patwari.models import Khatauni, Khewat, Owner


class OwnershipScope(str, Enum):
    KHEWAT = "khewat"      # Khewat-level default, applied via inheritance
    KHATAUNI = "khatauni"  # explicit Khatauni-level override


def khatauni_governance(khewat: Khewat) -> dict[str, OwnershipScope]:
    """For every Khatauni in the Khewat, decide whether it is governed by
    its own explicit owner(s) or inherits the Khewat-level default."""
    explicit_khatauni_ids = {o.khatauni_id for o in khewat.owners if o.khatauni_id is not None}
    return {
        kht.khatauni_id: (
            OwnershipScope.KHATAUNI if kht.khatauni_id in explicit_khatauni_ids else OwnershipScope.KHEWAT
        )
        for kht in khewat.khataunis
    }


def inheriting_khataunis(khewat: Khewat) -> list[Khatauni]:
    """Khataunis with no owner row of their own -- governed by the
    Khewat-level (pooled) owners, per the fallback/inheritance rule."""
    governance = khatauni_governance(khewat)
    return [kht for kht in khewat.khataunis if governance.get(kht.khatauni_id) == OwnershipScope.KHEWAT]


def owners_by_khatauni(khewat: Khewat) -> dict[str, list[Owner]]:
    grouped: dict[str, list[Owner]] = {}
    for owner in khewat.owners:
        if owner.khatauni_id is not None:
            grouped.setdefault(owner.khatauni_id, []).append(owner)
    return grouped


def pooled_owners(khewat: Khewat) -> list[Owner]:
    return [o for o in khewat.owners if o.khatauni_id is None]


@dataclass(frozen=True)
class EffectiveOwnershipInterest:
    """One Owner row's resolved entitlement: which scope it holds, which
    Khatauni(s) that scope's area is drawn from, and the exact area (in
    sarsahi) that owner's fraction is calculated against. Never includes
    area from a Khatauni governed by a different, explicit owner."""
    owner: Owner
    scope: OwnershipScope
    khatauni_ids: tuple[str, ...]
    area_sarsahi: int
    area_complete: bool
    missing_khatauni_ids: tuple[str, ...]

    def entitlement_sarsahi(self) -> Fraction | None:
        if self.owner.fraction is None:
            return None
        return Fraction(self.area_sarsahi) * self.owner.fraction


def resolve_owner_entitlements(
    owner_rows: list[Owner],
    khewat: Khewat,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> list[EffectiveOwnershipInterest]:
    """Resolve one real person's (possibly several) Owner rows within one
    Khewat into their effective entitlements. `owner_rows` must all share
    the same khewat_id (callers group by Khewat first, since Khewats are
    legally distinct holdings and must never be silently summed)."""
    inheriting = inheriting_khataunis(khewat)
    khataunis_by_id = {kht.khatauni_id: kht for kht in khewat.khataunis}

    interests: list[EffectiveOwnershipInterest] = []
    for owner in owner_rows:
        if owner.khatauni_id is not None:
            khatauni = khataunis_by_id.get(owner.khatauni_id)
            if (
                khatauni is None
                or khatauni.recorded_total_area is None
                or not khatauni.recorded_total_area.calculable
            ):
                interests.append(EffectiveOwnershipInterest(
                    owner=owner, scope=OwnershipScope.KHATAUNI,
                    khatauni_ids=(owner.khatauni_id,), area_sarsahi=0,
                    area_complete=False,
                    missing_khatauni_ids=(owner.khatauni_id,),
                ))
                continue
            interests.append(EffectiveOwnershipInterest(
                owner=owner, scope=OwnershipScope.KHATAUNI,
                khatauni_ids=(owner.khatauni_id,),
                area_sarsahi=khatauni.recorded_total_area.total_sarsahi(marla_per_kanal, sarsahi_per_marla),
                area_complete=True, missing_khatauni_ids=(),
            ))
        else:
            total = 0
            missing: list[str] = []
            for kht in inheriting:
                if kht.recorded_total_area is None:
                    missing.append(kht.khatauni_id)
                    continue
                area = kht.recorded_total_area.total_sarsahi(marla_per_kanal, sarsahi_per_marla)
                if area is None:
                    missing.append(kht.khatauni_id)
                    continue
                total += area
            interests.append(EffectiveOwnershipInterest(
                owner=owner, scope=OwnershipScope.KHEWAT,
                khatauni_ids=tuple(kht.khatauni_id for kht in inheriting),
                area_sarsahi=total, area_complete=not missing,
                missing_khatauni_ids=tuple(missing),
            ))
    return interests
