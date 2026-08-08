from __future__ import annotations

import asyncio
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import pydantic
from pydantic import BaseModel

from digital_patwari.assembly import assemble_page_observations
from digital_patwari.cache import PageObservationCache, page_cache_key
from digital_patwari.document_io import load_document_parts
from digital_patwari.models import DigitalPatwariDocument
from digital_patwari.observations import PageObservation, VerificationIssue
from digital_patwari.validation import ValidationReport, run_axiom_gates

EXTRACTION_SYSTEM_PROMPT = """
You extract one Punjab land-revenue page into a literal PageObservation.

Observation envelope rules:
- Set PageObservation.page_number to the supplied physical page number.
- Emit a PageCellObservation for every meaningful visible cell/region before
  forming canonical_payload. Preserve its exact raw_text, column_ref, status,
  confidence, provenance and uncertainty. A visibly blank ruled cell is not
  missing data: emit raw_text="" and is_blank=true.
- canonical_payload is a page-local candidate DigitalPatwariDocument. Do not
  clean malformed visible values to make it validate; preserve them there and
  in the literal cells so the deterministic assembler can warn and salvage.
- Emit FieldObservation records for extracted fields, with stable field_path,
  extracted_value, exact raw_text, confidence, page_number, column_ref,
  evidence_region, verification_status and uncertainty_reason. For NEEDS_REVIEW
  fields emit one focused VerificationIssue with proposed value/alternatives
  and a plain-language explanation of what depends on the answer.

Reading process -- follow this order, do not skip steps:
0. Transcribe the original Gurmukhi/Urdu/Persian revenue text first, exactly as printed. Only after
   transcribing do you classify structure (which column, which entity) and only after that do you form
   an English interpretation. Never translate first and then reason from the translation alone -- reason
   from the original text. For any word or number you cannot read with confidence, state the possible
   readings and mark that field's status as ILLEGIBLE or UNCERTAIN rather than picking one silently.

Structural relationship rules:
1. Generate deterministic string IDs based on position (e.g., KHW-1, KHT-1, OWN-1, KHS-1). Never use random UUIDs.
   Separately, always set Khewat.khewat_number and Khatauni.khatauni_number to the actual number PRINTED in
   the source for that Khewat/Khatauni (e.g. "45", "12") -- this is distinct from the internal KHW-1/KHT-1 ID
   and must reflect the source's own numbering exactly, since it is how the same Khewat/Khatauni spanning
   multiple pages gets recognized as one entity.
1b. A visually blank Column 1 is meaningful. When its ruled table cell continues from a preceding page,
    emit a Khewat container with khewat_number=null and continued_from_previous_page=true, and place that
    page's Khataunis, owners, Khasras and observations inside it. Do NOT copy Column 2 into Column 1:
    for example, under the continuing printed Khewat "198/185", values "219" and "220" in Column 2 are
    Khatauni numbers, never Khewat numbers. Preserve the complete slash-pair "198/185"; do not discard the
    previous-Jamabandi component. Set continued_from_previous_page only when the table geometry supports
    continuation; if there is no visible or preceding context, mark the reading uncertain instead.
2. Preserve every identifier as text. Never convert identifiers to numbers.
3. Preserve original text in `raw_` fields exactly as seen, without cleaning or fixing typos.
4. If text is illegible, use the visible raw text when possible and mark status as ILLEGIBLE.
5. Khewat, Khatauni, Khasra, and Mutation numbers are never interchangeable, even when the printed digits
   coincidentally match -- keep each in its own field and never substitute one for another.
6. The Khewat is the ownership account: owners and their share fractions belong at the Khewat level by
   default (Owner.khatauni_id left unset). Only set Owner.khatauni_id when a specific Khatauni's own
   Column 3 explicitly lists a DIFFERENT owner/share for that Khatauni than the Khewat's default --
   do not invent a Khatauni-level owner merely because a Khatauni exists, and do not leave a Khatauni's
   ownership as "unknown" just because it has no owner row of its own; it inherits the Khewat's owners.
   Khatauni-level fields (raw_cultivator_name, raw_possession_type) instead capture cultivation/possession,
   which is a separate concept from ownership.
6b. raw_owner_name_parentage must contain ONLY the owner's name and parentage text -- never the share
    fraction, even when Column 3 prints the name and share close together or on the same line. The share
    belongs solely in raw_share_fraction. Stop transcribing raw_owner_name_parentage as soon as the name and
    parentage are complete; do not continue into the next number/fraction printed after it.

Column 8 / remarks and mutations:
7. Extract Column 8 remarks and link them precisely to their target (Khewat, Khatauni, Owner, or Khasra),
   and classify each remark's remark_category as Approved_Mutation, Pending_Mutation, Legal_Encumbrance,
   Rent_Details, or Informational.
8. In addition to a general Remark, if Column 8 records a mutation (Inteqal), also emit a structured
   Mutation entry. Set status precisely from what the wording actually supports:
     - Approved: the text itself states sanction/approval (e.g. "manzoor", "sanctioned").
     - Pending: only entered/presented/under process, not yet sanctioned.
     - Rejected: the text states the mutation was rejected/refused.
     - Uncertain: a mutation number or reference exists but the status wording is unclear.
   A mutation NUMBER being present is not by itself evidence of Approved -- do not default to Approved.
   Only set mutation_type or transfer_scope when the source text makes them explicit; leave them unset
   otherwise. If the mutation is a mortgage (Rehin/bank charge), set mutation_type to Mortgage. If it is a
   release/discharge of an earlier mortgage, set mutation_type to Release_Discharge and set
   discharges_mutation_id to that earlier mortgage's mutation_id if you can identify it from the text.
9. An approved mutation may update active ownership; a pending, rejected, or uncertain mutation must never
   alter ownership interpretation elsewhere in the document — record it only as a pending/uncertain
   encumbrance. Do not claim a mortgage is currently active merely because mortgage wording appears
   somewhere in the document -- check whether a later release/discharge entry exists for that same
   mortgage before treating it as active.

Layout, Murabba, and area scope:
10. Set `layout` to modern_8_column, legacy_12_column, or unknown_layout based on what the page actually
    shows. Modern computerised Fards use 8 columns (1 Khewat, 2 Khatauni, 3 owners+shares, 4 cultivator,
    5 irrigation, 6 Murabba+Khasra, 7 area+classification, 8 Vishesh Kathan/remarks). Older Fards may use
    roughly 12 differently-arranged columns. Never force a visually incompatible legacy layout into the
    modern column semantics -- use unknown_layout if unsure.
11. Column 6 usually prints Murabba and Khasra together (e.g. "31 // 18" = Murabba 31, Khasra 18). Put them
    in SEPARATE fields: Khasra.murabba_number and Khasra.khasra_number. Never merge them into one string.
12. Column 7 mixes parcel areas, Khatauni subtotals, Khewat totals and document totals. Record each
    Khasra's own area on that Khasra, and each Khatauni's printed total in recorded_total_area. Where you
    emit an AreaObservation, always set its `scope` correctly -- these figures overlap and must never be
    added together. A total printed twice is the same land restated, not extra land.

Persons, purchasers, and cultivation:
13. Owners with fractional shares belong in Column 3 as Owner entries. A person recorded as a PURCHASER of
    NAMED Khasra numbers (mushtari) is different: emit a ParcelInterest listing those specific khasra_ids,
    not an Owner with a whole-Khewat fraction. Being called a purchaser establishes the role only -- the
    scope of the purchase comes from the named Khasras and the mutation, never from the word alone.
14. Column 4 records cultivation/possession, which is NOT ownership. Emit CultivationInterest entries for
    it, with `relationship` set to khud_kasht (self-cultivation by the owner), muzara (tenant),
    gair_mumkin, maqbuza_malkan, or unknown. Never infer that an owner is the cultivator or that a
    cultivator is an owner.

Mutation detail:
15. When the record states them, populate Mutation.mutation_date, transferor_name/transferor_owner_id,
    transferee_name, share_transferred, and area_transferred. Set sanction_wording to the exact phrase you
    read the status from. Set sequence_index when several mutations must be applied in a known order.
    Leave any of these unset rather than inferring them.

Page completeness:
16. If a page states its own position like "Page 5 of 8", set that page's SourceReference.page_number to 5
    and total_pages to 8. Leave total_pages unset when the source doesn't state a total. Also set
    SourceReference.column_ref (e.g. "3", "8") for each extracted fact where the column is identifiable.

17. Return only data supported by the source. Never guess a missing or illegible value; mark status as
    illegible or uncertain instead.
"""


