# Digital Patwari — Audit

Scope note: the working project was scattered across two directories. The actual
code (`patwari_agent.py`, `generate_schema.py`, 11 sample `fard_*.png` pages) lived in
`~/Desktop/Digital_/`, while the authoritative spec (`CLAUDE.md`) lived in
`~/Desktop/DigitalPatwari/`. There is no separate domain `.md` file — `CLAUDE.md` in
this directory **is** the domain specification (hierarchy, axiom gates, cognitive
workflow, known defects, module direction). I copied the code and samples into this
directory (originals untouched) so one directory now governs and contains the project.

## 1. What currently exists

- `patwari_agent.py` (442 lines, monolithic): Pydantic v2 schema, three axiom gates
  (AG-01/02/03), a Gemini Developer API adapter (`MyLLMAdapter`), a parser
  (`FardExtractionParser`), and a `__main__` smoke test.
- `generate_schema.py`: generates an `.xlsx` describing the schema/axioms for
  human reference. Documentation tool only, not used at runtime.
- `samples/fard_1.png` … `fard_11.png`: real scanned Fard pages, no ground truth
  attached.
- No tests, no CLI, no multi-page merge, no UI, no persisted output layer.

## 2. What CLAUDE.md requires vs. what's implemented

| Requirement (CLAUDE.md) | Status | Notes |
|---|---|---|
| Canonical hierarchy (Doc→Khewat→{Owner,Khatauni→Khasra}, Remarks) | **Implemented** | Matches `DigitalPatwariDocument` exactly. |
| `raw_`/normalized field separation for owner name & share | **Implemented** | `raw_owner_name_parentage`/`normalized_owner_name`, `raw_share_fraction`/`share_fraction`. |
| `raw_soil_classification` / `normalized_soil_classification` | **Implemented** | On `Khasra`. |
| `normalized_irrigation_source`, `normalized_cultivation_status` | **Missing** | No fields exist on any model. |
| `Remark.remark_category` enum (Pending_Mutation, Legal_Encumbrance, Rent_Details, Informational) | **Missing** | `Remark` has no category field — nothing forces the pending-vs-approved mutation distinction into structured data. |
| `AreaKanalMarlaSarsahi` type, sarsahi-level exactness | **Missing** | Code has `AreaKanalMarla` (kanal+marla only), no sarsahi unit at all. AG-03 compares in marla, not the lowest unit present, contradicting the spec directly. |
| `ExtractionStatus`, `ExtractionConfidence`, `RemarkTarget`, `SourceReference` | **Implemented** | As specified. |
| AG-01 share summation, exact `Fraction` | **Implemented** | Correct, uses `Fraction`, warns on zero owners. |
| AG-02 — Khasra↔Khatauni + Owner.khewat_id + Khatauni.khewat_id + global ID uniqueness + Remark.target_id resolution | **Partially implemented** | Only Khasra→Khatauni linkage is checked. Owner/Khatauni `khewat_id` cross-checks, ID uniqueness, and Remark target resolution are **not implemented** — this is explicitly required and currently silently unenforced. |
| AG-03 exact-to-sarsahi, configurable `sarsahi_per_marla`/`marla_per_kanal`, skip vs. pass on missing data | **Partially implemented** | Marla-level only (no sarsahi). Skip-on-missing behavior is correct. |
| Approved vs. Pending Mutation Rule (Column 8 override logic) | **Missing** | No code encodes this reasoning; it exists only as a prompt instruction line buried in `EXTRACTION_SYSTEM_PROMPT`, unchecked and unstructured. This is graded as a high accuracy risk (see §4). |
| Zero-Guesswork Guardrail (never invent missing values) | **Partially implemented** | Schema uses `ExtractionStatus` correctly, but nothing *enforces* that the LLM actually used `illegible`/`uncertain` instead of guessing — it's prompt-only, unverified. |
| Any-Fard input (PDF / image list / directory / manifest, no hardcoded names) | **Missing** | `__main__` hardcodes `["fard_1.png"]`. `load_document_parts` accepts any file, no MIME validation, no directory/PDF support, no manifest, no document ID. |
| Multi-page batching (`asyncio.gather`), page-level continuation state, deterministic merge | **Missing entirely** | No async, no batching, no cross-page Khewat/Khatauni continuation tracking, no merge step. |
| Deterministic IDs from doc identity/hierarchy/page/position | **Not implemented** | Prompt says "use KHW-1 style IDs," but nothing programmatically generates or verifies them — entirely dependent on LLM compliance. |
| Gemini Developer API usage (`api_key=os.environ[...]`, no `enterprise=True`) | **Implemented, with a dangerous stale comment** | Code is correct (`os.environ.get("GEMINI_API_KEY")`), but line 392 has a leftover comment `# Enabled enterprise=True to support the new AQ. project-bound API keys` that doesn't match the code and could mislead a future editor into actually adding `enterprise=True`. |
| Explicit timeout, bounded retries, retry-only-on-transient | **Missing** | `generate_content` call has no timeout, no retry logic at all. |
| `extra="forbid"` on the final structured contract | **Missing** | All models use `extra="ignore"`, silently dropping unexpected LLM fields — exactly the defect CLAUDE.md calls out. |
| Structured `pydantic.ValidationError.errors()` / `loc` surfaced on failure | **Missing** | `FardExtractionParser.extract` catches bare `Exception` and stores `str(exc)` — loses the field path entirely, exactly the defect CLAUDE.md calls out. |
| `generate_content` called once per batch, not per page in a loop | **Bug confirmed** | Lines 396–415: the `client.models.generate_content(...)` call is indented **inside** the `for part in document_parts:` loop. With N pages this fires N cumulative requests instead of one. Confirmed present, not yet fixed. |
| Atomic output save to user-selected destination | **Missing** | `__main__` only prints to stdout. |
| No secrets in code/output | **Implemented** | No hardcoded key found; env-var-only. Stale comment `# PASTE YOUR ACTUAL API KEY HERE:` above the `os.environ[...]` line should still be removed — it's misleading even though the code itself never accepts a pasted key. |
| Module split (`models.py`, `validation.py`, `providers/gemini.py`, `cli.py`, …) | **Not started** | Everything is one 442-line file. |
| Test suite (fractions, models, axiom gates, linkage, page merge) | **Missing entirely** | Zero tests exist anywhere in the project. |

