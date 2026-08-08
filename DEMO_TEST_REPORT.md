# Digital Patwari — Offline Demo Test Report

No network calls. No API key used. No Gemini/vision model invoked anywhere in this
run. Everything below exercises the pipeline **from the point after image/PDF
extraction** — i.e. structured data → validation → reconciliation → query — against
one hand-built synthetic Fard fixture (`scripts/demo_synthetic_fard.py`).

## 1. The fixture

Constructed directly as `DigitalPatwariDocument` objects (not from JSON/LLM output),
covering every element the demo asked for:

- 1 Khewat (`KHW-1`), 3 owners with shares `1/2 + 1/4 + 1/4 = 1/1` (exact).
- One owner (`Ki[smudged]an Lal`, `OWN-3`) deliberately marked `status=UNCERTAIN` —
  a simulated smudged/illegible entry.
- 2 Khataunis under the one Khewat (`KHT-1`: 5 kanal recorded; `KHT-2`: 3 kanal 10
  marla recorded) — the specific setup that would expose a double-counting bug.
- 4 Khasras total (2 per Khatauni), each with kanal/marla area, soil/irrigation/
  cultivation classification, summing exactly to their Khatauni's recorded total.
- 1 mutation (`MUT-1`): Approved, Sale, Specific_Khasra scope, Khasra 17, targeting
  Owner `OWN-1` (Chaman Lal).
- 1 Column 8 remark (Informational) on the Khewat.
- Every entity carries a `SourceReference` (page number + raw text) so every answer
  below can cite evidence.

## 2. Validation (Axiom Gates)

| Gate | Passed | Checked | Skipped | Issues |
|---|---|---|---|---|
| AG-01 (share summation) | True | 1 | 0 | 0 |
| AG-02 (linkage/integrity) | True | 11 | 0 | 0 |
| AG-03 (area consistency) | True | 2 | 0 | 0 |

**Overall: PASSED.**

## 3. Reconciliation (Approved/Pending Mutation Rule)

| Entity | Status | Mutations |
|---|---|---|
| OWN-1 (Chaman Lal) | `superseded_by_approved_mutation` | `[MUT-1]` |
| OWN-2 (Ram Lal) | `as_recorded_active` | `[]` |
| OWN-3 (Ki[smudged]an Lal) | `as_recorded_active` | `[]` |
| KHW-1 (Khewat-level) | `as_recorded_active` | `[]` |

Chaman Lal's approved mutation correctly supersedes only *his* ownership row, not
his co-owners' — the Khevat-level rollup stays active because the mutation targets
the Owner, not the whole Khewat.

## 4. Double-counting proof (specifically required by the task)

```
Khatauni KHT-1 recorded area: 900 sarsahi
Khatauni KHT-2 recorded area: 630 sarsahi
Correct Khewat total (KHT-1 + KHT-2, each counted once): 1530 sarsahi
A double-counting bug (e.g. KHT-1 area x2, ignoring KHT-2) would have produced: 1800 sarsahi
PROVEN: 1530 != 1800, and 1530 == 900 + 630 (1530)
Assertion passed: no double-counting occurred.
```

`900 sarsahi` = 5 kanal exactly; `630 sarsahi` = 3 kanal 10 marla exactly; the sum
`1530 sarsahi` = 8 kanal 10 marla, matching every downstream answer below. This is
also independently covered by `tests/test_query.py::test_owner_land_never_double_counts_across_multiple_khataunis`
and `tests/test_axiom_gates.py::test_ag03_multiple_khataunis_in_one_khewat_are_not_double_counted`.

## 5. Simulated user questions

### 1. Who are the owners?