class ExtractionProvider(Protocol):
    """Provider-neutral structured page extraction boundary."""

    def extract_structured(self, *, system_prompt: str, user_prompt: str, document_parts: list[dict[str, Any]], json_schema: type[BaseModel]) -> dict[str, Any] | str:
        ...


# Backward-compatible public name used by existing integrations.
StructuredLLMClient = ExtractionProvider


class DocumentStatus(str, Enum):
    COMPLETE = "COMPLETE"
    COMPLETE_WITH_WARNINGS = "COMPLETE_WITH_WARNINGS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ExtractionResult:
    document: DigitalPatwariDocument | None
    validation_report: ValidationReport | None
    raw_llm_output: dict[str, Any] | str | None
    parser_errors: list[str]
    # Non-fatal issues that don't prevent a document from being produced:
    # a page that failed extraction while other pages still succeeded, or a
    # document_header disagreement noticed while merging pages together.
    page_warnings: list[str] = field(default_factory=list)
    status: DocumentStatus | None = None
    observations: tuple[PageObservation, ...] = ()
    successful_pages: tuple[int, ...] = ()
    failed_pages: tuple[int, ...] = ()
    verification_issues: tuple[VerificationIssue, ...] = ()

    def __post_init__(self) -> None:
        # Older callers constructed ExtractionResult directly before status
        # existed. Infer a concrete status for those objects while all parser
        # paths continue to set it explicitly.
        if self.status is None:
            inferred = (
                DocumentStatus.COMPLETE
                if self.document is not None and not self.parser_errors
                else DocumentStatus.FAILED
            )
            object.__setattr__(self, "status", inferred)

    @property
    def succeeded(self) -> bool:
        return self.status != DocumentStatus.FAILED and self.document is not None