## 3. Architectural problems

1. **No separation of transport/parsing/validation/orchestration** — a single class change risks breaking unrelated behavior; impossible to unit test the Gemini call without mocking the whole file.
2. **The parser is a black box on failure.** Any exception — network, timeout, malformed JSON, Pydantic validation — collapses to a string. A user asking "why did this fail" gets nothing actionable.
3. **No document identity.** There's no concept of a document/run ID, so nothing about a given extraction (source pages, timestamps, retries) is durable or auditable — directly conflicting with the "Source Traceability" workflow requirement.
4. **Single-page assumption baked into the entry point** blocks the entire multi-page architecture the spec requires (page batching, continuation state, deterministic merge) — this isn't a small patch, it's a missing subsystem.
5. **AG-02/AG-03 gaps mean invalid documents can currently pass validation** — orphaned owners with wrong `khewat_id`, duplicate IDs across entities, and unresolved remark targets are all invisible today. This is the most direct accuracy risk in the whole codebase.

## 4. Accuracy risks (ranked)

1. **Pending vs. approved mutation logic isn't structural.** The single most Fard-specific piece of domain reasoning in CLAUDE.md — "an approved mutation updates active ownership; a pending mutation must not" — currently lives only as a sentence inside an LLM prompt, with no schema field to record which case applied and no code path that checks it. This is the highest-value, highest-risk gap for the product's actual purpose (telling a user who owns what right now).
2. **AG-02's missing FK/uniqueness checks** let structurally broken documents (e.g., an Owner pointing at the wrong Khewat) pass validation silently.
3. **`extra="ignore"` everywhere** means a schema mismatch from the LLM is silently discarded rather than surfaced — a silent accuracy failure mode, not just a code-quality issue.
4. **No sarsahi-level area precision** — AG-03 can pass with mismatches under 1 marla that CLAUDE.md explicitly requires be caught at the sarsahi level before any tolerance is applied.
5. **The `generate_content`-in-a-loop bug** doesn't just waste quota — with N pages it makes N separate, increasingly-cumulative requests instead of one deliberate call, which will degrade output quality and cost silently as page count grows.
6. **`gemini-3.5-flash`** is used without any note on where its availability was verified — CLAUDE.md requires checking current official docs before relying on it.

## 5. Recommended implementation order

