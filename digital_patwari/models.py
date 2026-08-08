from __future__ import annotations

from enum import Enum
from fractions import Fraction
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from typing_extensions import Annotated

from digital_patwari.normalization import parse_fraction

# =====================================================================
# ENUMS
# =====================================================================

class ExtractionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ExtractionStatus(str, Enum):
    PRESENT = "present"
    NOT_PRESENT = "not_present"
    ILLEGIBLE = "illegible"
    UNCERTAIN = "uncertain"

class RemarkTarget(str, Enum):
    KHEWAT = "Khewat"
    KHATAUNI = "Khatauni"
    OWNER = "Owner"
    KHASRA = "Khasra"

class RemarkCategory(str, Enum):
    APPROVED_MUTATION = "Approved_Mutation"
    PENDING_MUTATION = "Pending_Mutation"
    LEGAL_ENCUMBRANCE = "Legal_Encumbrance"
    RENT_DETAILS = "Rent_Details"
    INFORMATIONAL = "Informational"

class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"

class MutationStatus(str, Enum):
    """Mutation lifecycle. A mutation NUMBER appearing in Column 8 is NOT
    evidence of sanction -- only classify as APPROVED when the record's own
    wording supports it (e.g. "manzoor"/"sanctioned").

    Only APPROVED is operative for derived ownership (see
    `is_operative_for_derived_ownership`). Every other state is recorded
    and explained but must never move a share.

    APPROVED/PENDING are the coarse states the pipeline has always used and
    remain the canonical operative/non-operative pair. The finer states let
    the record's actual stage be preserved when the wording supports it,
    without any of them silently becoming operative."""
    REFERENCED = "Referenced"                              # merely cited elsewhere
    ENTERED = "Entered"                                    # entered in the register
    PRESENTED_FOR_VERIFICATION = "Presented_For_Verification"  # paratal
    PRESENTED_FOR_SANCTION = "Presented_For_Sanction"
    PENDING = "Pending"                                    # generic not-yet-sanctioned
    APPROVED = "Approved"                                  # sanctioned / manzoor
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
    UNCERTAIN = "Uncertain"


#: The ONLY status that may move a share in the derived-ownership engine.
#: Kept as a function (not a set literal inline) so every caller shares one
#: definition and a future domain change has exactly one edit site.
def is_operative_for_derived_ownership(status: "MutationStatus") -> bool:
    return status == MutationStatus.APPROVED


class DocumentLayout(str, Enum):
    """Fards are not all 8-column. Legacy records use roughly 12 columns
    with a different arrangement. Never force a legacy layout through
    modern-8-column column semantics."""
    MODERN_8_COLUMN = "modern_8_column"
    LEGACY_12_COLUMN = "legacy_12_column"
    UNKNOWN_LAYOUT = "unknown_layout"


class AreaScope(str, Enum):
    """What a given area figure actually measures. Column 7 mixes parcel
    areas, Khatauni subtotals, Khewat totals and document totals in one
    visual column -- they are representations of overlapping land, NOT
    addends. Never sum figures of differing scope."""
    KHASRA_AREA = "khasra_area"
    KHATAUNI_SUBTOTAL = "khatauni_subtotal"
    KHEWAT_TOTAL = "khewat_total"
    OTHER_ACCOUNT_TOTAL = "other_account_total"
    DOCUMENT_TOTAL = "document_total"
    UNKNOWN_AREA_SCOPE = "unknown_area_scope"


class InterestScope(str, Enum):
    """How a person's interest in land is scoped. A specific-Khasra
    purchase must never be multiplied against the whole Khewat."""
    UNDIVIDED_KHEWAT_SHARE = "undivided_khewat_share"
    SPECIFIC_KHASRA_INTEREST = "specific_khasra_interest"
    CULTIVATION_POSSESSION_ONLY = "cultivation_possession_only"
    MUTATION_DERIVED_OWNERSHIP = "mutation_derived_ownership"
    MIXED_INTEREST = "mixed_interest"
    UNKNOWN_REQUIRES_VERIFICATION = "unknown_requires_verification"


class PartyRole(str, Enum):
    """Role a named party plays in a transaction. Mushtari (purchaser) is
    NOT automatically a whole-Khewat owner -- the scope of what was bought
    must come from the record, not from the role word alone."""
    TRANSFEROR = "transferor"      # baya / seller
    TRANSFEREE = "transferee"      # mushtari / purchaser
    MORTGAGEE = "mortgagee"
    MORTGAGOR = "mortgagor"
    UNKNOWN = "unknown"