class FardExtractionParser:
    def __init__(
        self,
        llm_client: StructuredLLMClient | None = None,
        *,
        provider: ExtractionProvider | None = None,
        cache: PageObservationCache | None = None,
        max_page_retries: int = 2,
        marla_per_kanal: int = 20,
        sarsahi_per_marla: int = 9,
        area_tolerance_marla: int = 0,
        batch_size: int = 3,
    ) -> None:
        if provider is not None and llm_client is not None:
            raise ValueError("pass provider or llm_client, not both")
        self.provider = provider or llm_client
        if self.provider is None:
            raise ValueError("an extraction provider is required")
        # Compatibility attribute for callers that introspect the old name.
        self.llm_client = self.provider
        self.cache = cache
        self.max_page_retries = max_page_retries
        self.marla_per_kanal = marla_per_kanal
        self.sarsahi_per_marla = sarsahi_per_marla
        self.area_tolerance_marla = area_tolerance_marla
        self.batch_size = batch_size

    def extract(self, document_paths: list[str | Path]) -> ExtractionResult:
        return asyncio.run(self._extract_async(document_paths))

    async def _extract_async(self, document_paths: list[str | Path]) -> ExtractionResult:
        document_parts = load_document_parts(document_paths)
        user_prompt = "Extract the attached Fard/Jamabandi page conforming to the exact schema."

        numbered_parts = [
            (part.get("page_number", i), part)
            for i, part in enumerate(document_parts, start=1)
        ]
        page_results: dict[int, PageObservation] = {}
        page_warnings: list[str] = []

        numbered_parts.sort(key=lambda item: item[0])
        for batch_start in range(0, len(numbered_parts), self.batch_size):
            batch = numbered_parts[batch_start:batch_start + self.batch_size]
            outcomes = await asyncio.gather(
                *(self._extract_one_page(page_number, part, user_prompt) for page_number, part in batch)
            )
            for page_number, observation, error, from_cache in outcomes:
                if observation is not None:
                    page_results[page_number] = observation
                    if from_cache:
                        page_warnings.append(f"page {page_number}: reused cached observation")
                else:
                    page_warnings.append(f"page {page_number}: {error}")

        if not page_results:
            errors = page_warnings or ["transport_error: no pages extracted"]
            return ExtractionResult(
                None, None, None, errors,
                status=DocumentStatus.FAILED,
                failed_pages=tuple(page for page, _ in numbered_parts),
            )

        observations = [page_results[page_number] for page_number in sorted(page_results)]
        assembly = assemble_page_observations(observations)
        page_warnings.extend(assembly.warnings)
        page_warnings.extend(assembly.errors)
        failed_pages = tuple(sorted(set(page for page, _ in numbered_parts) - set(assembly.successful_pages)))
        if assembly.document is None:
            return ExtractionResult(
                None, None, None, page_warnings, status=DocumentStatus.FAILED,
                observations=tuple(observations), failed_pages=failed_pages,
            )

        report = run_axiom_gates(
            assembly.document,
            marla_per_kanal=self.marla_per_kanal,
            sarsahi_per_marla=self.sarsahi_per_marla,
            area_tolerance_marla=self.area_tolerance_marla,
        )
        if failed_pages or not assembly.has_trustworthy_header or assembly.unresolved_critical_issues:
            status = DocumentStatus.PARTIAL
        elif assembly.warnings or assembly.errors or not report.passed:
            status = DocumentStatus.COMPLETE_WITH_WARNINGS
        else:
            status = DocumentStatus.COMPLETE
        return ExtractionResult(
            assembly.document, report, None, [], page_warnings,
            status=status,
            observations=tuple(observations),
            successful_pages=assembly.successful_pages,
            failed_pages=failed_pages,
            verification_issues=assembly.verification_issues,
        )

    async def _extract_one_page(
        self, page_number: int, part: dict[str, Any], user_prompt: str
    ) -> tuple[int, PageObservation | None, str | None, bool]:
        identity = str(
            getattr(self.provider, "cache_identity", None)
            or getattr(self.provider, "model_name", None)
            or f"{type(self.provider).__module__}.{type(self.provider).__qualname__}"
        )
        schema_json = json.dumps(PageObservation.model_json_schema(), sort_keys=True, separators=(",", ":"))
        schema_fingerprint = hashlib.sha256(schema_json.encode("utf-8")).hexdigest()
        cache_key = page_cache_key(
            part,
            identity,
            extraction_prompt=f"{EXTRACTION_SYSTEM_PROMPT}\0{user_prompt}",
            observation_schema=f"3_STRUCTURAL_VERIFICATION:{schema_fingerprint}",
        )
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return page_number, cached, None, True

        raw_output: dict[str, Any] | str | None = None
        for attempt in range(self.max_page_retries + 1):
            try:
                raw_output = await asyncio.to_thread(
                    self.provider.extract_structured,
                    system_prompt=EXTRACTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    document_parts=[part],
                    json_schema=PageObservation,
                )
                break
            except Exception as exc:
                if attempt >= self.max_page_retries:
                    return page_number, None, f"transport_error: {exc}", False
                await asyncio.sleep(0)

        try:
            decoded = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
            try:
                observation = PageObservation.model_validate(decoded)
            except pydantic.ValidationError:
                # Compatibility for existing providers/tests returning a
                # canonical page directly. New providers receive the
                # PageObservation schema and should return the envelope.
                DigitalPatwariDocument.model_validate(decoded)
                observation = PageObservation(
                    page_number=page_number,
                    canonical_payload=decoded,
                )
            if observation.page_number != page_number:
                return (
                    page_number,
                    None,
                    f"page_number mismatch: provider returned {observation.page_number}",
                    False,
                )
        except pydantic.ValidationError as exc:
            field_errors = "; ".join(
                f"{'.'.join(str(loc_part) for loc_part in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            )
            return page_number, None, field_errors, False
        except Exception as exc:
            return page_number, None, f"parse_error: {exc}", False

        if self.cache is not None:
            self.cache.put(cache_key, observation)
        return page_number, observation, None, False