1. **Correctness bugs first** (this pass): dedent `generate_content`, add timeout + bounded transient-only retry, replace bare-`Exception` catch with structured `pydantic.ValidationError` handling, remove stale/misleading comments, validate MIME types and reject empty input, replace hardcoded `fard_1.png` with a real CLI accepting file/dir/PDF.
2. **Schema completeness** (this pass): add `AreaKanalMarlaSarsahi`, `Remark.remark_category`, `normalized_irrigation_source`, `normalized_cultivation_status`; move the final contract to `extra="forbid"`.
3. **Strengthen AG-02** (this pass) to cover Owner/Khatauni `khewat_id` cross-checks, global ID uniqueness, and Remark target resolution; extend AG-03 to sarsahi precision.
4. **Regression test suite** (this pass): fractions, axiom gates (including the explicit "one Khewat, multiple Khataunis must not double-count area" case), linkage failures, malformed/illegible/uncertain input.
5. **Module split** (next pass): extract `models.py`, `validation.py`, `document_io.py`, `providers/gemini.py`, `cli.py` per CLAUDE.md's preferred layout, keeping `patwari_agent.py` as a thin compatibility entry point.
6. **Multi-page architecture** (next pass): page discovery/ordering, async batched extraction, Khewat/Khatauni continuation tracking across pages, deterministic merge, deterministic ID generation.
7. **Mutation reasoning as structured logic** (next pass): promote the Approved/Pending Mutation Rule from prompt text into a checked code path that gates whether a Remark can alter active ownership.
8. **Atomic output persistence + document/run identity** (next pass).
9. **Reasoning/explanation layer** ("Record says / Calculated / Interpretation / Uncertain") and UX (next pass, after the above is trustworthy).

This pass implements items 1–4 above (correctness, schema completeness, AG-02/03
strengthening, tests) since everything else in the roadmap depends on the extraction
and validation core being correct and honest about failure first.

## 6. Progress: pass 2

Item 5 (module split), item 7 (mutation reasoning as structured logic), and the
reasoning/explanation layer from item 9 are now implemented:

- **Module split**: `digital_patwari/{models,normalization,validation,document_io,
  extraction,reconciliation,query,cli}.py` + `providers/gemini.py`.
  `patwari_agent.py` is now a thin compatibility shim re-exporting the same names.
- **Structured mutations**: `Mutation` model (status Approved/Pending, optional
  mutation_type, optional transfer_scope, affected_khasra_numbers) replaces
  prompt-only mutation handling. AG-02 now also checks Mutation ID uniqueness and
  target resolution.
- **Reconciliation** (`digital_patwari/reconciliation.py`): a fourth pipeline stage
  that applies the Approved/Pending Mutation Rule as checked code — classifying each
  owner's and Khewat's ownership as `as_recorded_active`, `superseded_by_approved_
  mutation`, or `pending_mutation_noted` — without ever computing a new share or
  owner from free-text mutation wording.
- **Query/explanation layer** (`digital_patwari/query.py`): `FardQueryEngine` reads
  only from the reconciled record (never raw LLM output) and answers the product's
  target questions (owners, share, land, Khasra context, mutations, remarks, total
  area, simple-English summary), each as an `Answer` with record_says/calculated/
  interpretation/evidence/confidence/uncertain.
- **Tests**: 27 new tests (67 total, up from 40) covering mutation linkage, all
  reconciliation branches, and every query method including abstention paths.

Still open: item 6 (multi-page async batching, cross-page continuation, deterministic
merge), full item 8 (document/run identity — atomic output save already existed), and
the UX layer. See the chat-turn MVP gap report for the current prioritized list.

## 7. Pass 3 — 35 domain rules audit (video-derived, cross-checked against a real Fard)

A-E audit against the existing codebase before implementing:

**A. Already correct**: canonical hierarchy (Khewat→Owner/Khatauni→Khasra, Remarks
separate), raw_/normalized field separation, `ExtractionStatus`/`ExtractionConfidence`
abstention model, `SourceReference` evidence on every entity, exact-`Fraction` area
arithmetic (`AreaKanalMarlaSarsahi.total_marla/total_sarsahi`), AG-01/02/03, the
Approved/Pending Mutation Rule via reconciliation.py, the `Answer` six-part structure,
provider-neutral extraction (`StructuredLLMClient` Protocol already existed).

**B. Documented but not enforced (fixed this pass)**: "Khewat = ownership account,
Khatauni = cultivation account" was prose-only in CLAUDE.md's Patwari Cognitive
Workflow; now enforced by `digital_patwari/ownership.py`'s inheritance/override
resolver. "Mutation ≠ automatically sanctioned" was prose; `MutationStatus` only had
Approved/Pending, no way to represent Rejected/Uncertain. Mortgage/discharge tracking
didn't exist as a concept at all.

