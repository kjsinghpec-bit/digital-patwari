# Needs Authority Validation

Propositions encountered in training material (Punjabi instructional videos,
including a Nirmal Patwari lesson) that Digital Patwari has **deliberately NOT
implemented as deterministic law**.

They are recorded here because they are plausible and potentially important,
not because they are confirmed. Each needs checking against the Punjab Land
Records Manual, the relevant Act/Rules, or a qualified revenue officer before
any of it becomes code.

## Why this file exists

Automatic Punjabi YouTube captions corrupt exactly the things that matter most
in a revenue record: fractions, denominators, Khasra numbers, dates, areas, and
Urdu/Persian revenue vocabulary. Concepts from such sources are usable; specific
numbers, spellings, and legal/procedural claims from them are not authoritative
on their own.

Digital Patwari's policy: **learn concepts from videos, never treat raw
auto-caption numbers or legal claims as ground truth.** Where caption, visible
document structure, and arithmetic consistency disagree, flag uncertainty.

## Classification scheme

| Class | Meaning |
|---|---|
| `CONFIRMED_DOMAIN_RULE` | Established; safe to implement |
| `NEW_GENERAL_READING_RULE` | Structural reading rule, consistent with the existing model |
| `USEFUL_HEURISTIC` | Helpful default, must stay overridable by evidence |
| `NEEDS_EXPERT_VALIDATION` | Needs a revenue professional's confirmation |
| `NEEDS_LEGAL_OR_MANUAL_VALIDATION` | Needs the Manual / Act / Rules checked |
| `TRANSCRIPT_ERROR_OR_UNRELIABLE` | Likely a caption artefact; do not use |

The same vocabulary is implemented in code as `TermValidation` in
`digital_patwari/terminology.py`, so a term's validation level travels with it
into every answer rather than living only in prose.

---

## Open items

### 1. Fard Badar and Punjab Land Records Manual para 7.29
**Class:** `NEEDS_LEGAL_OR_MANUAL_VALIDATION`

The lesson refers to Fard Badar and para 7.29 in connection with correcting
incorrect share entries.

**Not implemented.** Digital Patwari will report a share-sum inconsistency as a
mathematical fact (AG-01) and will **not** assert the legal consequence, the
correction procedure, or that the Jamabandi is legally invalid.

**To validate:** obtain the actual text of para 7.29; confirm scope, who may
initiate, and what class of error it covers.

### 2. Girdawari correction jurisdiction and procedure
**Class:** `NEEDS_AUTHORITATIVE_VALIDATION`

The lesson describes correcting Girdawari by consent or through an Assistant
Collector / Tehsildar.

**Not implemented.** Digital Patwari may state that *"recorded ownership and
recorded cultivation appear inconsistent"* but must not prescribe a remedy,
name a forum, or imply an entitlement to correction.

### 3. Jamabandi cycle timing (four-year / five-year)
**Class:** `NEEDS_MANUAL_OR_RULE_VALIDATION`

Historical revision cycles were discussed. Periods have varied over time and by
context.

**Not implemented.** No cycle length is hard-coded anywhere. `jamabandi_year` is
read from the document itself and never inferred from an assumed cycle.

### 4. Khasra number permanence until settlement/consolidation
**Class:** `NEEDS_MANUAL_OR_RULE_VALIDATION`

The claim that Khasra/survey numbers remain stable until a later settlement or
consolidation operation.

**Not implemented as an invariant.** Digital Patwari does not assume a Khasra
number identifies the same physical parcel across different Jamabandi years or
across consolidation events.

### 5. Specific-Khasra sale restrictions
**Class:** `NEEDS_LEGAL_OR_MANUAL_VALIDATION`

Statements about whether/when a co-sharer may sell a specific Khasra rather than
an undivided share.

**Not implemented.** Digital Patwari records *what the record says* about a
specific-parcel transaction (`ParcelInterest`, `MutationTransferScope`) and does
**not** opine on its validity or enforceability.

### 6. Murabba size / parcel count
**Class:** `NEEDS_EXPERT_VALIDATION`

No assumption is encoded about how large a Murabba is or how many Khasras it
contains. `murabba_number` is stored as an identifier only.

### 7. Transliteration of seller terminology ("Baya" / "Bai")
**Class:** `NEEDS_EXPERT_VALIDATION`

The seller/transferor term was heard via auto-caption and its spelling is not
confirmed. Implemented in `terminology.py` at `NEEDS_EXPERT_VALIDATION`, with
the original text always preserved as evidence.

### 8. "Mazru'a" / "Gair Mazru'a" spellings
**Class:** `NEEDS_EXPERT_VALIDATION`

Meanings (cultivated / uncultivated) are broadly established; the exact
transliteration came from an auto-captioned source. Raw text is preserved.

---

## Deliberately excluded from code, permanently

Digital Patwari answers questions about **what a record says and what follows
arithmetically from it**. It does not give legal advice, does not assert that a
document is legally valid or invalid, and does not prescribe remedies or forums.
Where a question needs that, the correct output is a flag for a Patwari,
revenue officer, or lawyer.
