# Digital Patwari — Repository Instructions

## Purpose

Digital Patwari extracts structured ground-truth data from Punjab Fard and Jamabandi PDFs or page images. The records are hierarchical, multilingual, frequently span page boundaries, and contain vertically merged cells.

The current implementation is in `patwari_agent.py`. It uses:

- Python
- Pydantic v2
- `google-genai`
- Gemini Developer API
- Exact fractions through `fractions.Fraction`

Read this file and the complete relevant source before changing code.

## Current code map

`patwari_agent.py` currently contains five sections:

1. Enums and normalization utilities
2. Pydantic schema models
3. AG-01, AG-02, and AG-03 validation
4. Document loader, parser, and Google GenAI adapter
5. A directly executable test block

Important existing types include:

- `ExtractionConfidence`
- `ExtractionStatus`
- `RemarkTarget`
- `SourceReference`
- `AreaKanalMarlaSarsahi`
- `Remark`
- `DocumentHeader`
- `Owner`
- `Khasra`
- `Khatauni`
- `Khewat`
- `DigitalPatwariDocument`
- `ValidationIssue`
- `GateResult`
- `ValidationReport`
- `ExtractionResult`
- `FardExtractionParser`
- `MyLLMAdapter`

Preserve public model and field names unless a schema migration is explicitly approved.

## Canonical hierarchy

The source is not a flat table. Preserve this structure:

