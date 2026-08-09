"""Typed view models: canonical objects -> UI shapes.

This module is presentation only. It re-derives no share, no area and no
legal conclusion; every number it shows was already computed by
``digital_patwari``'s validated engines. Its jobs are:

  * naming things in citizen language while keeping the Punjabi term,
  * attaching evidence to every statement,
  * making uncertainty and absence structurally impossible to hide.

Two rules are enforced here rather than left to the frontend:

  1. A value that is unknown is emitted as ``None`` with a ``tone`` of
     ``unknown``. It is never emitted as 0, "-" or "".
  2. Nothing is described as "not present" when the page it would have
     appeared on was not read. That distinction lives in ``PageVM.state``
     and in ``SummaryVM.unread_pages``.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from digital_patwari.derived_ownership import format_fraction
from digital_patwari.encumbrance import MortgageStatus, resolve_mortgage_status
from digital_patwari.extraction import DocumentStatus, ExtractionResult
from digital_patwari_ui.absence import AbsenceClaim, absence_claim, compute_unread_pages
from digital_patwari_ui.absence import stated_total_pages as _stated_total_pages
from digital_patwari.models import (
    AreaKanalMarlaSarsahi,
    DigitalPatwariDocument,
    ExtractionStatus,
    GateResult,
    Khasra,
    Khatauni,
    Khewat,
    Mutation,
    Owner,
    Remark,
    RemarkTarget,
    SourceReference,
    is_operative_for_derived_ownership,
)
from digital_patwari.observations import (
    FieldObservation,
    PageObservation,
    VerificationIssue,
    VerificationReason,
)
from digital_patwari.ownership import (
    OwnershipScope,
    khatauni_governance,
    resolve_owner_entitlements,
)
# Unit conversion must have exactly one implementation. The query layer owns
# it; the UI formats what that produces rather than dividing by 20 and 9
# again in a second place.
from digital_patwari.query import _display_sarsahi as display_sarsahi
from digital_patwari.query import khewat_total_area_sarsahi
from digital_patwari.reconciliation import ReconciledFardRecord

Tone = Literal["ok", "warn", "unknown", "info"]

COLUMN_LABELS: dict[str, str] = {
    "1": "Column 1 — Khewat (ownership account)",
    "2": "Column 2 — Khatauni (cultivation account)",
    "3": "Column 3 — Owners and shares",
    "4": "Column 4 — Cultivation / possession",
    "5": "Column 5 — Irrigation",
    "6": "Column 6 — Murabba and Khasra",
    "7": "Column 7 — Area",
    "8": "Column 8 — Vishesh Kathan (remarks and mutations)",
    "header": "Page header",
}

GATE_TITLES: dict[str, tuple[str, str]] = {
    "AG-01": (
        "Do the recorded shares add up?",
        "Every owner's share in a Khewat should add up to one whole.",
    ),
    "AG-02": (
        "Is every entry attached to the right record?",
        "Each parcel must belong to a Khatauni, and each Khatauni to a Khewat.",
    ),
    "AG-03": (
        "Do the areas add up?",
        "The parcels listed under a Khatauni should add up to that Khatauni's printed total.",
    ),
    "AG-04": (
        "Are all the pages here?",
        "If a page says \"Page 5 of 8\", all eight pages must be present.",
    ),
    "AG-05": (
        "Do the mutation share and area agree?",
        "Where a mutation states both a share and an area, the two should match.",
    ),
    "AG-06": (
        "Is the same land counted twice?",
        "A total printed twice is the same land written again, not extra land.",
    ),
    "AG-07": (
        "Are purchased parcels properly identified?",
        "A purchase of named parcels must point at real parcels in this record.",
    ),
}

VERIFICATION_REASON_TEXT: dict[VerificationReason, str] = {
    VerificationReason.UNREADABLE: "The printing here could not be read clearly.",
    VerificationReason.AMBIGUOUS: "More than one reading of this text is possible.",
    VerificationReason.STRUCTURAL_CONFLICT: "Two parts of the record disagree about this.",
    VerificationReason.INVALID_FORMAT: "The value read here is not in a form we can use.",
    VerificationReason.CALCULATION_MISMATCH: "A calculation using this value did not come out right.",
}

MORTGAGE_STATUS_TEXT: dict[MortgageStatus, tuple[str, Tone]] = {
    MortgageStatus.NO_MORTGAGE_DETECTED: ("No mortgage entry found in this record", "ok"),
    MortgageStatus.ACTIVE_MORTGAGE_LIKELY: ("A mortgage is recorded with no release found", "warn"),
    MortgageStatus.DISCHARGED: ("A mortgage was recorded and later released", "ok"),
    MortgageStatus.UNCLEAR: ("A mortgage is recorded but the entry is unclear", "warn"),
}

STATUS_TEXT: dict[DocumentStatus, tuple[str, str, Tone]] = {
    DocumentStatus.COMPLETE: (
        "Every page was read",
        "All pages were read and every check passed.",
        "ok",
    ),
    DocumentStatus.COMPLETE_WITH_WARNINGS: (
        "Read, with things to check",
        "All pages were read, but some entries in the record do not agree with each other.",
        "warn",
    ),
    DocumentStatus.PARTIAL: (
        "Partly read",
        "Some of this record could not be read or still needs your confirmation. "
        "What is missing is unknown — it is not empty.",
        "warn",
    ),
    DocumentStatus.FAILED: (
        "Could not be read",
        "This document could not be read. Nothing about its contents can be shown.",
        "unknown",
    ),
}


# =====================================================================
# EVIDENCE
# =====================================================================


class EvidenceVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int | None = None
    column_ref: str | None = None
    column_label: str | None = None
    raw_text: str | None = None
    status: str = ExtractionStatus.PRESENT.value
    confidence: str | None = None
    provenance: str | None = None
    region: str | None = None
    is_blank_cell: bool = False


class EvidenceIndex:
    """Joins canonical ``SourceReference``s to their ``FieldObservation``.

    Canonical entities keep a SourceReference (page, column, raw text) but
    the page-local observation IDs are regenerated by the cross-page merge,
    so an ID join is not available after merging. The stable join key is
    what was actually printed: (page number, column, raw text). A miss is
    normal and harmless — the evidence still shows page, column and raw
    text, only the on-page highlight is absent.
    """

    def __init__(self, observations: tuple[PageObservation, ...] | list[PageObservation]) -> None:
        self._by_key: dict[tuple[int, str, str], FieldObservation] = {}
        self._by_id: dict[str, FieldObservation] = {}
        self._blank_cells: set[tuple[int, str]] = set()
        for observation in observations:
            for field_observation in observation.fields:
                self._by_id[field_observation.observation_id] = field_observation
                key = (field_observation.page_number, field_observation.column_ref, field_observation.raw_text)
                self._by_key.setdefault(key, field_observation)
            for cell in observation.cells:
                if cell.is_blank:
                    self._blank_cells.add((observation.page_number, cell.column_ref))

    def field(self, observation_id: str) -> FieldObservation | None:
        return self._by_id.get(observation_id)

    def region_for(self, source: SourceReference | None) -> str | None:
        if source is None or source.column_ref is None:
            return None
        found = self._by_key.get((source.page_number, source.column_ref, source.raw_text or ""))
        return found.evidence_region if found is not None else None

    def is_blank_cell(self, source: SourceReference | None) -> bool:
        if source is None or source.column_ref is None:
            return False
        return (source.page_number, source.column_ref) in self._blank_cells

    def evidence(self, source: SourceReference | None) -> list[EvidenceVM]:
        if source is None:
            return []
        return [EvidenceVM(
            page_number=source.page_number,
            column_ref=source.column_ref,
            column_label=COLUMN_LABELS.get(source.column_ref or ""),
            raw_text=source.raw_text,
            status=source.status.value,
            confidence=source.confidence.value,
            provenance=source.provenance.value,
            region=self.region_for(source),
            is_blank_cell=self.is_blank_cell(source),
        )]

    def evidence_many(self, sources: list[SourceReference | None]) -> list[EvidenceVM]:
        collected: list[EvidenceVM] = []
        for source in sources:
            collected.extend(self.evidence(source))
        return collected


# =====================================================================
# SMALL SHARED SHAPES
# =====================================================================


class FindingVM(BaseModel):
    """One headline statement with its evidence."""

    model_config = ConfigDict(extra="forbid")
    id: str
    label: str
    value: str | None = None
    detail: str | None = None
    tone: Tone = "info"
    evidence: list[EvidenceVM] = Field(default_factory=list)


class PageVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int
    state: Literal["read", "reused_from_cache", "failed", "not_uploaded"]
    message: str
    stated_total_pages: int | None = None


class CalculationStepVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    value: str
    note: str | None = None


class CalculationVM(BaseModel):
    """A reproducible calculation, shown step by step."""

    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    steps: list[CalculationStepVM] = Field(default_factory=list)
    result: str | None = None
    uncertain: bool = False
    note: str | None = None
    evidence: list[EvidenceVM] = Field(default_factory=list)


# =====================================================================
# RECORD SHAPES
# =====================================================================


class KhasraVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khasra_id: str
    khasra_number: str
    murabba_number: str | None = None
    area: str | None = None
    area_known: bool = True
    irrigation: str | None = None
    raw_soil_classification: str | None = None
    cultivation_status: str | None = None
    status: str = ExtractionStatus.PRESENT.value
    evidence: list[EvidenceVM] = Field(default_factory=list)


class KhatauniVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khatauni_id: str
    khatauni_number: str
    khewat_id: str
    khewat_number: str | None = None
    cultivator: str | None = None
    possession_type: str | None = None
    recorded_area: str | None = None
    parcels_area: str | None = None
    area_agrees: bool | None = None
    area_note: str | None = None
    governed_by: Literal["own_owners", "khewat_default"] = "khewat_default"
    governance_note: str
    continuation_note: str | None = None
    khasras: list[KhasraVM] = Field(default_factory=list)
    evidence: list[EvidenceVM] = Field(default_factory=list)


class OwnerVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: str
    khewat_id: str
    khewat_number: str | None = None
    name: str
    raw_name: str
    share: str | None = None
    raw_share: str
    share_known: bool = True
    scope: Literal["khewat", "khatauni"] = "khewat"
    scope_note: str
    khatauni_numbers: list[str] = Field(default_factory=list)
    area: str | None = None
    area_known: bool = False
    area_note: str | None = None
    status: str = ExtractionStatus.PRESENT.value
    reconciliation_note: str | None = None
    evidence: list[EvidenceVM] = Field(default_factory=list)


class MutationVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mutation_id: str
    status: str
    status_plain: str
    moves_ownership: bool
    mutation_type: str | None = None
    date: str | None = None
    transferor: str | None = None
    transferee: str | None = None
    share_transferred: str | None = None
    target: str
    raw_text: str
    meaning: str | None = None
    evidence: list[EvidenceVM] = Field(default_factory=list)


class RemarkVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    category_plain: str
    target: str
    raw_text: str
    meaning: str | None = None
    tone: Tone = "info"
    evidence: list[EvidenceVM] = Field(default_factory=list)


class MortgageVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khewat_id: str
    khewat_number: str | None = None
    status: str
    status_plain: str
    tone: Tone
    note: str
    mutations: list[MutationVM] = Field(default_factory=list)
    releases: list[MutationVM] = Field(default_factory=list)


class KhewatVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khewat_id: str
    khewat_number: str | None = None
    number_known: bool = True
    total_share: str | None = None
    total_area: str | None = None
    total_area_complete: bool = True
    owners: list[OwnerVM] = Field(default_factory=list)
    khataunis: list[KhatauniVM] = Field(default_factory=list)
    mutations: list[MutationVM] = Field(default_factory=list)
    remarks: list[RemarkVM] = Field(default_factory=list)
    mortgage: MortgageVM | None = None
    evidence: list[EvidenceVM] = Field(default_factory=list)


class CultivationVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_name: str
    khewat_number: str | None = None
    khatauni_number: str | None = None
    relationship: str
    relationship_plain: str
    raw_text: str | None = None
    share: str | None = None
    status: str
    evidence: list[EvidenceVM] = Field(default_factory=list)


class GateVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate_id: str
    title: str
    plain_language: str
    passed: bool
    checked_entities: int
    skipped_entities: int
    skipped: bool = False
    issues: list[dict[str, str | None]] = Field(default_factory=list)


class VerificationQuestionVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue_id: str
    question: str
    why_it_matters: str
    reason: str
    reason_plain: str
    page_number: int | None = None
    column_ref: str | None = None
    column_label: str | None = None
    ai_reading: str | None = None
    ai_raw_text: str | None = None
    proposed_value: Any = None
    alternatives: list[Any] = Field(default_factory=list)
    region: str | None = None
    critical: bool = True
    resolved: bool = False


class HeaderVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    village: str
    hadbast_number: str
    jamabandi_year: str
    lr_number: str
    district: str | None = None
    tehsil: str | None = None
    layout: str
    layout_plain: str
    evidence: list[EvidenceVM] = Field(default_factory=list)


class CountsVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khewats: int
    khataunis: int
    khasras: int
    owners: int
    mutations: int
    remarks: int
    cultivation_entries: int


class SummaryVM(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    scenario_key: str | None = None
    scenario_label: str | None = None
    status: str
    status_title: str
    status_explanation: str
    status_tone: Tone
    is_readable: bool
    header: HeaderVM | None = None
    counts: CountsVM | None = None
    findings: list[FindingVM] = Field(default_factory=list)
    pages: list[PageVM] = Field(default_factory=list)
    unread_pages: list[int] = Field(default_factory=list)
    stated_total_pages: int | None = None
    gates: list[GateVM] = Field(default_factory=list)
    gates_passed: bool | None = None
    open_questions: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AbsenceClaimVM(BaseModel):
    """One 'nothing found' statement, mirroring
    ``digital_patwari_ui.absence.AbsenceClaim``. Every screen that can show
    an empty list (mutations, remarks, possession, mortgages) renders THIS
    pre-composed text/tone rather than writing its own -- see
    ``digital_patwari_ui/absence.py`` for the single source of the wording.
    """

    model_config = ConfigDict(extra="forbid")
    text: str
    tone: Literal["ok", "unknown"]
    uncertain: bool


def _absence_vm(claim: AbsenceClaim) -> AbsenceClaimVM:
    return AbsenceClaimVM(text=claim.text, tone=claim.tone, uncertain=claim.uncertain)


class DocumentVM(BaseModel):
    """Everything the UI needs for one analysed document."""

    model_config = ConfigDict(extra="forbid")
    summary: SummaryVM
    khewats: list[KhewatVM] = Field(default_factory=list)
    owners: list[OwnerVM] = Field(default_factory=list)
    mutations: list[MutationVM] = Field(default_factory=list)
    remarks: list[RemarkVM] = Field(default_factory=list)
    mortgages: list[MortgageVM] = Field(default_factory=list)
    cultivation: list[CultivationVM] = Field(default_factory=list)
    questions: list[VerificationQuestionVM] = Field(default_factory=list)
    calculations: list[CalculationVM] = Field(default_factory=list)
    #: Pre-composed empty-state text for each screen that lists entries.
    #: Always populated (even when the corresponding list is non-empty, or
    #: the document could not be read at all) so a screen never needs to
    #: compose its own "No X found" wording -- see absence.py.
    mutations_absence: AbsenceClaimVM
    remarks_absence: AbsenceClaimVM
    possession_absence: AbsenceClaimVM
    mortgages_absence: AbsenceClaimVM


# =====================================================================
# BUILDERS
# =====================================================================


def _area_display(area: AreaKanalMarlaSarsahi | None) -> tuple[str | None, bool]:
    """Format a recorded area. Returns (text, known). An area with an
    unresolved component is reported as unknown, never as zero."""
    if area is None:
        return None, False
    if not area.calculable:
        return None, False
    return f"{area.kanal} kanal {area.marla} marla {area.sarsahi} sarsahi", True


def _plain_mutation_status(mutation: Mutation) -> str:
    if is_operative_for_derived_ownership(mutation.status):
        return "Sanctioned — this one can change who owns the land"
    mapping = {
        "Referenced": "Only mentioned elsewhere — it does not change ownership here",
        "Entered": "Entered in the register — not yet sanctioned",
        "Presented_For_Verification": "Presented for checking — not yet sanctioned",
        "Presented_For_Sanction": "Put up for sanction — not yet sanctioned",
        "Pending": "Pending — not yet sanctioned, so ownership is unchanged",
        "Rejected": "Rejected — it does not change ownership",
        "Cancelled": "Cancelled — it does not change ownership",
        "Uncertain": "The status could not be read — treat with caution",
    }
    return mapping.get(mutation.status.value, "Not sanctioned — ownership is unchanged")


_REMARK_CATEGORY_PLAIN = {
    "Approved_Mutation": "A sanctioned change is noted here",
    "Pending_Mutation": "A change has been entered but not sanctioned",
    "Legal_Encumbrance": "A legal charge, such as a mortgage, is noted here",
    "Rent_Details": "Rent details are noted here",
    "Informational": "A general note",
}

_REMARK_CATEGORY_TONE: dict[str, Tone] = {
    "Approved_Mutation": "warn",
    "Pending_Mutation": "warn",
    "Legal_Encumbrance": "warn",
    "Rent_Details": "info",
    "Informational": "info",
}

_CULTIVATION_PLAIN = {
    "khud_kasht": "Khud Kasht — the owner farms it themselves",
    "muzara": "Muzara — a tenant farms it",
    "gair_mumkin": "Gair Mumkin — not cultivable",
    "maqbuza_malkan": "Maqbuza Malkan — in the owners' own possession",
    "other": "Another arrangement is recorded",
    "unknown": "The arrangement is not clear from the record",
}

_LAYOUT_PLAIN = {
    "modern_8_column": "A modern 8-column Fard",
    "legacy_12_column": "An older Fard with a different column arrangement",
    "unknown_layout": "The column layout could not be determined",
}


def _target_label(target_type: RemarkTarget, target_id: str, document: DigitalPatwariDocument) -> str:
    if target_type == RemarkTarget.KHEWAT:
        for khewat in document.khewats:
            if khewat.khewat_id == target_id:
                return f"Khewat {khewat.khewat_number or '(number not read)'}"
    if target_type == RemarkTarget.KHATAUNI:
        for khewat in document.khewats:
            for khatauni in khewat.khataunis:
                if khatauni.khatauni_id == target_id:
                    return f"Khatauni {khatauni.khatauni_number}"
    if target_type == RemarkTarget.OWNER:
        for khewat in document.khewats:
            for owner in khewat.owners:
                if owner.owner_id == target_id:
                    return owner.normalized_owner_name or owner.raw_owner_name_parentage
    if target_type == RemarkTarget.KHASRA:
        for khewat in document.khewats:
            for khatauni in khewat.khataunis:
                for khasra in khatauni.khasras:
                    if khasra.khasra_id == target_id:
                        return f"Khasra {khasra.khasra_number}"
    return f"{target_type.value} {target_id}"


def build_mutation(mutation: Mutation, document: DigitalPatwariDocument, index: EvidenceIndex) -> MutationVM:
    return MutationVM(
        mutation_id=mutation.mutation_id,
        status=mutation.status.value,
        status_plain=_plain_mutation_status(mutation),
        moves_ownership=mutation.is_operative,
        mutation_type=mutation.mutation_type.value if mutation.mutation_type else None,
        date=mutation.mutation_date,
        transferor=mutation.transferor_name,
        transferee=mutation.transferee_name,
        share_transferred=mutation.share_transferred,
        target=_target_label(mutation.target_type, mutation.target_id, document),
        raw_text=mutation.raw_text,
        meaning=mutation.parsed_meaning,
        evidence=index.evidence(mutation.source),
    )


def build_remark(remark: Remark, document: DigitalPatwariDocument, index: EvidenceIndex) -> RemarkVM:
    category = remark.remark_category.value
    return RemarkVM(
        category=category,
        category_plain=_REMARK_CATEGORY_PLAIN.get(category, "A note in the remarks column"),
        target=_target_label(remark.target_type, remark.target_id, document),
        raw_text=remark.raw_text,
        meaning=remark.parsed_meaning,
        tone=_REMARK_CATEGORY_TONE.get(category, "info"),
        evidence=index.evidence(remark.source),
    )


def build_khasra(khasra: Khasra, index: EvidenceIndex) -> KhasraVM:
    area, known = _area_display(khasra.area_kanal_marla)
    return KhasraVM(
        khasra_id=khasra.khasra_id,
        khasra_number=khasra.khasra_number,
        murabba_number=khasra.murabba_number,
        area=area,
        area_known=known,
        irrigation=khasra.normalized_irrigation_source,
        raw_soil_classification=khasra.raw_soil_classification,
        cultivation_status=khasra.normalized_cultivation_status,
        status=khasra.status.value,
        evidence=index.evidence(khasra.source),
    )


def build_khatauni(
    khatauni: Khatauni,
    khewat: Khewat,
    governance: dict[str, OwnershipScope],
    index: EvidenceIndex,
    *,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> KhatauniVM:
    recorded, recorded_known = _area_display(khatauni.recorded_total_area)

    parcel_total = 0
    parcels_complete = bool(khatauni.khasras)
    for khasra in khatauni.khasras:
        total = khasra.area_kanal_marla.total_sarsahi(marla_per_kanal, sarsahi_per_marla)
        if total is None:
            parcels_complete = False
            continue
        parcel_total += total
    parcels_area = display_sarsahi(parcel_total, marla_per_kanal, sarsahi_per_marla) if parcels_complete else None

    agrees: bool | None = None
    note: str | None = None
    if recorded_known and parcels_complete:
        recorded_sarsahi = khatauni.recorded_total_area.total_sarsahi(marla_per_kanal, sarsahi_per_marla)
        agrees = recorded_sarsahi == parcel_total
        if not agrees:
            note = (
                "The printed total for this Khatauni and the sum of its own parcels do not agree. "
                "Both figures are shown exactly as recorded; neither has been altered."
            )
    elif not recorded_known:
        note = "This Khatauni has no readable printed total, so the two cannot be compared."
    elif not parcels_complete:
        note = "One or more parcels here have no readable area, so the parcels cannot be added up."

    scope = governance.get(khatauni.khatauni_id, OwnershipScope.KHEWAT)
    if scope == OwnershipScope.KHATAUNI:
        governed_by: Literal["own_owners", "khewat_default"] = "own_owners"
        governance_note = "This Khatauni has its own owners listed, which apply to it alone."
    else:
        governed_by = "khewat_default"
        governance_note = (
            f"No separate owners are listed for this Khatauni, so it is owned by "
            f"Khewat {khewat.khewat_number or '(number not read)'}'s owners. "
            "A blank owner column here does not mean the owner is unknown."
        )

    continuation_note = None
    if index.is_blank_cell(khatauni.source) or (khatauni.source and khatauni.source.page_number and khewat.source and khewat.source.page_number and khatauni.source.page_number != khewat.source.page_number):
        continuation_note = (
            f"This Khatauni continues under Khewat {khewat.khewat_number or '(number not read)'} "
            f"from an earlier page. The Khewat cell is blank on its own page."
        )

    return KhatauniVM(
        khatauni_id=khatauni.khatauni_id,
        khatauni_number=khatauni.khatauni_number,
        khewat_id=khewat.khewat_id,
        khewat_number=khewat.khewat_number,
        cultivator=khatauni.raw_cultivator_name,
        possession_type=khatauni.raw_possession_type,
        recorded_area=recorded,
        parcels_area=parcels_area,
        area_agrees=agrees,
        area_note=note,
        governed_by=governed_by,
        governance_note=governance_note,
        continuation_note=continuation_note,
        khasras=[build_khasra(khasra, index) for khasra in khatauni.khasras],
        evidence=index.evidence(khatauni.source),
    )


def build_owner(
    owner: Owner,
    khewat: Khewat,
    record: ReconciledFardRecord,
    index: EvidenceIndex,
    *,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> OwnerVM:
    interests = resolve_owner_entitlements([owner], khewat, marla_per_kanal, sarsahi_per_marla)
    interest = interests[0]

    area: str | None = None
    area_known = False
    area_note: str | None = None
    entitlement = interest.entitlement_sarsahi()
    if owner.fraction is None:
        area_note = (
            "This owner's share could not be read, so no area can be calculated from it. "
            "It has not been guessed."
        )
    elif not interest.area_complete:
        area_note = (
            "Some of the land this share applies to has no readable area, so the area "
            "cannot be calculated in full."
        )
    elif entitlement is not None:
        # entitlement is an exact Fraction of sarsahi; show the whole-sarsahi
        # figure and keep the exact fraction visible when it is not whole.
        whole = int(entitlement)
        area = display_sarsahi(whole, marla_per_kanal, sarsahi_per_marla)
        area_known = True
        if entitlement != whole:
            area_note = f"Exact value: {format_fraction(entitlement)} sarsahi."

    if interest.scope == OwnershipScope.KHATAUNI:
        scope: Literal["khewat", "khatauni"] = "khatauni"
        scope_note = (
            "This share is recorded against one Khatauni only, so it applies to that "
            "Khatauni's land and not to the whole Khewat."
        )
    else:
        scope = "khewat"
        scope_note = (
            "This share is recorded at Khewat level, so it applies to the Khewat's land "
            "that has no separate owner list of its own."
        )

    khatauni_numbers = [
        khatauni.khatauni_number
        for khatauni in khewat.khataunis
        if khatauni.khatauni_id in interest.khatauni_ids
    ]

    reconciliation = record.reconciliation_for_owner(owner.owner_id)
    return OwnerVM(
        owner_id=owner.owner_id,
        khewat_id=khewat.khewat_id,
        khewat_number=khewat.khewat_number,
        name=owner.normalized_owner_name or owner.raw_owner_name_parentage,
        raw_name=owner.raw_owner_name_parentage,
        share=owner.share_fraction,
        raw_share=owner.raw_share_fraction,
        share_known=owner.share_fraction is not None,
        scope=scope,
        scope_note=scope_note,
        khatauni_numbers=khatauni_numbers,
        area=area,
        area_known=area_known,
        area_note=area_note,
        status=owner.status.value,
        reconciliation_note=reconciliation.note if reconciliation else None,
        evidence=index.evidence(owner.source),
    )


def build_mortgage(khewat: Khewat, document: DigitalPatwariDocument, index: EvidenceIndex) -> MortgageVM:
    finding = resolve_mortgage_status(document, RemarkTarget.KHEWAT, khewat.khewat_id)
    plain, tone = MORTGAGE_STATUS_TEXT[finding.status]
    return MortgageVM(
        khewat_id=khewat.khewat_id,
        khewat_number=khewat.khewat_number,
        status=finding.status.value,
        status_plain=plain,
        tone=tone,
        note=finding.note,
        mutations=[build_mutation(m, document, index) for m in finding.mortgage_mutations],
        releases=[build_mutation(m, document, index) for m in finding.discharge_mutations],
    )


def build_khewat(
    khewat: Khewat,
    record: ReconciledFardRecord,
    index: EvidenceIndex,
    *,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> KhewatVM:
    document = record.document
    governance = khatauni_governance(khewat)
    total_sarsahi, complete, _missing = khewat_total_area_sarsahi(khewat, marla_per_kanal, sarsahi_per_marla)
    mortgage = build_mortgage(khewat, document, index)
    return KhewatVM(
        khewat_id=khewat.khewat_id,
        khewat_number=khewat.khewat_number,
        number_known=khewat.khewat_number is not None,
        total_share=khewat.total_share,
        total_area=display_sarsahi(total_sarsahi, marla_per_kanal, sarsahi_per_marla) if complete else None,
        total_area_complete=complete,
        owners=[
            build_owner(owner, khewat, record, index,
                        marla_per_kanal=marla_per_kanal, sarsahi_per_marla=sarsahi_per_marla)
            for owner in khewat.owners
        ],
        khataunis=[
            build_khatauni(khatauni, khewat, governance, index,
                           marla_per_kanal=marla_per_kanal, sarsahi_per_marla=sarsahi_per_marla)
            for khatauni in khewat.khataunis
        ],
        mutations=[
            build_mutation(m, document, index) for m in document.mutations
            if m.target_type == RemarkTarget.KHEWAT and m.target_id == khewat.khewat_id
        ],
        remarks=[
            build_remark(r, document, index) for r in document.remarks
            if r.target_type == RemarkTarget.KHEWAT and r.target_id == khewat.khewat_id
        ],
        mortgage=mortgage if mortgage.status != MortgageStatus.NO_MORTGAGE_DETECTED.value else None,
        evidence=index.evidence(khewat.source),
    )


def build_gate(gate: GateResult) -> GateVM:
    title, plain = GATE_TITLES.get(gate.gate_id, (gate.gate_id, "A consistency check on this record."))
    return GateVM(
        gate_id=gate.gate_id,
        title=title,
        plain_language=plain,
        passed=gate.passed,
        checked_entities=gate.checked_entities,
        skipped_entities=gate.skipped_entities,
        skipped=gate.checked_entities == 0 and gate.skipped_entities > 0,
        issues=[{
            "severity": issue.severity.value,
            "message": issue.message,
            "entity": f"{issue.entity_type} {issue.entity_id}",
            "expected": issue.expected,
            "actual": issue.actual,
            "difference": issue.difference,
        } for issue in gate.issues],
    )


def build_question(issue: VerificationIssue, index: EvidenceIndex) -> VerificationQuestionVM:
    field_observation = index.field(issue.field_observation_id)
    return VerificationQuestionVM(
        issue_id=issue.issue_id,
        question=issue.question,
        why_it_matters=issue.depends_on,
        reason=issue.reason.value,
        reason_plain=VERIFICATION_REASON_TEXT.get(issue.reason, "This entry needs to be checked by a person."),
        page_number=issue.page_number or (field_observation.page_number if field_observation else None),
        column_ref=field_observation.column_ref if field_observation else None,
        column_label=COLUMN_LABELS.get(field_observation.column_ref) if field_observation else None,
        ai_reading=None if field_observation is None else _as_text(field_observation.extracted_value),
        ai_raw_text=field_observation.raw_text if field_observation else None,
        proposed_value=issue.proposed_value,
        alternatives=list(issue.alternatives),
        region=field_observation.evidence_region if field_observation else None,
        critical=issue.critical,
        resolved=issue.resolved,
    )


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def build_calculations(
    record: ReconciledFardRecord,
    index: EvidenceIndex,
    *,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> list[CalculationVM]:
    """Show the working for each Khewat's area and each owner's share of it.

    Every figure comes from the same functions the validation gates use, so
    what is displayed and what is checked cannot diverge.
    """
    calculations: list[CalculationVM] = []
    for khewat in record.document.khewats:
        steps: list[CalculationStepVM] = []
        for khatauni in khewat.khataunis:
            area, known = _area_display(khatauni.recorded_total_area)
            steps.append(CalculationStepVM(
                label=f"Khatauni {khatauni.khatauni_number} printed total",
                value=area or "not readable",
                note=None if known else "Left out of the total because it could not be read.",
            ))
        total_sarsahi, complete, missing = khewat_total_area_sarsahi(khewat, marla_per_kanal, sarsahi_per_marla)
        calculations.append(CalculationVM(
            id=f"area-{khewat.khewat_id}",
            title=f"Total land in Khewat {khewat.khewat_number or '(number not read)'}",
            steps=steps,
            result=display_sarsahi(total_sarsahi, marla_per_kanal, sarsahi_per_marla),
            uncertain=not complete,
            note=(
                "Each Khatauni is added exactly once. A Khewat total already contains its "
                "Khataunis, so the two are never added together."
                if complete else
                f"Incomplete: {len(missing)} Khatauni(s) have no readable area and are left out."
            ),
            evidence=index.evidence_many([khatauni.source for khatauni in khewat.khataunis]),
        ))

        for owner in khewat.owners:
            interest = resolve_owner_entitlements([owner], khewat, marla_per_kanal, sarsahi_per_marla)[0]
            entitlement = interest.entitlement_sarsahi()
            scope_area = display_sarsahi(interest.area_sarsahi, marla_per_kanal, sarsahi_per_marla)
            steps = [
                CalculationStepVM(
                    label="Land this share applies to",
                    value=scope_area,
                    note=(
                        "The whole Khewat's land that has no separate owner list"
                        if interest.scope == OwnershipScope.KHEWAT
                        else f"Khatauni {', '.join(interest.khatauni_ids)} only"
                    ),
                ),
                CalculationStepVM(
                    label="Recorded share",
                    value=owner.share_fraction or "could not be read",
                    note=f"Printed as: {owner.raw_share_fraction}",
                ),
            ]
            if entitlement is None or not interest.area_complete:
                result = None
            else:
                result = display_sarsahi(int(entitlement), marla_per_kanal, sarsahi_per_marla)
                steps.append(CalculationStepVM(
                    label="Land × share",
                    value=f"{scope_area} × {owner.share_fraction} = {result}",
                ))
            calculations.append(CalculationVM(
                id=f"share-{owner.owner_id}",
                title=f"{owner.normalized_owner_name or owner.raw_owner_name_parentage}'s recorded portion",
                steps=steps,
                result=result,
                uncertain=result is None,
                note=(
                    "This is the area recorded in this Fard. It is not a statement of legal title."
                    if result is not None else
                    "This cannot be calculated because the share or the area could not be read. "
                    "No value has been guessed."
                ),
                evidence=index.evidence(owner.source),
            ))
    return calculations


def build_pages(
    result: ExtractionResult,
    uploaded_pages: tuple[int, ...],
    stated_total: int | None,
) -> list[PageVM]:
    successful = set(result.successful_pages)
    failed = set(result.failed_pages)
    cached = {
        int(warning.split(":")[0].split()[1])
        for warning in result.page_warnings
        if warning.startswith("page ") and "reused cached observation" in warning
    }
    known = sorted(set(uploaded_pages) | successful | failed | set(range(1, (stated_total or 0) + 1)))
    pages: list[PageVM] = []
    for page_number in known:
        if page_number in successful:
            state: Literal["read", "reused_from_cache", "failed", "not_uploaded"] = (
                "reused_from_cache" if page_number in cached else "read"
            )
            message = (
                f"Page {page_number} was already read earlier and did not need reading again."
                if state == "reused_from_cache"
                else f"Page {page_number} has been read."
            )
        elif page_number in failed or page_number in uploaded_pages:
            state = "failed"
            message = (
                f"Page {page_number} could not be processed. "
                "We will not treat the missing page as absent information."
            )
        else:
            state = "not_uploaded"
            message = (
                f"Page {page_number} is referred to by the document but was not uploaded. "
                "Its contents are unknown."
            )
        pages.append(PageVM(
            page_number=page_number,
            state=state,
            message=message,
            stated_total_pages=stated_total,
        ))
    return pages


def build_findings(
    record: ReconciledFardRecord,
    index: EvidenceIndex,
    khewats: list[KhewatVM],
    *,
    unread_pages: list[int] | None = None,
) -> list[FindingVM]:
    """Headline statements.

    ``unread_pages`` is load-bearing, not decoration. Any finding whose value
    is a NEGATIVE claim ("no mortgage", "no mutations") is downgraded to
    "unknown" when a page was not read, because an unread page cannot support
    a claim that something is absent.
    """
    document = record.document
    unread = unread_pages or []
    partial_note = (
        f" Page(s) {', '.join(str(page) for page in unread)} could not be read, so this "
        "counts only what is on the pages that were read."
        if unread else ""
    )
    header = document.document_header
    findings: list[FindingVM] = [
        FindingVM(
            id="village",
            label="Village and Hadbast",
            value=f"{header.village} · Hadbast {header.hadbast_number}",
            tone="info",
            evidence=index.evidence(header.source),
        ),
        FindingVM(
            id="jamabandi-year",
            label="Jamabandi year",
            value=header.jamabandi_year,
            detail="This is the year the ownership snapshot in this record belongs to.",
            tone="info",
            evidence=index.evidence(header.source),
        ),
    ]

    owner_count = sum(len(khewat.owners) for khewat in khewats)
    unreadable_shares = sum(1 for k in khewats for o in k.owners if not o.share_known)
    findings.append(FindingVM(
        id="owners",
        label="Owner entries found",
        value=str(owner_count),
        detail=(
            (f"{unreadable_shares} of these has a share we could not read." if unreadable_shares else "")
            + partial_note
        ) or None,
        tone="warn" if unreadable_shares else ("unknown" if unread else "ok"),
    ))

    incomplete = [k for k in khewats if not k.total_area_complete]
    total_answer_evidence = index.evidence_many([
        khatauni.source for khewat in document.khewats for khatauni in khewat.khataunis
    ])
    if incomplete or unread:
        findings.append(FindingVM(
            id="total-area",
            label="Total recorded land",
            value=None,
            detail=(
                "Some Khataunis have no readable area, so a whole-document total would be "
                "misleading. Each Khewat's own total is shown separately instead."
                if incomplete else
                "A whole-document total is not shown because not every page was read. "
                "Each Khewat's own total, from the pages that were read, is shown separately."
            ),
            tone="unknown",
            evidence=total_answer_evidence,
        ))
    else:
        total_sarsahi = 0
        for khewat in document.khewats:
            subtotal, _complete, _missing = khewat_total_area_sarsahi(khewat)
            total_sarsahi += subtotal
        findings.append(FindingVM(
            id="total-area",
            label="Total recorded land",
            value=display_sarsahi(total_sarsahi),
            detail="Each Khatauni counted exactly once across all Khewats.",
            tone="ok",
            evidence=total_answer_evidence,
        ))

    operative = [m for m in document.mutations if m.is_operative]
    entered = [m for m in document.mutations if not m.is_operative]
    mutations_claim = absence_claim("mutation entries", unread)
    findings.append(FindingVM(
        id="mutations",
        label="Mutations (Inteqal) recorded",
        value=(
            str(len(document.mutations)) if document.mutations
            else ("Unknown" if mutations_claim.uncertain else "None found")
        ),
        detail=(
            f"{len(operative)} sanctioned, {len(entered)} not sanctioned. "
            "Only a sanctioned mutation can change who owns the land." + partial_note
            if document.mutations else mutations_claim.text
        ),
        tone="warn" if operative else (mutations_claim.tone if not document.mutations else "info"),
        evidence=index.evidence_many([m.source for m in document.mutations]),
    ))

    mortgaged = [k for k in khewats if k.mortgage and k.mortgage.tone == "warn"]
    mortgages_claim = absence_claim("mortgage entries", unread)
    if mortgaged:
        mortgage_value: str | None = str(len(mortgaged))
        mortgage_detail = (
            "A mortgage entry was found with no release recorded in this document. "
            "Confirm the current position with the bank or registry." + partial_note
        )
        mortgage_tone: Tone = "warn"
    else:
        mortgage_value = "Unknown" if mortgages_claim.uncertain else "None found"
        mortgage_detail = mortgages_claim.text
        mortgage_tone = mortgages_claim.tone
    findings.append(FindingVM(
        id="mortgages",
        label="Mortgages and charges",
        value=mortgage_value,
        detail=mortgage_detail,
        tone=mortgage_tone,
    ))
    return findings


def build_document_vm(
    session_id: str,
    result: ExtractionResult,
    record: ReconciledFardRecord | None,
    *,
    uploaded_pages: tuple[int, ...] = (),
    scenario_key: str | None = None,
    scenario_label: str | None = None,
    marla_per_kanal: int = 20,
    sarsahi_per_marla: int = 9,
) -> DocumentVM:
    status = result.status or DocumentStatus.FAILED
    title, explanation, tone = STATUS_TEXT[status]
    index = EvidenceIndex(result.observations)
    stated_total = _stated_total_pages(result.document)
    pages = build_pages(result, uploaded_pages, stated_total)
    unread = [page.page_number for page in pages if page.state in ("failed", "not_uploaded")]
    questions = [build_question(issue, index) for issue in result.verification_issues]

    # Computed once, from the same unread-pages list the Summary screen
    # itself uses, so no screen or Ask answer can ever compose a
    # different "no X found" claim for the same document state.
    mutations_absence = _absence_vm(absence_claim("mutation entries", unread))
    remarks_absence = _absence_vm(absence_claim("Column 8 remarks", unread))
    possession_absence = _absence_vm(absence_claim("cultivation or possession entries", unread))
    mortgages_absence = _absence_vm(absence_claim("mortgage entries", unread))

    if record is None or result.document is None:
        return DocumentVM(
            summary=SummaryVM(
                session_id=session_id,
                scenario_key=scenario_key,
                scenario_label=scenario_label,
                status=status.value,
                status_title=title,
                status_explanation=explanation,
                status_tone=tone,
                is_readable=False,
                pages=pages,
                unread_pages=unread,
                stated_total_pages=stated_total,
                open_questions=len([q for q in questions if not q.resolved]),
                warnings=list(result.page_warnings),
                errors=list(result.parser_errors),
            ),
            questions=questions,
            mutations_absence=mutations_absence,
            remarks_absence=remarks_absence,
            possession_absence=possession_absence,
            mortgages_absence=mortgages_absence,
        )

    document = record.document
    khewats = [
        build_khewat(khewat, record, index,
                     marla_per_kanal=marla_per_kanal, sarsahi_per_marla=sarsahi_per_marla)
        for khewat in document.khewats
    ]
    owners = [owner for khewat in khewats for owner in khewat.owners]

    cultivation = [
        CultivationVM(
            person_name=interest.person_name,
            khewat_number=next(
                (k.khewat_number for k in document.khewats if k.khewat_id == interest.khewat_id), None
            ),
            khatauni_number=next(
                (kh.khatauni_number for k in document.khewats for kh in k.khataunis
                 if kh.khatauni_id == interest.khatauni_id), None
            ),
            relationship=interest.relationship.value,
            relationship_plain=_CULTIVATION_PLAIN.get(
                interest.relationship.value, "The arrangement is recorded but not classified."
            ),
            raw_text=interest.raw_relationship_text,
            share=interest.share_fraction,
            status=interest.status.value,
            evidence=index.evidence(interest.source),
        )
        for interest in document.cultivation_interests
    ]

    gates = [build_gate(gate) for gate in record.validation_report.gates]
    summary = SummaryVM(
        session_id=session_id,
        scenario_key=scenario_key,
        scenario_label=scenario_label,
        status=status.value,
        status_title=title,
        status_explanation=explanation,
        status_tone=tone,
        is_readable=True,
        header=HeaderVM(
            village=document.document_header.village,
            hadbast_number=document.document_header.hadbast_number,
            jamabandi_year=document.document_header.jamabandi_year,
            lr_number=document.document_header.lr_number,
            district=document.document_header.district,
            tehsil=document.document_header.tehsil,
            layout=document.layout.value,
            layout_plain=_LAYOUT_PLAIN.get(document.layout.value, "The column layout is not known."),
            evidence=index.evidence(document.document_header.source),
        ),
        counts=CountsVM(
            khewats=len(document.khewats),
            khataunis=sum(len(k.khataunis) for k in document.khewats),
            khasras=sum(len(kh.khasras) for k in document.khewats for kh in k.khataunis),
            owners=len(owners),
            mutations=len(document.mutations),
            remarks=len(document.remarks),
            cultivation_entries=len(document.cultivation_interests),
        ),
        findings=build_findings(record, index, khewats, unread_pages=unread),
        pages=pages,
        unread_pages=unread,
        stated_total_pages=stated_total,
        gates=gates,
        gates_passed=record.validation_report.passed,
        open_questions=len([q for q in questions if not q.resolved]),
        warnings=list(result.page_warnings),
        errors=list(result.parser_errors),
    )

    return DocumentVM(
        summary=summary,
        khewats=khewats,
        owners=owners,
        mutations=[build_mutation(m, document, index) for m in document.mutations],
        remarks=[build_remark(r, document, index) for r in document.remarks],
        mortgages=[k.mortgage for k in khewats if k.mortgage is not None],
        cultivation=cultivation,
        questions=questions,
        calculations=build_calculations(
            record, index, marla_per_kanal=marla_per_kanal, sarsahi_per_marla=sarsahi_per_marla
        ),
        mutations_absence=mutations_absence,
        remarks_absence=remarks_absence,
        possession_absence=possession_absence,
        mortgages_absence=mortgages_absence,
    )
