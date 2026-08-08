"""Base Jamabandi ownership vs. mutation ledger vs. derived position.

Digital Patwari must never collapse these into one number:

  STATE 1  BASE JAMABANDI OWNERSHIP
           What the Jamabandi's own ownership column explicitly records.
           This is a historical fact. It is NEVER overwritten or rewritten,
           no matter what later mutations say.

  STATE 2  POST-JAMABANDI MUTATION EFFECTS
           The ledger of subsequent Column-8 mutations, each preserved with
           its own status and evidence.

  STATE 3  DERIVED / EFFECTIVE POSITION
           base +/- the effects of mutations that are actually operative.
           Always labelled as derived, never presented as what the record
           itself says.

  (STATE 4 possession/Girdawari lives in cultivation.py -- a mutation that
   moves ownership does not prove possession moved.)

Only an APPROVED/sanctioned mutation is operative here (see
models.is_operative_for_derived_ownership). Referenced, entered, presented
for verification (paratal), presented for sanction, pending, rejected,
cancelled and uncertain mutations are all recorded and explained but never
move a share.

All arithmetic is exact Fraction arithmetic in deterministic code -- never
LLM subtraction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from digital_patwari.models import (
    DigitalPatwariDocument,
    Khewat,
    Mutation,
    Owner,
    RemarkTarget,
)
from digital_patwari.normalization import parse_fraction


@dataclass(frozen=True)
class AppliedMutationEffect:
    """One operative mutation's arithmetic effect on one owner's share."""
    mutation_id: str
    share_before: Fraction
    share_delta: Fraction          # negative for a transfer out, positive for an acquisition
    share_after: Fraction
    description: str


@dataclass(frozen=True)
class DerivedOwnershipPosition:
    """The three states for one Owner row, kept separate and all visible."""
    owner_id: str
    khewat_id: str
    person_name: str

    base_share: Fraction                                   # STATE 1 -- never rewritten
    applied_effects: tuple[AppliedMutationEffect, ...]     # STATE 2 (the operative subset)
    derived_share: Fraction                                # STATE 3

    # Non-operative mutations touching this owner: recorded, not applied.
    unapplied_mutation_ids: tuple[str, ...] = ()
    unapplied_reason: str | None = None
    # True when something blocked a clean derivation (e.g. a transfer larger
    # than the held share) -- callers must abstain rather than present a figure.
    derivation_failed: bool = False
    failure_reason: str | None = None

    @property
    def changed(self) -> bool:
        return self.derived_share != self.base_share


@dataclass(frozen=True)
class AcquiredPosition:
    """Share acquired by a transferee who has no Owner row in this
    Jamabandi yet -- a mutation gave them land, but the base record
    predates it. Reported as derived-only, never as a base record fact."""
    person_name: str
    khewat_id: str
    acquired_share: Fraction
    mutation_ids: tuple[str, ...]


@dataclass(frozen=True)
class KhewatDerivedOwnership:
    khewat_id: str
    positions: tuple[DerivedOwnershipPosition, ...]
    acquisitions: tuple[AcquiredPosition, ...] = ()

    def position_for_owner(self, owner_id: str) -> DerivedOwnershipPosition | None:
        for position in self.positions:
            if position.owner_id == owner_id:
                return position
        return None


def _chronological(mutations: list[Mutation]) -> list[Mutation]:
    """Order mutations for sequential application.

    A later mutation can act on the result of an earlier one, so order
    matters and mutations must not be evaluated in isolation. Explicit
    sequence_index wins; then mutation_date as source text (ISO-ish text
    sorts correctly; anything else falls back to stable document order);
    then the order they appear in the document.
    """
    def sort_key(indexed: tuple[int, Mutation]):
        position, mutation = indexed
        has_index = mutation.sequence_index is not None
        return (
            0 if has_index else 1,
            mutation.sequence_index if has_index else 0,
            mutation.mutation_date or "",
            position,
        )

    return [m for _, m in sorted(enumerate(mutations), key=sort_key)]


def _mutations_affecting_owner(document: DigitalPatwariDocument, owner: Owner) -> list[Mutation]:
    return [
        m for m in document.mutations
        if (m.target_type == RemarkTarget.OWNER and m.target_id == owner.owner_id)
        or (m.transferor_owner_id is not None and m.transferor_owner_id == owner.owner_id)
    ]


def derive_khewat_ownership(document: DigitalPatwariDocument, khewat: Khewat) -> KhewatDerivedOwnership:
    positions: list[DerivedOwnershipPosition] = []
    acquisitions_by_person: dict[str, list[Mutation]] = {}

    for owner in khewat.owners:
        base_share = owner.fraction
        relevant = _chronological(_mutations_affecting_owner(document, owner))

        operative = [m for m in relevant if m.is_operative]
        non_operative = [m for m in relevant if not m.is_operative]

        running = base_share
        applied: list[AppliedMutationEffect] = []
        derivation_failed = False
        failure_reason: str | None = None

        for mutation in operative:
            transferred = mutation.transferred_fraction
            if transferred is None:
                # Operative but no share stated -- cannot derive arithmetic.
                # Do not guess a share from free text; flag and stop.
                derivation_failed = True
                failure_reason = (
                    f"Mutation {mutation.mutation_id} is sanctioned but states no transferable share; "
                    f"the derived position cannot be computed without guessing."
                )
                break
            if transferred > running:
                derivation_failed = True
                failure_reason = (
                    f"Mutation {mutation.mutation_id} transfers {transferred}, which exceeds the "
                    f"{running} held at that point. This is a record/extraction inconsistency, not a "
                    f"negative holding -- human verification required."
                )
                break

            share_after = running - transferred
            applied.append(AppliedMutationEffect(
                mutation_id=mutation.mutation_id,
                share_before=running, share_delta=-transferred, share_after=share_after,
                # Deliberately carries NO fraction text. The exact values live
                # in share_before/share_delta/share_after so the presentation
                # layer can render them over the denominator the Fard actually
                # printed -- baking "100/467" in here would make an explanation
                # impossible to check against a page that reads "200/934".
                description=(
                    f"Sanctioned {(mutation.mutation_type.value if mutation.mutation_type else 'transfer')}"
                    + (f" to {mutation.transferee_name}" if mutation.transferee_name else "")
                ),
            ))
            running = share_after

            if mutation.transferee_name:
                acquisitions_by_person.setdefault(mutation.transferee_name, []).append(mutation)

        positions.append(DerivedOwnershipPosition(
            owner_id=owner.owner_id,
            khewat_id=khewat.khewat_id,
            person_name=owner.raw_owner_name_parentage,
            base_share=base_share,
            applied_effects=tuple(applied),
            # On failure the derived share stays at the base -- never a
            # half-applied or negative figure. derivation_failed tells the
            # caller to abstain rather than trust it.
            derived_share=base_share if derivation_failed else running,
            unapplied_mutation_ids=tuple(m.mutation_id for m in non_operative),
            unapplied_reason=(
                "Recorded but not operative (not sanctioned/approved); ownership as recorded is unchanged."
                if non_operative else None
            ),
            derivation_failed=derivation_failed,
            failure_reason=failure_reason,
        ))

    existing_names = {o.raw_owner_name_parentage.strip().lower() for o in khewat.owners}
    acquisitions: list[AcquiredPosition] = []
    for person_name, mutations in acquisitions_by_person.items():
        if person_name.strip().lower() in existing_names:
            # Already an owner row in this Khewat; their acquisition shows up
            # through their own position rather than as a separate entry.
            continue
        total = Fraction(0)
        for mutation in mutations:
            transferred = mutation.transferred_fraction
            if transferred is not None:
                total += transferred
        acquisitions.append(AcquiredPosition(
            person_name=person_name, khewat_id=khewat.khewat_id,
            acquired_share=total,
            mutation_ids=tuple(m.mutation_id for m in mutations),
        ))

    return KhewatDerivedOwnership(
        khewat_id=khewat.khewat_id,
        positions=tuple(positions),
        acquisitions=tuple(acquisitions),
    )


def derive_document_ownership(document: DigitalPatwariDocument) -> dict[str, KhewatDerivedOwnership]:
    return {khewat.khewat_id: derive_khewat_ownership(document, khewat) for khewat in document.khewats}


def format_fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def format_over_denominator(value: Fraction, denominator: int | None) -> str:
    """Express an exact fraction over the denominator the Fard actually
    printed, when it divides evenly.

    Fards state co-sharer shares over a common denominator (404/934,
    200/934, 204/934...). Reducing to lowest terms is mathematically
    identical but makes an explanation hard to check against the page --
    "102/467" does not visibly correspond to the printed "204/934". This
    re-expresses for DISPLAY only; all arithmetic stays on the exact
    Fraction."""
    canonical = format_fraction(value)
    if not denominator or denominator <= 0:
        return canonical
    scaled_numerator = value * denominator
    if scaled_numerator.denominator != 1:
        return canonical  # doesn't divide evenly; showing it would be misleading
    if denominator == value.denominator:
        return canonical
    return f"{scaled_numerator.numerator}/{denominator} (= {canonical})"
