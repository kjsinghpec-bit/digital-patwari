"""Stage 3-4 of the extraction pipeline: reconciliation.

The full pipeline, made explicit as distinct stages instead of one opaque
call, is:

  1. Candidate extraction  -- what the model initially reads.
     ExtractionResult.raw_llm_output (untrusted, unvalidated JSON/text).

  2. Validated record      -- what pydantic confirms is schema-shaped.
     ExtractionResult.document (DigitalPatwariDocument), or a list of
     structured field errors in ExtractionResult.parser_errors if it
     isn't.

  3. Gate-checked record   -- what deterministic validation confirms.
     ExtractionResult.validation_report (AG-01/02/03: share summation,
     linkage/integrity, area consistency). Nothing here is inferred --
     only checked.

  4. Reconciled record     -- what gets corrected/reconciled, and what
     ultimately becomes the trusted structured Fard record.
     ReconciledFardRecord, produced by reconcile() below. This is the
     ONLY stage the query/explanation layer (digital_patwari.query) is
     allowed to read from.

Reconciliation here means exactly one thing: applying CLAUDE.md's
Approved-vs-Pending Mutation Rule as checked code. It never invents a
new owner, share, or area from free-text mutation wording -- that would
violate the Zero-Guesswork Guardrail. It only classifies, per owner and
per Khewat, whether the ownership *as recorded* should be trusted as
currently active, treated as superseded pending manual verification, or
left active with a pending-mutation note attached.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from digital_patwari.extraction import ExtractionResult
from digital_patwari.models import DigitalPatwariDocument, MutationStatus, RemarkTarget
from digital_patwari.validation import ValidationReport


class OwnershipStatus(str, Enum):
    AS_RECORDED_ACTIVE = "as_recorded_active"
    SUPERSEDED_BY_APPROVED_MUTATION = "superseded_by_approved_mutation"
    PENDING_MUTATION_NOTED = "pending_mutation_noted"


@dataclass(frozen=True)
class OwnershipReconciliation:
    khewat_id: str
    owner_id: str | None  # None => this entry is a Khewat-level rollup, not owner-specific
    status: OwnershipStatus
    mutation_ids: list[str]
    note: str


@dataclass(frozen=True)
class ReconciledFardRecord:
    """The trusted structured Fard record. Everything the query layer
    answers from must come from here, never from raw_llm_output."""
    document: DigitalPatwariDocument
    validation_report: ValidationReport
    ownership_reconciliations: tuple[OwnershipReconciliation, ...]

    def reconciliation_for_owner(self, owner_id: str) -> OwnershipReconciliation | None:
        for r in self.ownership_reconciliations:
            if r.owner_id == owner_id:
                return r
        return None

    def reconciliation_for_khewat(self, khewat_id: str) -> OwnershipReconciliation | None:
        for r in self.ownership_reconciliations:
            if r.khewat_id == khewat_id and r.owner_id is None:
                return r
        return None


def _mutations_for(document: DigitalPatwariDocument, target_type: RemarkTarget, target_id: str, status: MutationStatus):
    return [
        m for m in document.mutations
        if m.target_type == target_type and m.target_id == target_id and m.status == status
    ]


def reconcile(document: DigitalPatwariDocument, validation_report: ValidationReport) -> ReconciledFardRecord:
    reconciliations: list[OwnershipReconciliation] = []

    for khewat in document.khewats:
        khewat_approved = _mutations_for(document, RemarkTarget.KHEWAT, khewat.khewat_id, MutationStatus.APPROVED)
        khewat_pending = _mutations_for(document, RemarkTarget.KHEWAT, khewat.khewat_id, MutationStatus.PENDING)

        for owner in khewat.owners:
            owner_approved = _mutations_for(document, RemarkTarget.OWNER, owner.owner_id, MutationStatus.APPROVED)
            owner_pending = _mutations_for(document, RemarkTarget.OWNER, owner.owner_id, MutationStatus.PENDING)

            approved = khewat_approved + owner_approved
            pending = khewat_pending + owner_pending

            if approved:
                status = OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION
                note = (
                    "An approved/sanctioned mutation exists against this owner or Khewat. Per the "
                    "Approved Mutation Rule, ownership as recorded in this Fard row may no longer be "
                    "current. Digital Patwari does not compute a new share or owner from free-text "
                    "mutation wording -- verify against the mutation record."
                )
                mutation_ids = [m.mutation_id for m in approved]
            elif pending:
                status = OwnershipStatus.PENDING_MUTATION_NOTED
                note = (
                    "A mutation is entered/pending but not yet sanctioned. Per the Pending Mutation "
                    "Rule, ownership as recorded remains active; this is noted only as a pending "
                    "encumbrance."
                )
                mutation_ids = [m.mutation_id for m in pending]
            else:
                status = OwnershipStatus.AS_RECORDED_ACTIVE
                note = "No mutation is recorded against this owner or Khewat; ownership as recorded is currently active."
                mutation_ids = []

            reconciliations.append(OwnershipReconciliation(
                khewat_id=khewat.khewat_id, owner_id=owner.owner_id,
                status=status, mutation_ids=mutation_ids, note=note,
            ))

        if khewat_approved:
            khewat_status = OwnershipStatus.SUPERSEDED_BY_APPROVED_MUTATION
            khewat_note = "An approved mutation is recorded against this Khewat as a whole."
            khewat_mutation_ids = [m.mutation_id for m in khewat_approved]
        elif khewat_pending:
            khewat_status = OwnershipStatus.PENDING_MUTATION_NOTED
            khewat_note = "A pending mutation is recorded against this Khewat as a whole; active ownership is unchanged."
            khewat_mutation_ids = [m.mutation_id for m in khewat_pending]
        else:
            khewat_status = OwnershipStatus.AS_RECORDED_ACTIVE
            khewat_note = "No Khewat-level mutation recorded."
            khewat_mutation_ids = []

        reconciliations.append(OwnershipReconciliation(
            khewat_id=khewat.khewat_id, owner_id=None,
            status=khewat_status, mutation_ids=khewat_mutation_ids, note=khewat_note,
        ))

    return ReconciledFardRecord(
        document=document,
        validation_report=validation_report,
        ownership_reconciliations=tuple(reconciliations),
    )


def reconcile_extraction_result(result: ExtractionResult) -> ReconciledFardRecord:
    """Convenience: build a ReconciledFardRecord directly from a
    successful FardExtractionParser.extract() result."""
    if not result.succeeded:
        raise ValueError("Cannot reconcile a failed extraction result.")
    return reconcile(result.document, result.validation_report)