**C. Missing (added this pass)**: decimal-Kanal/decimal-Marla conversion (a real
Fard convention this session hadn't encountered before), document-completeness
checking (page X of Y), multi-Khewat owner-total tracing (an owner's total across
every Khewat they appear in, opt-in and identity-safe).

**D. Conflicts with the prior Khatauni-ownership change**: none found. The Khewat-
default/Khatauni-override resolver built in pass 2 already implements exactly what
this pass's rules 1/2/8 describe — the new rules confirmed the design rather than
requiring rework.

**E. Incorrect schema assumptions found**: none newly found this pass; the one found
in pass 2 (Owner tied to exactly one Khatauni) was already corrected.

**Implemented this pass**: `MutationStatus.REJECTED/UNCERTAIN`, `MutationType.
MORTGAGE/RELEASE_DISCHARGE` + `Mutation.discharges_mutation_id`,
`SourceReference.total_pages` + AG-04 document-completeness gate,
`digital_patwari/normalization.py` decimal-Kanal/Marla converters,
`digital_patwari/encumbrance.py` mortgage-status resolver,
`FardQueryEngine.owner_total_across_khewats()` and `.mortgage_status_for()`,
`EXTRACTION_SYSTEM_PROMPT` updated for transcribe-before-translate order and the
new granularity. 24 new regression tests (105 total).

## 8. Pass 4 — consolidated domain intelligence (Videos 2/3 + Nirmal Patwari lesson)

**A. Already correct**: core ontology; Khewat=ownership / Khatauni=cultivation
scoping; multi-Khatauni double-count AND omission prevention; exact Fraction
arithmetic incl. decimal-Kanal/Marla; AG-04 completeness; abstention model;
provider-neutral `StructuredLLMClient`.

**B. Documentation-only, now operationalised**: undivided-vs-exclusive-parcel
distinction (was an English string, now `InterestScope` + `ParcelInterest`);
ownership-vs-cultivation separation (now `CultivationInterest` + Khud Kasht
recognition).

**C. Missing, now added**: `DocumentLayout`; `Khasra.murabba_number` (the schema
previously had NO Murabba field at all); specific-parcel/purchaser interests;
the three-state base/mutation/derived ownership engine; Girdawari as a distinct
fourth state; `AreaScope` + `AreaObservation` + repeated-total detection;
mutation chronology and transferor/transferee/date/share/area fields;
AG-05 `MUTATION_SHARE_AREA_MISMATCH`; AG-06 area-scope repetition; AG-07
parcel-interest resolution; revenue terminology dictionary with per-term
validation levels; explicit share-denominator-coincidence guard.

**D. Conflicts**: none. Part 6's "do not make khatauni_id mandatory" matches the
existing `str | None` design — the lessons confirmed the pass-2 architecture
rather than requiring rework.

**E. Incorrect schema assumptions found**: the absent Murabba field (Murabba and
Khasra were being conflated into `khasra_number` for records like "31 // 18").

**Two real bugs found by the new tests, fixed in production code:**
1. `terminology.lookup_term("Mushtari")` returned the PLURAL entry, because
   `Mushtari` and `Mushtariyan` share a normalized form and the later entry
   clobbered the earlier one's caution text. Fixed by registering exact
   raw_term spellings first and using setdefault for normalized/variant keys.
2. `owner_current_position` rendered a transferred share as `100/467` instead of
   the printed `200/934` — before/after values were formatted over the printed
   denominator but the delta was not. Fixed by removing pre-baked fraction text
   from `AppliedMutationEffect.description` so the presentation layer formats
   every fraction over the denominator the Fard actually printed.

**Tests**: 55 new (160 total, up from 105), covering TEST 1-50 of the request
plus abstention/guard cases. No prior test removed.

**Deliberately NOT implemented as law** — recorded in
`NEEDS_AUTHORITY_VALIDATION.md`: Fard Badar / para 7.29 procedure; Girdawari
correction jurisdiction; Jamabandi cycle timing; Khasra-number permanence;
specific-Khasra sale restrictions; Murabba size; unconfirmed transliterations.

**Explicitly deferred, not faked**: duplicate/overlapping-photo detection and
page-order/orientation reconstruction (rule 20) need real image-level processing
(perceptual hashing, EXIF/rotation analysis) — out of scope for this text/schema
pass; noted here rather than stubbed. A second concrete extraction provider (e.g. a
Claude vision adapter) was not built — the `StructuredLLMClient` Protocol already
makes this a drop-in addition whenever needed, so nothing architectural blocks it.