class CultivationRelationship(str, Enum):
    """Possession/cultivation relationship -- a separate dimension from
    ownership. Owner != cultivator and cultivator != owner."""
    KHUD_KASHT = "khud_kasht"          # self-cultivation by the owner
    MUZARA = "muzara"                  # tenant
    GAIR_MUMKIN = "gair_mumkin"        # uncultivable
    MAQBUZA_MALKAN = "maqbuza_malkan"  # in owners' possession
    OTHER = "other"
    UNKNOWN = "unknown"


class EvidenceProvenance(str, Enum):
    MACHINE_READ = "machine_read"
    USER_CORRECTED = "user_corrected"

class MutationType(str, Enum):
    SALE = "Sale"
    INHERITANCE = "Inheritance"
    GIFT = "Gift"
    PARTITION = "Partition"
    CORRECTION = "Correction"
    MORTGAGE = "Mortgage"
    RELEASE_DISCHARGE = "Release_Discharge"
    OTHER = "Other"

class MutationTransferScope(str, Enum):
    UNDIVIDED_SHARE = "Undivided_Share"
    SPECIFIC_KHASRA = "Specific_Khasra"

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]

# =====================================================================
# SCHEMA MODELS
# =====================================================================

class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1)
    # From the source's own printed pagination (e.g. "Page 5 of 8" -> 8).
    # None when the page doesn't state a total. Used by AG-04 to catch an
    # incomplete upload rather than silently analyzing a partial Fard.
    total_pages: int | None = Field(default=None, ge=1)
    # Which column/region of the Fard this came from (e.g. "3" for the
    # ownership column, "8" for Vishesh Kathan). Free text because legacy
    # layouts do not use the modern 8-column numbering.
    column_ref: str | None = None
    region: str | None = None
    status: ExtractionStatus = ExtractionStatus.PRESENT
    confidence: ExtractionConfidence = ExtractionConfidence.MEDIUM
    provenance: EvidenceProvenance = EvidenceProvenance.MACHINE_READ
    raw_text: str | None = None