**Record says:** Chaman Lal s/o Sohan Lal — Khewat KHW-1, share 1/2; Ram Lal s/o
Sohan Lal — Khewat KHW-1, share 1/4; Ki[smudged]an Lal s/o Sohan Lal — Khewat
KHW-1, share 1/4 (uncertain/illegible).
**Calculated:** 3 owner record(s) across 1 Khewat(s).
**Interpretation:** (none)
**Evidence:** p.1 (x3, one per owner's raw text).
**Confidence:** n/a (aggregate answer).
**Verification required:** YES — one owner entry marked illegible/uncertain.

### 2. How much land does each owner have?

**Chaman Lal**
- Record says: Khewat total = 8 kanal 10 marla 0 sarsahi.
- Calculated: 1/2 of 8-10-0 = 4 kanal 5 marla 0 sarsahi.
- Interpretation: CAUTION — an approved mutation is recorded against this owner; the
  figure reflects the Fard as recorded and may no longer be current.
- Evidence: p.1 (owner row), p.1 (Khewat header).
- Confidence: high.
- **Verification required: YES** — approved mutation may have superseded this row.

**Ram Lal**
- Record says: Khewat total = 8 kanal 10 marla 0 sarsahi.
- Calculated: 1/4 of 8-10-0 = 2 kanal 2 marla 4 sarsahi (exact: 765/2 sarsahi).
- Interpretation: no mutation recorded; ownership as recorded is active.
- Confidence: high.
- Verification required: No.

**Ki[smudged]an Lal**
- Record says: Khewat total = 8 kanal 10 marla 0 sarsahi.
- Calculated: **not calculated** — owner status is uncertain, so no number is
  presented as settled.
- Interpretation: no mutation recorded.
- Confidence: n/a.
- **Verification required: YES** — owner extraction status is 'uncertain'.

### 3. What is the total area of the Khewat?

**Record says:** Sum of each Khatauni's own recorded_total_area (each counted
once). **Calculated:** 8 kanal 10 marla 0 sarsahi. **Verification required:** No.

### 4. Which Khataunis belong to the Khewat?

**Record says:** KHT-1, KHT-2. **Calculated:** 2 Khataunis. **Interpretation:**
confirmed via AG-02's Khatauni→Khewat cross-check (passed). **Verification
required:** No.

### 5. Which Khasras are connected to each owner?

For both Chaman Lal and Ram Lal: **Record says:** Khasra numbers recorded under
Khewat KHW-1: 17, 18, 22, 23. **Interpretation:** Khasra numbers are a spatial
description of the Khewat/Khatauni, *not* a direct owner-to-parcel assignment —
the Fard does not establish individual possession of any specific Khasra.
**Verification required:** No (the caveat itself is the correct, non-overclaiming
answer, not an uncertainty).

### 6. Has any owner sold or purchased land?

**Record says:** [Approved] Sale, scope=Specific_Khasra, khasra(s)=17 — "Mutation
No. 245: Chaman Lal sold Khasra No. 17 (3 Kanal) to Ram Lal, sanctioned
12-03-2021." **Interpretation:** CAUTION — this mutation is approved/sanctioned;
active ownership may differ from the plain Fard row. **Evidence:** p.1. **Verification
required:** No (this answer's whole content *is* the mutation notice; no additional
uncertainty flag needed on top of surfacing it).

### 7. Is the mutation an undivided-share transfer or a specific-Khasra transfer?

**Record says:** `transfer_scope=Specific_Khasra`, `affected_khasra_numbers=['17']`.
**Interpretation:** specific-Khasra transfer (Khasra 17), not an undivided share.
**Verification required:** No.

### 8. Explain Column 8.

**Record says:** [Informational] "Column 8 note: field boundary re-verified by
Patwari during 2019 girdawari." **Interpretation:** (none — informational, no
ownership effect). **Verification required:** No.

### 9. Is anything uncertain or inconsistent?

**Record says:** Ki[smudged]an Lal's raw share = 1/4. **Calculated:** normalized =
1/4. **Confidence:** low. **Verification required: YES** — owner extraction status
is 'uncertain'. (This is the one deliberately-uncertain field in the fixture, and
the system correctly refuses to present it as settled.)

### 10. Explain the Fard in simple English.

> Village: Sanghol (Hadbast 142), Jamabandi year 2020-21. This Fard records 1
> Khewat(s) with 3 owner entr(y/ies). Total recorded area: 8 kanal 10 marla 0
> sarsahi. Mutations: 1 approved, 0 pending. Axiom gate validation: PASSED.

**Verification required:** No (this summary itself passed gates; it doesn't hide
that Chaman Lal's row needs individual verification — that's surfaced at the
owner-specific answers above, not smuggled into the aggregate summary).

## 6. Bug found and fixed during this run

**What happened:** question 2 for Chaman Lal, on the *first* run, showed
`Interpretation: CAUTION — approved mutation may make this stale` but
`Verification required: No`. The prose and the machine-checkable flag disagreed —
exactly the kind of thing a UI would get wrong (show the number as settled fact,
never surface the caution banner, because it keys off `uncertain`, not the
interpretation string).

