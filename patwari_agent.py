"""Compatibility entry point.

The implementation now lives in the digital_patwari/ package (models,
normalization, validation, document_io, extraction, providers/gemini,
reconciliation, query, cli) per CLAUDE.md's preferred module direction.
This module re-exports the same public names so existing scripts,
notebooks, and tests that do `from patwari_agent import X` keep working
unchanged, and remains directly runnable: `python patwari_agent.py ...`.
"""
from __future__ import annotations

from digital_patwari.document_io import (
    SUPPORTED_MIME_TYPES,
    load_document_parts,
    resolve_input_paths,
)
from digital_patwari.extraction import (
    EXTRACTION_SYSTEM_PROMPT,
    ExtractionResult,
    FardExtractionParser,
    StructuredLLMClient,
)
from digital_patwari.models import (
    AreaKanalMarla,
    AreaKanalMarlaSarsahi,
    AreaObservation,
    AreaScope,
    CultivationInterest,
    CultivationRelationship,
    DigitalPatwariDocument,
    DocumentHeader,
    DocumentLayout,
    EvidenceProvenance,
    ExtractionConfidence,
    ExtractionStatus,
    GateResult,
    InterestScope,
    Khasra,
    Khatauni,
    Khewat,
    Mutation,
    MutationStatus,
    MutationTransferScope,
    MutationType,
    NonEmptyString,
    Owner,
    ParcelInterest,
    PartyRole,
    Remark,
    RemarkCategory,
    RemarkTarget,
    SourceReference,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    is_operative_for_derived_ownership,
)
from digital_patwari.derived_ownership import (
    AcquiredPosition,
    AppliedMutationEffect,
    DerivedOwnershipPosition,
    KhewatDerivedOwnership,
    derive_document_ownership,
    derive_khewat_ownership,
    format_fraction,
    format_over_denominator,
)
from digital_patwari.encumbrance import MortgageFinding, MortgageStatus, resolve_mortgage_status
from digital_patwari.interests import (
    ResolvedParcelInterest,
    classify_person_interest_scope,
    cultivation_share_reconciliation,
    is_khud_kasht,
    resolve_cultivation_interests,
    resolve_parcel_interests,
)
from digital_patwari.normalization import (
    add_shares,
    area_from_share,
    decimal_kanal_to_kanal_marla,
    decimal_kanal_to_sarsahi,
    decimal_marla_to_marla_sarsahi,
    normalize_optional_text,
    parse_fraction,
    raw_share_denominator,
    share_denominator_matches_total_marla,
    subtract_shares,
)
from digital_patwari.ownership import (
    EffectiveOwnershipInterest,
    OwnershipScope,
    inheriting_khataunis,
    khatauni_governance,
    owners_by_khatauni,
    pooled_owners,
    resolve_owner_entitlements,
)
from digital_patwari.providers.gemini import MyLLMAdapter
from digital_patwari.query import Answer, FardQueryEngine
from digital_patwari.reconciliation import (
    OwnershipReconciliation,
    OwnershipStatus,
    ReconciledFardRecord,
    reconcile,
)
from digital_patwari.terminology import (
    REVENUE_TERMS,
    RevenueTerm,
    TermCategory,
    TermValidation,
    find_terms,
    is_reliable,
    lookup_term,
)
from digital_patwari.validation import (
    run_axiom_gates,
    validate_ag01_khewat_share_summation,
    validate_ag02_linkage_and_integrity,
    validate_ag03_area_consistency,
    validate_ag04_document_completeness,
    validate_ag05_mutation_share_area_consistency,
    validate_ag06_area_observation_scopes,
    validate_ag07_parcel_interest_resolution,
)

if __name__ == "__main__":
    from digital_patwari.cli import main

    raise SystemExit(main())