class AreaKanalMarlaSarsahi(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kanal: int = Field(default=0, ge=0)
    marla: int = Field(default=0, ge=0)
    sarsahi: int = Field(default=0, ge=0)
    raw_text: str | None = None
    status: ExtractionStatus = ExtractionStatus.PRESENT

    def total_marla(self, marla_per_kanal: int = 20) -> int:
        return (self.kanal * marla_per_kanal) + self.marla

    def total_sarsahi(self, marla_per_kanal: int = 20, sarsahi_per_marla: int = 9) -> int:
        return (self.total_marla(marla_per_kanal) * sarsahi_per_marla) + self.sarsahi

# Backward-compatible alias: earlier revisions of this schema used
# AreaKanalMarla (kanal/marla only, no sarsahi unit).
AreaKanalMarla = AreaKanalMarlaSarsahi

class Remark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: RemarkTarget
    target_id: NonEmptyString
    remark_category: RemarkCategory
    raw_text: NonEmptyString
    parsed_meaning: str | None = None
    source: SourceReference | None = None

class Mutation(BaseModel):
    """A structured Column-8 mutation (Inteqal), distinct from a general
    Remark. Only fields the source text actually supports should be
    populated — leave mutation_type/transfer_scope as None rather than
    guessing when the record doesn't make them explicit."""
    model_config = ConfigDict(extra="forbid")
    mutation_id: NonEmptyString
    target_type: RemarkTarget
    target_id: NonEmptyString
    status: MutationStatus
    mutation_type: MutationType | None = None
    transfer_scope: MutationTransferScope | None = None
    affected_khasra_numbers: list[str] = Field(default_factory=list)
    # Only set when mutation_type == RELEASE_DISCHARGE: the mutation_id of
    # the earlier Mortgage entry this one discharges/releases. Lets a
    # mortgage's current status be resolved deterministically instead of
    # assuming "mortgage mentioned" means "mortgage still active".
    discharges_mutation_id: str | None = None

    # -- transaction detail (Part 50). All optional: populate only what the
    # -- record actually states; never infer a party or a share.
    mutation_date: str | None = None          # kept as source text, not parsed to a date type
    sequence_index: int | None = None         # explicit chronological order when dates are unreliable
    transferor_owner_id: str | None = None    # the Owner row losing the share
    transferee_name: str | None = None        # acquirer, who may have no Owner row yet in this Jamabandi
    transferor_name: str | None = None
    # Exact share moved by this mutation, as a normalized fraction string.
    # None when the record does not state a share (e.g. a pure mortgage).
    share_transferred: str | None = None
    # Area the record itself states was transferred, if any. Cross-checked
    # against share_transferred x scope area by AG-05.
    area_transferred: AreaKanalMarlaSarsahi | None = None
    sanction_wording: str | None = None       # the exact phrase the status was read from

    raw_text: NonEmptyString
    parsed_meaning: str | None = None
    extraction_status: ExtractionStatus = ExtractionStatus.PRESENT
    source: SourceReference | None = None

    @field_validator("share_transferred", mode="before")
    @classmethod
    def normalize_share_transferred(cls, value: Any) -> Any:
        return None if value is None else parse_fraction(value)

    @property
    def transferred_fraction(self) -> Fraction | None:
        return None if self.share_transferred is None else Fraction(self.share_transferred)

    @property
    def is_operative(self) -> bool:
        """Whether this mutation may move a share in the derived-ownership
        engine. Deliberately narrow -- see is_operative_for_derived_ownership."""
        return is_operative_for_derived_ownership(self.status)

class DocumentHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")
    village: NonEmptyString
    hadbast_number: NonEmptyString
    jamabandi_year: NonEmptyString
    lr_number: NonEmptyString
    district: str | None = None
    tehsil: str | None = None
    source: SourceReference | None = None

class Owner(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: NonEmptyString
    khewat_id: NonEmptyString
    # None => share_fraction pools against the WHOLE Khewat (single ownership
    # group spanning every Khatauni). Set => share_fraction pools only against
    # this specific Khatauni's own area -- real Fards routinely split one
    # Khewat into Khataunis with entirely disjoint owner groups (verified
    # against samples/real_fard/Chaman Lal Sanghol.pdf), and a Khewat-wide
    # multiply would attribute land the owner has no stake in.
    khatauni_id: str | None = None
    raw_owner_name_parentage: NonEmptyString
    normalized_owner_name: str | None = None
    raw_share_fraction: NonEmptyString
    share_fraction: NonEmptyString
    status: ExtractionStatus = ExtractionStatus.PRESENT
    source: SourceReference | None = None

    @field_validator("share_fraction", mode="before")
    @classmethod
    def normalize_share_fraction(cls, value: Any) -> str:
        return parse_fraction(value)

    @property
    def fraction(self) -> Fraction:
        return Fraction(self.share_fraction)

class Khasra(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khasra_id: NonEmptyString
    khasra_number: NonEmptyString
    # Murabba (the larger mapped grouping, printed as e.g. "31 // 18" where
    # 31 is the Murabba and 18 the Khasra). Kept STRICTLY separate from
    # khasra_number -- never merged into one ambiguous identifier.
    murabba_number: str | None = None
    khatauni_id: NonEmptyString
    area_kanal_marla: AreaKanalMarlaSarsahi
    raw_soil_classification: str | None = None
    normalized_soil_classification: str | None = None
    normalized_irrigation_source: str | None = None
    normalized_cultivation_status: str | None = None
    status: ExtractionStatus = ExtractionStatus.PRESENT
    source: SourceReference | None = None

class Khatauni(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khatauni_id: NonEmptyString
    khewat_id: NonEmptyString
    raw_cultivator_name: str | None = None
    raw_possession_type: str | None = None
    # Expected sum of Khatauni-scoped Owner.share_fraction values (Owners
    # with khatauni_id == this Khatauni). Only meaningful when this
    # Khatauni has its own disjoint owner group; defaults to "1/1" like
    # Khewat.total_share.
    raw_total_share: NonEmptyString = "1/1"
    total_share: NonEmptyString = "1/1"
    recorded_total_area: AreaKanalMarlaSarsahi | None = None
    khasras: list[Khasra] = Field(default_factory=list)
    source: SourceReference | None = None

    @field_validator("total_share", mode="before")
    @classmethod
    def normalize_total_share(cls, value: Any) -> str:
        return parse_fraction(value)

    @property
    def expected_total_share(self) -> Fraction:
        return Fraction(self.total_share)

class Khewat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    khewat_id: NonEmptyString
    owner_group_ref: str | None = None
    raw_total_share: NonEmptyString = "1/1"
    total_share: NonEmptyString = "1/1"
    owners: list[Owner] = Field(default_factory=list)
    khataunis: list[Khatauni] = Field(default_factory=list)
    source: SourceReference | None = None

    @field_validator("total_share", mode="before")
    @classmethod
    def normalize_total_share(cls, value: Any) -> str:
        return parse_fraction(value)

    @property
    def expected_total_share(self) -> Fraction:
        return Fraction(self.total_share)

class ParcelInterest(BaseModel):
    """A person's interest in SPECIFIC Khasra parcels, as opposed to an
    undivided fractional share of a whole Khewat.

    This is the Mushtari (purchaser) case: someone who bought named Khasra
    numbers holds those parcels, NOT a fraction of the entire Khewat. Their
    area is the sum of the named parcels' own areas -- multiplying any
    fraction against the whole Khewat here would be wrong.

    Being recorded as a purchaser establishes purchaser status only; the
    SCOPE of what was purchased comes from the named khasra_ids, the linked
    mutation, and the surrounding record -- never from the role word alone."""
    model_config = ConfigDict(extra="forbid")
    parcel_interest_id: NonEmptyString
    person_name: NonEmptyString
    khewat_id: NonEmptyString
    khatauni_id: str | None = None
    khasra_ids: list[str] = Field(default_factory=list)
    role: PartyRole = PartyRole.TRANSFEREE
    scope: InterestScope = InterestScope.SPECIFIC_KHASRA_INTEREST
    # Links this interest back to the Column-8 mutation that created it, so
    # a pending/rejected transaction never silently reads as settled fact.
    mutation_id: str | None = None
    status: ExtractionStatus = ExtractionStatus.PRESENT
    source: SourceReference | None = None


class CultivationInterest(BaseModel):
    """A person's cultivation/possession relationship to a Khatauni --
    the Girdawari dimension, kept structurally separate from ownership.

    Owner != cultivator and cultivator != owner. A mutation that changes
    ownership does not by itself prove possession changed, and matching
    ownership to cultivation is NOT required -- a difference between them
    can be entirely legitimate and meaningful."""
    model_config = ConfigDict(extra="forbid")
    cultivation_interest_id: NonEmptyString
    person_name: NonEmptyString
    khewat_id: NonEmptyString
    khatauni_id: NonEmptyString
    relationship: CultivationRelationship = CultivationRelationship.UNKNOWN
    raw_relationship_text: str | None = None
    # Fraction of the cultivation scope, when the record states one. This
    # reconciles INDEPENDENTLY of ownership shares -- never cross-checked
    # against them as if they had to agree.
    share_fraction: str | None = None
    status: ExtractionStatus = ExtractionStatus.PRESENT
    source: SourceReference | None = None

    @field_validator("share_fraction", mode="before")
    @classmethod
    def normalize_share_fraction(cls, value: Any) -> Any:
        return None if value is None else parse_fraction(value)

    @property
    def fraction(self) -> Fraction | None:
        return None if self.share_fraction is None else Fraction(self.share_fraction)


class AreaObservation(BaseModel):
    """One area figure as printed somewhere in the document, tagged with
    what it actually measures.

    Column 7 mixes parcel areas, Khatauni subtotals, Khewat totals and
    document totals in a single visual column. They overlap: a Khewat total
    already contains its Khataunis' subtotals, which already contain their
    Khasras' areas. Recording scope explicitly is what stops the engine
    from ever summing across scopes, and lets a repeated printed total be
    recognised as a repetition rather than as additional land."""
    model_config = ConfigDict(extra="forbid")
    observation_id: NonEmptyString
    scope: AreaScope
    area: AreaKanalMarlaSarsahi
    khewat_id: str | None = None
    khatauni_id: str | None = None
    khasra_id: str | None = None
    source: SourceReference | None = None


class DigitalPatwariDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "4_DOMAIN_INTELLIGENCE"
    document_header: DocumentHeader
    layout: DocumentLayout = DocumentLayout.UNKNOWN_LAYOUT
    khewats: list[Khewat] = Field(default_factory=list)
    remarks: list[Remark] = Field(default_factory=list)
    mutations: list[Mutation] = Field(default_factory=list)
    parcel_interests: list[ParcelInterest] = Field(default_factory=list)
    cultivation_interests: list[CultivationInterest] = Field(default_factory=list)
    area_observations: list[AreaObservation] = Field(default_factory=list)

# =====================================================================
# VALIDATION REPORT MODELS
# =====================================================================

class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate_id: str
    severity: ValidationSeverity
    message: str
    entity_type: str
    entity_id: str
    expected: str | None = None
    actual: str | None = None
    difference: str | None = None

class GateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate_id: str
    passed: bool
    checked_entities: int = Field(ge=0)
    skipped_entities: int = Field(default=0, ge=0)
    issues: list[ValidationIssue] = Field(default_factory=list)

class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    gates: list[GateResult]

    @property
    def issues(self) -> list[ValidationIssue]:
        return [issue for gate in self.gates for issue in gate.issues]