```text
DigitalPatwariDocument
├── DocumentHeader
├── Khewat[]
│   ├── Owner[]
│   └── Khatauni[]
│       └── Khasra[]
└── Remark[]




Relationship rules:

One document contains zero or more Khewats.

One Khewat can contain multiple Owners.

One Khewat can contain multiple Khataunis.

Each Owner belongs to exactly one Khewat.

Each Khatauni belongs to exactly one Khewat.

Each Khasra belongs to exactly one Khatauni.

Do not assign a Khasra directly to an Owner unless the source explicitly establishes that relation and the schema is intentionally extended.

Remarks can target a Khewat, Khatauni, Owner, or Khasra through Remark.target_type and Remark.target_id.

Remarks must include a remark_category enum (e.g., Pending_Mutation, Legal_Encumbrance, Rent_Details, Informational) to explicitly classify their legal impact.

Never duplicate a vertically merged Khewat or Khatauni merely because it continues across visual rows or pages.

Schema fidelity
Preserve source evidence and normalized values separately:

Owner source text: raw_owner_name_parentage

Owner normalized name: normalized_owner_name

Owner source share: raw_share_fraction

Owner canonical share: share_fraction

Soil/Irrigation source text: raw_soil_classification

Irrigation normalized value: normalized_irrigation_source (e.g., Chahi, Nehri, Barani)

Cultivation normalized value: normalized_cultivation_status (e.g., Khudkasht, Muzara, Gair Mumkin)

Source evidence: SourceReference

Never silently clean or overwrite raw_ values. Treat identifiers as strings, even if they look numeric.

Use these extraction statuses distinctly:

present

not_present

illegible

uncertain

Do not substitute an empty string, zero, or guessed value for missing or illegible content.

Patwari Cognitive Workflow
When analyzing any document, the agent must execute reasoning and parsing strictly in this order:

Record Metadata -> Owner Identification -> Mutation/Remarks Analysis -> Share Verification -> Total Area Assessment -> Calculation & Linking


amabandi Year: Always identify the Jamabandi year first to establish the precise legal snapshot of ownership.

Record Identity: Identify the village, Hadbast number, Tehsil, and District before parsing ownership lines.

Owner Identification: Locate the owner and parentage details in Column 3 (Ownership/Malikan).

Column 8 Override Check: Inspect Column 8 (Remarks/Khana Kaifiyat/Mutations) before finalizing ownership interpretation or calculating individual areas.

Approved Mutation Rule: If an approved/sanctioned mutation (Inteqal) exists in Column 8, update the active legal ownership structure accordingly.

Pending Mutation Rule: If a mutation is only entered/presented/pending in Column 8, do NOT alter the primary ownership hierarchy; record it as a pending encumbrance.

Proportional Area Calculation: Calculate individual co-owner area by multiplying the total Khewat area by the specific co-owner's exact ownership share fraction (share_fraction).

Khasra Spatial Context: Treat Khasra numbers as spatial descriptions of where possession/cultivation lies. For macro ownership verification, establish the total Khewat area first.

Zero-Guesswork Guardrail: Never guess or hallucinate missing data. If ownership, share, or area is ambiguous, mark status as uncertain and flag for human verification.

Source Traceability: Every extracted entity and calculated field must map back to a verified line and page entry in the source document (SourceReference).

Khewat vs. Khatauni: what each one governs
Khewat is the ownership account. "Who owns?" is answered from the Khewat's owner
records by default. Khatauni is the cultivation/possession account — it groups
Khasras and records who cultivates/possesses, not who owns.

An Owner's `khatauni_id` (see `digital_patwari/models.py`) is optional and encodes
this precisely:
- unset (None): the owner's share is a Khewat-level default. It governs every
  Khatauni under that Khewat that has no owner row of its own (inheritance/fallback
  — a Khatauni with no owner is NOT "unknown ownership," it inherits the Khewat's
  default).
- set: an explicit Khatauni-level override for that one Khatauni only. It does not
  apply to the Khewat's other Khataunis, and does not get overridden by unrelated
  Khewat-level defaults.

`digital_patwari/ownership.py` resolves this deterministically (`khatauni_governance`,
`resolve_owner_entitlements`) — every Khatauni is governed by exactly one owner
group, never zero (omission) and never two (double-counting). Do not implement
"every Owner must belong to a Khatauni" as a shortcut; that was tried and reverted
after a real Fard (Khewat 219 of a real Sanghol Jamabandi) showed Khataunis with
completely disjoint owner cohorts under one Khewat, and Khataunis with no owner row
at all that still had valid, inherited ownership.

An owner can hold land in more than one Khewat. `FardQueryEngine.owner_land()`
resolves one Khewat's entitlement and deliberately abstains when a name spans
multiple Khewats (protects against merging two different people who share a name).
`FardQueryEngine.owner_total_across_khewats()` is the explicit opt-in for "trace
this owner through the whole Fard and sum every Khewat" — it still refuses to merge
rows whose exact name+parentage text differs.

Axiom gates
Every successfully parsed document must run run_axiom_gates.

AG-01 — Khewat share summation
The exact sum of Owner.share_fraction values in a Khewat must equal Khewat.total_share.

Continue using Fraction, not float.

A Khewat with no extracted owners is unevaluable and should produce a warning.

Do not invent missing shares to force the total to pass.

AG-02 — Khasra/Khatauni linkage
Every Khasra must reference an existing Khatauni, and its khatauni_id must equal the ID of the Khatauni containing it.

Also validate:

Owner khewat_id against its containing Khewat.

Khatauni khewat_id against its containing Khewat.

Uniqueness of Khewat, Khatauni, Owner, and Khasra IDs.

Every Remark.target_id against an entity of its declared target type.

AG-03 — Area consistency
The sum of Khasra areas in a Khatauni must equal its recorded_total_area.

Default conversion hierarchy: 1 Kanal = 20 Marla, 1 Marla = 9 Sarsahi.

Validate exact area consistency down to the Sarsahi level using exact fractions before applying any tolerance_marla.

Keep marla_per_kanal and sarsahi_per_marla configurable.

Compare integer totals based on the lowest unit of measurement present.

Keep tolerance_marla explicit.

If the source total or Khasras are absent, report the gate as skipped rather than passed by assumption.

AG-04 — Document completeness
If any page's SourceReference states its own total_pages (parsed from printed
pagination like "Page 5 of 8"), the number of distinct page_numbers actually present
across the whole document must reach that total. If fewer pages are present than
stated, flag INCOMPLETE DOCUMENT with the specific missing page numbers rather than
silently analyzing a partial Fard. Skipped (not failed) when no page states a total.

Decimal Kanal/Marla conversion
Some sources print area as decimal Kanal (e.g. "10.55 Kanal") or leave a decimal
Marla remainder. The decimal fraction is NOT literal Marla/Sarsahi digits pasted
together — 10.55 Kanal is 10 Kanal + (0.55 × 20) Marla = 10 Kanal 11 Marla, not
"10 Kanal 55 Marla". Use `digital_patwari/normalization.py`'s
`decimal_kanal_to_kanal_marla` / `decimal_marla_to_marla_sarsahi` /
`decimal_kanal_to_sarsahi` — exact Fraction arithmetic, never float rounding.

Mutation status and mortgage/rehin status
A mutation NUMBER being present in Column 8 is not evidence of approval by itself.
`Mutation.status` is one of Approved / Pending / Rejected / Uncertain — only set
Approved when the text itself says sanctioned/manzoor. A mortgage mention is not
evidence the loan is currently active — `digital_patwari/encumbrance.py`'s
`resolve_mortgage_status` checks for a matching `Release_Discharge` mutation
(`Mutation.discharges_mutation_id`) before calling a mortgage discharged vs. still
likely active; it never assumes either without checking.

Any-Fard input requirement
The production program must work with any caller-supplied Fard. Never hardcode:

fard_1.png

A fixed page count

Sequential file names

A village or district

A Khewat/Khatauni count

A particular table layout

Accept a PDF, an ordered list of image paths, a directory, or a manifest through a proper CLI or public function. Validate supported MIME types and fail clearly on empty input.

Create a stable document ID and ordered page manifest. Preserve original file names and page numbers in the audit trail.

Multi-page architecture
Do not send an unbounded number of high-resolution pages in one synchronous request.

Use this target workflow:

Discover and deterministically order the source pages.

Preserve originals; preprocess only into derived temporary files.

Extract pages asynchronously in small configurable batches (e.g., using asyncio.gather()) to eliminate I/O bottlenecks.

Store page-level observations with source references.

Track open Khewat/Khatauni continuation state across page boundaries.

Merge entities deterministically.

Deduplicate only when source evidence supports identity.

Validate the complete Pydantic document.

Run all axiom gates.

Save structured JSON and a separate validation report.

Use a single-page smoke test for development, but do not turn its file name into a production default.

Google GenAI rules
The intended free-development backend is the Gemini Developer API:

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


Do not pass enterprise=True unless the user intentionally chooses Google Cloud Agent Platform/Vertex AI and has enabled billing.

The current model setting is gemini-3.5-flash. Keep it configurable and verify current availability in official Google documentation before changing it.

Use structured JSON output with:

response_mime_type="application/json"

response_schema=DigitalPatwariDocument

deterministic or near-deterministic temperature

Every request must have:

An explicit timeout

Bounded retries

Retry only for transient failures

No retry loop for permanent 4xx errors

Clear progress output for long-running work

Secret handling
This repository has previously contained an API key in the executable block. Remove that pattern; never restore it.

Never hardcode an API key.

Never ask the user to paste a key into Python source.

Read only GEMINI_API_KEY from the environment.

Fail immediately with a clear message when the variable is missing.

Never print keys or complete environment mappings.

Never expose a key in terminal inspection, screenshots, tracebacks, fixtures, logs, JSON output, or commits.

Never commit .env.

If a key is exposed, instruct the user to revoke it before further use.

Do not access or reproduce a secret merely because it is present in an older version of the file.

Known defects in the current script
Future agents must account for these real issues:

The executable block still handles the API key incorrectly and must use os.environ["GEMINI_API_KEY"].

The test input is hardcoded to fard_1.png.

generate_content is indented inside the document-parts loop. With multiple pages, it sends repeated cumulative requests instead of one deliberate request or a controlled page-batch workflow.

The adapter has no explicit request timeout.

The parser catches all exceptions as plain strings, losing structured error classification. Validation reports must capture and expose the exact pydantic.ValidationError field path (loc) so the user knows exactly which specific Khasra or Owner caused the extraction to fail.

load_document_parts accepts unsupported files and duplicates every page in memory as base64.

Most Pydantic models use extra="ignore", which can silently discard unexpected LLM fields. Prefer extra="forbid" for the final structured contract unless compatibility requirements justify otherwise.

The document model does not currently enforce global ID uniqueness, parent/child foreign keys, or Remark target resolution.

Output is printed to stdout but not saved atomically to a user-selected destination.

The single file combines models, validation, transport, orchestration, and CLI execution, which makes testing and maintenance difficult.

Do not attempt to hide these defects with prompt changes alone.

Preferred module direction
When refactoring is authorized, move toward:


digital_patwari/
├── models.py
├── normalization.py
├── validation.py
├── document_io.py
├── extraction.py
├── merge.py
├── providers/
│   └── gemini.py
└── cli.py
tests/
├── test_fractions.py
├── test_models.py
├── test_axiom_gates.py
├── test_linkage.py
├── test_page_merge.py
└── fixtures/

Keep refactors incremental. Preserve a working entry point while modules are extracted.

Python standards
Use Pydantic v2 APIs.

Use type hints on public functions.

Keep transport, parsing, normalization, merge, and validation separate.

Use exact arithmetic for legal shares and land area.

Prefer small testable functions.

Do not use random UUIDs for extracted source entities.

Generate deterministic IDs from document identity, hierarchy, source page, and stable position or source identifiers.

Avoid destructive automatic JSON repair.

Retain raw model output for audit only when it contains no secrets and is stored securely.

Save outputs atomically so a failed run does not overwrite a valid result.

Change procedure
Before editing:

Read the relevant code and its callers.

Check for unsaved or unrelated user changes.

Ensure inspection commands cannot print secrets.

State any schema migration explicitly.

After editing:

Run syntax validation:

python3 -m py_compile patwari_agent.py

Run unit tests.

Run a one-page smoke test using a caller-supplied file.

Verify valid structured JSON.

Verify source references and raw values.

Run all axiom gates.

Test a multi-page Fard where a Khewat or Khatauni crosses a page boundary.

Test malformed, missing, illegible, and uncertain values.

Confirm no API key or private record has entered version control.

Definition of done
Work is complete only when:

Syntax and tests pass.

No secret exists in source code or output.

The same entry point accepts arbitrary valid Fard inputs.

Output conforms to the strict Pydantic contract.

IDs and foreign keys are valid and deterministic.

Raw source evidence is retained.

AG-01, AG-02, and AG-03 return structured results.

One-page and multi-page test cases work.

Page-boundary continuation is handled explicitly.

Failures return actionable diagnostics rather than hanging indefinitely.

AG-01, AG-02, AG-03, and AG-04 return structured results (updated from the AG-01/02/03
line above once AG-04's document-completeness gate was added).

Reading order for the extraction model
Transcribe the original Gurmukhi/Urdu/Persian text first, classify its structure
second, form an English interpretation third. Never translate first and reason from
the translation alone — see `EXTRACTION_SYSTEM_PROMPT` in `digital_patwari/extraction.py`,
which encodes this as the model's first instruction. For uncertain words, the model
must state the possible readings and mark that field ILLEGIBLE/UNCERTAIN, not guess.

Provider-neutral extraction architecture
Digital Patwari's deterministic logic (schemas, validators, reconciliation, ownership
resolution, query layer) must never become conceptually dependent on a specific
extraction provider. `digital_patwari/extraction.py` defines `StructuredLLMClient` as
a `Protocol` — any provider adapter that returns the same `DigitalPatwariDocument`
JSON shape can be substituted (`digital_patwari/providers/gemini.py` is the current
concrete implementation; a Claude or other provider adapter can be added alongside it
without touching validation, reconciliation, ownership, or query code at all).

Three ownership states, plus possession as a fourth
These must never be collapsed into a single number:

1. BASE JAMABANDI OWNERSHIP — what the ownership column explicitly records.
   A historical fact; NEVER overwritten, no matter what later mutations say.
2. POST-JAMABANDI MUTATION EFFECTS — the Column-8 mutation ledger, each entry
   preserved with its own status and evidence.
3. DERIVED / EFFECTIVE POSITION — base ± the effects of mutations that are
   actually operative. Always labelled derived, never presented as what the
   record itself says.
4. POSSESSION / GIRDAWARI — a separate dimension entirely. A mutation moving
   ownership does not prove possession moved.

Implemented in `digital_patwari/derived_ownership.py` (states 1–3, exact
Fraction arithmetic, chronological application, never negative) and
`digital_patwari/interests.py` (state 4, `CultivationInterest`). Surfaced by
`FardQueryEngine.owner_current_position()`, whose `Answer` carries
`record_says` / `mutation_effect` / `derived_position` / `possession_position`
as separate fields precisely so a UI cannot merge them.

Only `MutationStatus.APPROVED` is operative — see
`models.is_operative_for_derived_ownership`, the single edit site for that
rule. Referenced, entered, presented-for-verification (paratal),
presented-for-sanction, pending, rejected, cancelled and uncertain mutations
are all recorded and explained but never move a share.

Person–land relationships are not one-dimensional
Four different relationships, each calculated differently, never summed as if
each were separate land:

- Khewat-scoped ownership → `ownership.py` (fraction × correct scope area)
- Cultivation / possession → `interests.py` (`CultivationInterest`)
- Specific-Khasra interest → `interests.py` (`ParcelInterest`)
- Mutation-derived ownership → `derived_ownership.py`

A purchaser (mushtari) of NAMED Khasras holds those parcels' own areas. Their
interest must never be multiplied against the whole Khewat. Being called a
purchaser establishes a role only; scope comes from the named Khasras, the
linked mutation and the surrounding record.

Area figures are scoped, not addable
Column 7 mixes parcel areas, Khatauni subtotals, Khewat totals and document
totals. These overlap — a Khewat total already contains its Khataunis'
subtotals, which already contain their Khasras. `AreaScope` on
`AreaObservation` records which is which, and AG-06 flags a repeated identical
total inside one scope. A total printed twice is the same land restated, not
additional land. The core invariant: THE SAME PHYSICAL LAND MUST NOT
CONTRIBUTE TWICE TO THE SAME CALCULATION.

Never infer area from a share's denominator
Some Fards print shares whose denominator equals the scope's total Marla count
(a 46K-14M = 934 Marla Khewat carrying 404/934), which tempts a reader into
treating the numerator as "Marlas owned". That is a coincidence, not a rule,
and breaks on ordinary fractions (1/4, 1/7, 209/944).
`normalization.share_denominator_matches_total_marla` exists ONLY to detect and
flag the coincidence; every calculation goes through
`normalization.area_from_share` (actual total area × actual recorded fraction).

Murabba is not Khasra
Column 6 prints them together ("31 // 18"). They are stored in separate fields
(`Khasra.murabba_number`, `Khasra.khasra_number`) and never merged into one
ambiguous identifier. No assumption is encoded about a Murabba's size or parcel
count.

Not every Fard has eight columns
Modern computerised Fards commonly use 8 columns; legacy records may use
roughly 12, differently arranged. `DocumentLayout` records which, defaulting to
`UNKNOWN_LAYOUT`. Never force a visually incompatible legacy Fard through
modern 8-column semantics.

Domain rules sourced from external material (e.g. instructional videos)
Automatic captions and transcripts can contain real numeric/word errors. Any domain
rule sourced from such material must be extracted as a CONCEPTUAL rule or heuristic,
compared against the existing domain model in this file, validated against a real or
constructed example, and explicitly approved before being implemented — never
implemented from an unverified transcript number directly. Concepts from such sources
are usable; specific numeric examples from them are not authoritative on their own.

Open items of this kind are tracked in `NEEDS_AUTHORITY_VALIDATION.md`, and the same
classification vocabulary is implemented in code as `TermValidation` in
`digital_patwari/terminology.py` so a term's validation level travels into answers
rather than living only in prose. Digital Patwari reports what a record says and what
follows arithmetically; it does not assert legal validity, prescribe remedies, or name
forums.
## Superpowers Skills
Before writing code, planning, or debugging, consult and strictly follow the workflows in:
`./superpowers/skills/`