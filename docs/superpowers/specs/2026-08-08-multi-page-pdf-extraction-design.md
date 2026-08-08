# Multi-page PDF extraction — design

Date: 2026-08-08

## Problem

`digital_patwari/document_io.py` currently sends an entire multi-page PDF to
Gemini as a single base64 blob in one `application/pdf` part. Running the
pipeline against a real 11-page Fard (`samples/real_fard/Chaman Lal
Sanghol.pdf`, confirmed via raw PDF page-tree inspection: `/Count 11`, 11
`/Type /Page` objects) produced a document with data from only 1 distinct
page. AG-04 (document completeness) correctly flagged this as an incomplete
document, and AG-01 (Khewat share summation) failed as a downstream
consequence of the missing pages' owner data.

This matches the "Multi-page architecture" section of the repo's `CLAUDE.md`,
which requires deterministic page ordering, small async batches, page-level
observations with source references, tracked continuation state across page
boundaries, and deterministic merge — none of which exist yet.

## Goals

- Extract every physical page of a caller-supplied PDF, not just the first.
- Correctly merge a Khewat/Khatauni that spans a page boundary into one
  entity rather than duplicating it.
- Keep failures for one page from silently discarding a document that has
  good data from the other pages.
- Stay inside Gemini's per-request schema complexity ceiling (see prior fix
  in `digital_patwari/providers/gemini.py`: `_generate_with_schema_fallback`
  auto-splits an overly-complex schema into multiple requests and merges the
  results) — per-page requests use the same full `DigitalPatwariDocument`
  schema and rely on that existing fallback.

## Non-goals

- Rendering pages to images. Pages stay as PDF bytes (`application/pdf`),
  split per-page with `pypdf`, to avoid a rasterization dependency and DPI
  tuning surface.
- Passing prior-page context into later page extraction calls. Pages are
  extracted independently and in parallel; continuation is resolved entirely
  by the post-hoc merge step, not by prompting.

## Schema change (approved)

Add two required fields, following the existing `raw_`/normalized
separation pattern used elsewhere (e.g. `raw_owner_name_parentage`):

```python
class Khewat(BaseModel):
    khewat_id: NonEmptyString        # internal, e.g. "KHW-1" (regenerated post-merge)
    khewat_number: NonEmptyString    # printed source value, e.g. "45"
    ...

class Khatauni(BaseModel):
    khatauni_id: NonEmptyString
    khatauni_number: NonEmptyString  # printed source value
    ...
```

These are the actual printed identifiers used as the merge key across pages.
`khewat_id`/`khatauni_id`/`khasra_id` remain the internal deterministic IDs
(`KHW-1`, `KHT-1`, `KHS-1`, ...) — after merging, they are *regenerated* from
final post-merge hierarchy position, since each page's own IDs are only
locally unique (two different pages independently numbering their first
Khewat "KHW-1" is expected and not a collision once regenerated).

`EXTRACTION_SYSTEM_PROMPT` gets one additional instruction: always populate
`khewat_number` / `khatauni_number` from the source's printed Khewat/Khatauni
number, distinct from the internal ID.

## Architecture / data flow

1. **`document_io.py`** — `load_document_parts` splits any PDF input into
   per-page parts using `pypdf.PdfReader` / `PdfWriter`: one single-page PDF
   (in-memory bytes, not written to disk) per physical page, each still
   `mime_type="application/pdf"`, each tagged with its 1-indexed page number
   and source filename. Non-PDF inputs (individual image files, directories
   of pre-split page images) are unaffected — already one page per part.

2. **`extraction.py`** — `FardExtractionParser.extract()` gains an async
   core (`_extract_async`), with the existing public `extract()` calling
   `asyncio.run(self._extract_async(...))` so `cli.py`'s call site is
   unchanged. Pages are processed in configurable-size batches (default 3)
   via `asyncio.gather`, each page independently calling
   `MyLLMAdapter.extract_structured` against the full `DigitalPatwariDocument`
   schema. Each page's result is a partial `DigitalPatwariDocument`-shaped
   dict; every entity extracted from that page carries
   `SourceReference.page_number` for that page.

   A single page's transport/validation failure is recorded per-page and
   does not abort the whole run — the merge step proceeds with whatever
   pages succeeded, and failed pages are reported in `parser_errors`.

3. **New `digital_patwari/merge.py`** — deterministic merge of the list of
   per-page partial documents into one `DigitalPatwariDocument`:
   - Group Khewats across pages by `khewat_number`.
   - Group Khataunis by `(khewat_number, khatauni_number)`.
   - Group Khasras by `(khatauni key, khasra_number)`.
   - Regenerate final `khewat_id`/`khatauni_id`/`khasra_id`/`owner_id`
     deterministically from post-merge hierarchy position (document →
     Khewat index → Khatauni index → Khasra/Owner index), per CLAUDE.md's
     "deterministic IDs from document identity, hierarchy, source page, and
     stable position" rule.
   - Concatenate `remarks` / `mutations` / `parcel_interests` /
     `cultivation_interests` / `area_observations` across pages, rewriting
     their `target_id` / `khasra_ids` / `transferor_owner_id` references to
     the regenerated IDs.
   - `document_header`, `layout`, `schema_version` are taken from the first
     page that has them; if a later page's `document_header` disagrees
     (different village/hadbast/year), that's recorded as a merge warning,
     not silently dropped or silently overwritten.
   - Never invent or drop data: a Khewat/Khatauni/Khasra appearing on only
     one page is kept as-is; nothing is deduplicated without a matching
     printed number.

4. AG-04 (document completeness) is unchanged in logic — it now checks
   genuinely multi-page extraction output instead of a single-page blob, so
   it becomes a meaningful check rather than one that always fires.

## Error handling

- Per-page transport errors (timeout, malformed JSON, schema validation
  failure on that page's partial output) are caught individually, recorded
  with the page number, and do not stop other pages' batches from running.
- If the merge step finds a `document_header` disagreement across pages,
  it's a `ValidationIssue`-style warning attached to the result, not an
  exception.
- Final Pydantic validation of the fully-merged document still happens
  exactly as today (`DigitalPatwariDocument.model_validate`), so a
  structurally invalid merge result still surfaces field-path errors via
  `pydantic.ValidationError.errors()`.

## Testing

- `tests/test_page_merge.py` (per CLAUDE.md's planned test layout): synthetic
  2-page partial documents where a Khewat starts on page 1 (owners only) and
  continues on page 2 (adds a Khatauni) — asserts the merged result has one
  Khewat with both the owners and the Khatauni, and that regenerated IDs are
  consistent and referenced correctly by any Remark/Mutation in the fixture.
- Additional case: two pages independently both extract a Khewat they each
  call `khewat_number="1"` — asserts they merge into one entity (this is the
  common case, not an edge case, since every page's first Khewat is often
  the continuation of the previous page's last one).
- Real smoke test: run the full pipeline against `samples/real_fard/Chaman
  Lal Sanghol.pdf` end-to-end and confirm AG-04 sees all 11 pages
  represented (passing is not required — the model's actual read of the
  document determines that — but the "page(s) present" count must reach 11).

## Open questions / risks

- `pypdf` is a new dependency (already present in `requirements.txt` per a
  prior update: `pypdf==4.10.0`).
- Splitting into per-page PDFs preserves any embedded page-level pagination
  text (e.g. "Page 5 of 8") intact per page, which AG-04 already parses from
  `SourceReference.total_pages`.
- Cost/quota: this trades one whole-document request for up to N per-page
  requests (batched, not all at once) — worth calling out since Gemini's
  free-tier daily quota is already a known constraint in this project.