**Root cause classification: reasoning.** Not extraction (nothing was misread),
not schema (fields were correct), not mapping (Khewat/Khatauni/Khasra linkage was
correct), not calculation (4 kanal 5 marla is exactly 1/2 of 8-10-0), not
reconciliation (the reconciliation step correctly computed
`superseded_by_approved_mutation`). The bug was in `query.py`'s answer-assembly:
`owner_share()` and `owner_land()` read the reconciliation status to build the
*interpretation* text, but never fed it into the `uncertain` flag.

**Fix:** added `FardQueryEngine._reconciliation_flags_uncertain()` and wired it
into `owner_share()` and `owner_land()`, so `uncertain=True` whenever an approved
mutation may have superseded the row — while still showing the "as recorded"
calculated value (this isn't missing data, it's stale-risk data). Also gave
`mutations_for()` its own tailored interpretation text instead of reusing the
share/land-specific `_ownership_note()` wording, since a mutation *being reported*
isn't itself an uncertainty about that report.

**Regression tests added** (`tests/test_query.py`):
- `test_owner_share_flags_verification_required_when_approved_mutation_supersedes`
- `test_owner_land_flags_verification_required_when_approved_mutation_supersedes`
- `test_owner_land_not_flagged_uncertain_when_only_pending_mutation_exists` (proves
  the fix doesn't over-trigger — a *pending* mutation must NOT flip the flag, per
  the Pending Mutation Rule).

No other production code was changed to make this demo "look successful." This was
a real inconsistency the demo happened to expose; the fixture was not adjusted to
avoid it.

## 7. Full test suite

```
70 passed, 1 warning in ~1.1s
```

70/70 (67 pre-existing + 3 new regression tests from the fix above). Zero
regressions.

## 8. What genuinely works without the AI extraction layer

- Full Pydantic schema + `extra="forbid"` contract enforcement.
- All three axiom gates (AG-01 share summation, AG-02 linkage/integrity/uniqueness/
  remark+mutation target resolution, AG-03 area consistency to the sarsahi).
- Reconciliation (Approved/Pending Mutation Rule) as checked code, never inventing
  values.
- The full query/explanation layer and its abstention behavior (no-match,
  ambiguous-match, uncertain-status, incomplete-area all correctly refuse to
  present a settled answer).
- The multi-Khatauni-per-Khewat non-double-counting guarantee, proven both by
  targeted regression tests and by this end-to-end run.
- Exact-fraction arithmetic throughout (`Fraction`, never float).

None of this depends on Gemini. Everything above is exercised purely by
constructing `DigitalPatwariDocument` objects directly — which is also exactly
what a human-correction or manual-entry path into Digital Patwari would use.

## 9. What still requires Gemini (or another vision/model API)

- Reading the actual Punjabi/Gurmukhi text off a scanned Fard page.
- Producing the initial structured JSON candidate (Khewat/Khatauni/Owner/Khasra/
  Mutation/Remark) from that image — i.e. everything upstream of what this demo
  exercised.
- Judging legibility (deciding a field is `illegible`/`uncertain` in the first
  place) — this demo simulated that judgment by hand; the real system depends on
  the model making that call honestly per the prompt's zero-guesswork instruction,
  which is unverified against real scans.
- Multi-page continuation (a Khewat spanning two pages) — still unimplemented
  regardless of model.

## 10. Ready for a real PDF test tomorrow?

**Conditionally yes**, with expectations set correctly:

- Everything downstream of extraction (validation → reconciliation → query) is now
  demonstrated correct on a realistic, deliberately adversarial fixture, and has a
  70-test regression suite behind it.
- What tomorrow's real-PDF run actually tests is the *one* part this demo could
  not: whether Gemini reads the scan accurately, follows the ID/category/mutation
  conventions in the prompt, and is honest about illegibility. Expect the first
  real run to surface extraction-layer issues (wrong IDs, missed mutations,
  overconfident guesses) that this demo, by construction, could not have shown —
  it never exercised the model at all.
- Recommend treating the real-PDF run the same way this session treated the
  demo: as an evaluation that may expose a genuine bug, classified by root cause
  (extraction/schema/mapping/calculation/reconciliation/reasoning), fixed with a
  regression test, not patched just to make that one PDF pass.
