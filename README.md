# Digital Patwari

**Upload a Punjab Fard or Jamabandi. Understand what it says, how the conclusion was reached, and where the evidence appears.**

Digital Patwari is an evidence-first system for understanding Punjab land records. Its purpose is not merely to digitise a Fard, but to make the record understandable to an ordinary citizen while preserving the structure, uncertainty and evidence of the original document.

## The problem

Punjab citizens can obtain digital land records, but a digital document is not automatically an understandable document.

A Fard may spread one ownership record across several pages. A Khewat may begin on one page, continue through blank cells on another, contain multiple Khataunis, and end with a total several pages later. Owners, shares, possession entries, mutations, mortgages and remarks may all interact.

A system that reads each page in isolation can produce a confident but incorrect answer.

Digital Patwari is being built to solve that deeper problem:

> **Access gives a citizen the document. Digital Patwari should help the citizen understand it.**

## Our guiding philosophy

### 1. Evidence before conclusions

Every important answer should be traceable to its source page, column, region or preserved text. The system should be able to show not only *what* it concluded, but *why*.

### 2. Observe first, assemble second

The system first records what each page visibly contains as a page observation. It does not immediately force every page into a final ownership hierarchy.

Only after page-level evidence has been preserved does the cross-page assembler connect Khewats, Khataunis, Khasras, owners and totals into one canonical Fard document.

This distinction is essential for records containing blank continuation cells and information carried across page boundaries.

### 3. Blank does not mean absent

A blank Khewat or owner cell on a continuation page may mean “continued from the previous page,” not “no Khewat” or “no owner.”

Digital Patwari must preserve the blank observation, examine its surrounding structure and page sequence, and avoid silently inventing a value.

### 4. Uncertainty must remain visible

If text is unclear, malformed, conflicting or incomplete, the system should say so. It must not turn uncertainty into false precision.

Possible states include:

- complete;
- complete with warnings;
- partial;
- failed;
- requires human verification.

Missing or failed pages must never be treated as proof that information is absent.

### 5. Humans are partners, not error handlers

When AI cannot confidently read a name, share, Khewat, Khatauni, Khasra or area, it should ask a focused question and show the relevant evidence.

Human corrections should be explicit and auditable. The original observation must remain available so that a correction never silently rewrites history.

### 6. Calculations must be reproducible

Ownership shares and land-area calculations should be performed using exact arithmetic and documented rules. A citizen should be able to inspect the source share, the governed land area and the resulting calculation.

### 7. Simple language, faithful meaning

The interface should explain revenue terminology in clear Punjabi and English without changing its legal or administrative meaning.

The final product should be usable by a farmer, family member, buyer, NRI, junior official or lawyer—not only by a programmer or revenue expert.

### 8. Privacy by design

Fards may contain personal and property information. API keys must never appear in code, logs or generated reports. Extraction outputs and page caches should remain outside the repository unless their inclusion is deliberate and reviewed.

### 9. No silent success

A saved JSON file does not by itself mean that extraction succeeded. Page failures, provider errors, validation failures and incomplete evidence must remain visible in the final status.

### 10. Assistance, not legal adjudication

Digital Patwari explains the information contained in a land record. It does not make a legal determination of title or ownership and does not replace verification by the Punjab Revenue Department or advice from a qualified legal professional.

## What Digital Patwari aims to explain

- recorded owners and their shares;
- Khewats and their connected Khataunis;
- Khasra numbers, parcels and recorded areas;
- mutations and changes in ownership;
- possession, cultivation and Girdawari entries;
- mortgages, remarks and encumbrances;
- exact land-area calculations;
- inconsistencies and uncertain readings;
- evidence supporting every important answer.

## Architecture

```text
Fard PDF or page images
        |
        v
Per-page evidence observations
        |
        v
Cross-page continuation and hierarchy assembly
        |
        v
Canonical DigitalPatwariDocument
        |
        +--> Ownership and area calculations
        +--> Validation and consistency gates
        +--> Human-verification questions
        +--> Evidence-backed citizen explanations
```

The current architecture includes:

- per-page extraction;
- evidence-preserving page observations;
- deterministic cross-page assembly;
- Khewat/Khatauni/Khasra hierarchy reconstruction;
- page-level caching and retry support;
- partial-failure reporting;
- human-verification records and audited corrections;
- canonical ownership, query, reconciliation and validation engines.

## The continuation case that shaped the architecture

One important test case contains Khewat **198/185** beginning on one page, Khatauni **219** on the next page and Khatauni **220** on a following page. Some continuation cells are blank even though the ownership context continues.

The architectural rule is:

- preserve what each page actually prints;
- treat Column 1 as Khewat and Column 2 as Khatauni;
- carry context forward only when supported by page order and structure;
- keep both Khataunis under the correct Khewat;
- apply Khewat-governed ownership across its Khataunis according to the recorded rules;
- retain page evidence for every inherited or calculated result.

This must be a generic rule for Punjab Fards—not a hard-coded exception for one document.

## Current verification status

The page-observation architecture has passed the repository’s automated offline test suite and the GitHub Actions test workflow.

A controlled live Gemini smoke test was attempted, but Google returned `429 RESOURCE_EXHAUSTED` before processing the page. Therefore, live-provider extraction with the new architecture is **not yet verified**. This is a provider quota limitation, not evidence that the architecture passed or failed the real-page test.

The project should not be described as production-ready until controlled live-provider and complete multi-page Fard verification succeed.

## Intended citizen experience

The final experience should be simple:

1. Upload a Fard.
2. Wait while each page is checked.
3. See a plain-language summary.
4. Explore owners, Khewats, Khataunis, Khasras, mutations, possession, remarks and calculations.
5. Tap any important statement to view its evidence.
6. Answer a focused verification question when the system is uncertain.
7. Ask Digital Patwari questions about that specific Fard.

The complexity belongs inside the system. The citizen should receive clarity, evidence and an honest statement of uncertainty.

## Development status

Digital Patwari is under active development. The immediate priorities are:

1. complete a successful one-page live-provider schema test;
2. verify the Khewat 198/185 continuation across the relevant pages;
3. run a complete 11-page Fard with cached per-page extraction;
4. verify ownership, areas, mutations, remarks and axiom gates;
5. build a citizen-facing Punjabi/English beta interface;
6. add authentication, authorization and encrypted storage before broader use.

## Important notice

Digital Patwari is an explanatory and verification-assistance tool. Source records, official revenue entries and competent professional advice remain authoritative.
