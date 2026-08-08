"""Mortgage (Rehin) status resolution.

A mortgage MENTION in Column 8 does not mean a mortgage is currently
ACTIVE -- a later entry may show it discharged/released. Digital Patwari
must not claim an active loan merely because historical mortgage wording
appears; it must check whether a release/discharge entry exists for that
specific mortgage.

This mirrors reconciliation.py's Approved/Pending Mutation Rule but is
kept separate: a mortgage is an encumbrance, not an ownership transfer,
and "discharged" is not the same axis as "approved/pending".
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from digital_patwari.models import DigitalPatwariDocument, Mutation, MutationType


class MortgageStatus(str, Enum):
    NO_MORTGAGE_DETECTED = "no_mortgage_detected"
    ACTIVE_MORTGAGE_LIKELY = "active_mortgage_likely"
    DISCHARGED = "discharged"
    UNCLEAR = "unclear"


@dataclass(frozen=True)
class MortgageFinding:
    status: MortgageStatus
    mortgage_mutations: tuple[Mutation, ...]
    discharge_mutations: tuple[Mutation, ...]
    note: str


def resolve_mortgage_status(document: DigitalPatwariDocument, target_type, target_id: str) -> MortgageFinding:
    mortgages = tuple(
        m for m in document.mutations
        if m.target_type == target_type and m.target_id == target_id and m.mutation_type == MutationType.MORTGAGE
    )
    if not mortgages:
        return MortgageFinding(
            status=MortgageStatus.NO_MORTGAGE_DETECTED,
            mortgage_mutations=(), discharge_mutations=(),
            note="No mortgage (Rehin) entry is recorded against this entity.",
        )

    mortgage_ids = {m.mutation_id for m in mortgages}
    discharges = tuple(
        m for m in document.mutations
        if m.mutation_type == MutationType.RELEASE_DISCHARGE and m.discharges_mutation_id in mortgage_ids
    )
    discharged_ids = {m.discharges_mutation_id for m in discharges}
    still_active = [m for m in mortgages if m.mutation_id not in discharged_ids]

    if not still_active:
        return MortgageFinding(
            status=MortgageStatus.DISCHARGED,
            mortgage_mutations=mortgages, discharge_mutations=discharges,
            note="A mortgage was recorded, but a matching release/discharge entry was also found -- "
                 "treat it as discharged, not active.",
        )

    if any(m.extraction_status.value != "present" for m in still_active):
        return MortgageFinding(
            status=MortgageStatus.UNCLEAR,
            mortgage_mutations=mortgages, discharge_mutations=discharges,
            note="A mortgage entry exists with no matching discharge, but its extraction status is "
                 "uncertain/illegible -- verify before relying on this.",
        )

    return MortgageFinding(
        status=MortgageStatus.ACTIVE_MORTGAGE_LIKELY,
        mortgage_mutations=mortgages, discharge_mutations=discharges,
        note="A mortgage entry exists with no matching release/discharge entry found in this document -- "
             "likely still active, but confirm with current bank/registry records rather than assuming.",
    )
