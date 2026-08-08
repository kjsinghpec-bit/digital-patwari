"""Literal, provider-neutral observations for one source page.

The observation layer deliberately sits in front of the canonical domain
model.  It preserves what was seen (including empty ruled cells and malformed
values) while ``assembly.py`` decides which supported facts can safely enter
``DigitalPatwariDocument``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from digital_patwari.models import (
    DigitalPatwariDocument,
    EvidenceProvenance,
    ExtractionConfidence,
    ExtractionStatus,
)


class PageCellObservation(BaseModel):
    """A literal reading of one visible table cell or page region."""

    model_config = ConfigDict(extra="forbid")
    column_ref: str
    raw_text: str
    is_blank: bool = False
    row_ref: str | None = None
    region: str | None = None
    status: ExtractionStatus = ExtractionStatus.PRESENT
    confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    provenance: EvidenceProvenance = EvidenceProvenance.MACHINE_READ
    uncertainty: str | None = None

    @model_validator(mode="after")
    def blank_cells_are_literal(self) -> "PageCellObservation":
        if self.is_blank and self.raw_text != "":
            raise ValueError("an explicit blank cell must preserve raw_text as an empty string")
        return self


class VerificationStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"


class VerificationReason(str, Enum):
    UNREADABLE = "UNREADABLE"
    AMBIGUOUS = "AMBIGUOUS"
    STRUCTURAL_CONFLICT = "STRUCTURAL_CONFLICT"
    INVALID_FORMAT = "INVALID_FORMAT"
    CALCULATION_MISMATCH = "CALCULATION_MISMATCH"


class VerificationAction(str, Enum):
    CONFIRM = "CONFIRM"
    SELECT_ALTERNATIVE = "SELECT_ALTERNATIVE"
    ENTER_CORRECTION = "ENTER_CORRECTION"


class FieldObservation(BaseModel):
    """UI-ready evidence and verification state for one extracted field."""

    model_config = ConfigDict(extra="forbid")
    observation_id: str
    field_path: list[str | int]
    entity_type: str
    entity_id: str | None = None
    extracted_value: Any = None
    raw_text: str
    confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    page_number: int = Field(ge=1)
    column_ref: str
    evidence_region: str | None = None
    provenance: EvidenceProvenance = EvidenceProvenance.MACHINE_READ
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED
    verification_reason: VerificationReason | None = None
    uncertainty_reason: str | None = None
    corrected_value: Any = None
    verifier_id: str | None = None
    verification_session_id: str | None = None
    verified_at: datetime | None = None

    @property
    def effective_value(self) -> Any:
        return self.corrected_value if self.verification_status == VerificationStatus.CORRECTED else self.extracted_value


class VerificationIssue(BaseModel):
    """One focused question suitable for a citizen verification screen."""

    model_config = ConfigDict(extra="forbid")
    issue_id: str
    field_observation_id: str
    page_number: int | None = Field(default=None, ge=1)
    field_path: list[str | int] = Field(default_factory=list)
    reason: VerificationReason
    question: str
    proposed_value: Any = None
    alternatives: list[Any] = Field(default_factory=list)
    depends_on: str
    critical: bool = True
    resolved: bool = False


class VerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue_id: str
    action: VerificationAction
    verifier_id: str
    verification_session_id: str
    selected_alternative: Any = None
    correction: Any = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def action_has_value(self) -> "VerificationResponse":
        if self.action == VerificationAction.SELECT_ALTERNATIVE and self.selected_alternative is None:
            raise ValueError("selected_alternative is required for SELECT_ALTERNATIVE")
        if self.action == VerificationAction.ENTER_CORRECTION and self.correction is None:
            raise ValueError("correction is required for ENTER_CORRECTION")
        return self


class VerificationRecord(BaseModel):
    """Immutable audit record; the AI value is never overwritten."""

    model_config = ConfigDict(extra="forbid")
    issue_id: str
    field_observation_id: str
    original_value: Any = None
    corrected_value: Any = None
    action: VerificationAction
    verifier_id: str
    verification_session_id: str
    timestamp: datetime


class StructuralOperationType(str, Enum):
    UPDATE_FIELD = "UPDATE_FIELD"
    ADD_ROW = "ADD_ROW"
    DELETE_ROW = "DELETE_ROW"
    SPLIT_ROW = "SPLIT_ROW"
    MERGE_ROWS = "MERGE_ROWS"


class StructuralCorrectionRequest(BaseModel):
    """Provider-neutral command for changing canonical structure offline."""

    model_config = ConfigDict(extra="forbid")
    operation_id: str
    operation: StructuralOperationType
    page_number: int = Field(ge=1)
    target_list_path: list[str | int]
    row_indices: list[int] = Field(default_factory=list)
    corrected_rows: list[dict[str, Any]] = Field(default_factory=list)
    field_path: list[str | int] = Field(default_factory=list)
    corrected_value: Any = None
    human_reason: str | None = None
    operator_id: str
    verification_session_id: str
    critical: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def operation_shape_is_complete(self) -> "StructuralCorrectionRequest":
        if self.operation in {StructuralOperationType.ADD_ROW, StructuralOperationType.DELETE_ROW}:
            if not self.human_reason or not self.human_reason.strip():
                raise ValueError(f"{self.operation.value} requires a human_reason")
        if self.operation == StructuralOperationType.UPDATE_FIELD:
            if len(self.row_indices) != 1 or not self.field_path:
                raise ValueError("UPDATE_FIELD requires one row index and a field_path")
        elif self.operation == StructuralOperationType.ADD_ROW:
            if self.row_indices or len(self.corrected_rows) != 1:
                raise ValueError("ADD_ROW requires exactly one corrected row and no source row")
        elif self.operation == StructuralOperationType.DELETE_ROW:
            if len(self.row_indices) != 1 or self.corrected_rows:
                raise ValueError("DELETE_ROW requires exactly one source row")
        elif self.operation == StructuralOperationType.SPLIT_ROW:
            if len(self.row_indices) != 1 or len(self.corrected_rows) < 2:
                raise ValueError("SPLIT_ROW requires one source row and at least two corrected rows")
        elif self.operation == StructuralOperationType.MERGE_ROWS:
            if len(set(self.row_indices)) < 2 or len(self.corrected_rows) != 1:
                raise ValueError("MERGE_ROWS requires at least two source rows and one corrected row")
        return self


class StructuralCorrectionRecord(BaseModel):
    """Immutable evidence-preserving audit entry for a structural operation."""

    model_config = ConfigDict(extra="forbid")
    operation_id: str
    operation: StructuralOperationType
    page_number: int
    target_list_path: list[str | int]
    row_indices: list[int]
    original_rows: list[dict[str, Any]] = Field(default_factory=list)
    corrected_rows: list[dict[str, Any]] = Field(default_factory=list)
    original_raw_evidence: list[str] = Field(default_factory=list)
    human_reason: str | None = None
    operator_id: str
    verification_session_id: str
    timestamp: datetime
    critical: bool = True
    verification_status: VerificationStatus = VerificationStatus.NEEDS_REVIEW
    confirmed_by: str | None = None
    confirmation_session_id: str | None = None
    confirmed_at: datetime | None = None


class StructuralConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation_id: str
    verifier_id: str
    verification_session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PageObservation(BaseModel):
    """Everything observed on a single physical page.

    ``canonical_payload`` is an untrusted candidate mapping.  Keeping it as a
    mapping is intentional: malformed fractions or areas must survive parsing
    of the observation envelope so the assembler can warn and salvage other
    rows from the same page.
    """

    model_config = ConfigDict(extra="forbid")
    observation_schema_version: str = "3_STRUCTURAL_VERIFICATION"
    page_number: int = Field(ge=1)
    cells: list[PageCellObservation] = Field(default_factory=list)
    fields: list[FieldObservation] = Field(default_factory=list)
    verification_issues: list[VerificationIssue] = Field(default_factory=list)
    verification_history: list[VerificationRecord] = Field(default_factory=list)
    structural_history: list[StructuralCorrectionRecord] = Field(default_factory=list)
    # The union advertises the complete canonical schema to structured-output
    # providers, while the raw mapping branch lets malformed visible values
    # survive long enough for deterministic salvage and warnings.
    canonical_payload: DigitalPatwariDocument | dict[str, Any]
