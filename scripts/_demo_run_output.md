# Synthetic Fard Demo Run

## Validation (Axiom Gates)

- **AG-01**: passed=True, checked=1, skipped=0, issues=0
- **AG-02**: passed=True, checked=11, skipped=0, issues=0
- **AG-03**: passed=True, checked=2, skipped=0, issues=0
- **AG-04**: passed=True, checked=0, skipped=1, issues=1
    - [warning] Document Sanghol: Document completeness check skipped: no page states a total page count.
- **AG-05**: passed=True, checked=0, skipped=1, issues=0
- **AG-06**: passed=True, checked=0, skipped=0, issues=0
- **AG-07**: passed=True, checked=0, skipped=0, issues=0

**Overall validation passed:** True

## Reconciliation (Approved/Pending Mutation Rule)

- OWN-1: status=superseded_by_approved_mutation, mutations=['MUT-1']
- OWN-2: status=as_recorded_active, mutations=[]
- OWN-3: status=as_recorded_active, mutations=[]
- (Khewat-level: KHW-1): status=as_recorded_active, mutations=[]

## Double-counting proof

- Khatauni KHT-1 recorded area: 900 sarsahi
- Khatauni KHT-2 recorded area: 630 sarsahi
- Correct Khewat total (KHT-1 + KHT-2, each counted once): 1530 sarsahi
- A double-counting bug (e.g. KHT-1 area x2, ignoring KHT-2) would have produced: 1800 sarsahi
- PROVEN: 1530 sarsahi != 1800 sarsahi, and 1530 == 900 + 630 (1530)
- Assertion passed: no double-counting occurred.

## Simulated user questions

### 1. Who are the owners?

**Record says:** Chaman Lal s/o Sohan Lal -- Khewat KHW-1, share 1/2
Ram Lal s/o Sohan Lal -- Khewat KHW-1, share 1/4
Ki[smudged]an Lal s/o Sohan Lal -- Khewat KHW-1, share 1/4 (uncertain/illegible)

**Calculated:** 3 owner record(s) across 1 Khewat(s).

**Interpretation:** (none)

**Evidence:** p.1: "Chaman Lal s/o Sohan Lal -- 1/2 hissa"; p.1: "Ram Lal s/o Sohan Lal -- 1/4 hissa"; p.1: "Ki...an Lal s/o Sohan Lal -- 1/4 hissa"

**Confidence:** (not applicable)

**Verification required:** YES -- One or more owner entries are marked illegible/uncertain/not_present.

### 2. How much land does Chaman Lal have?

**Record says:** Ownership interests for Chaman Lal s/o Sohan Lal in Khewat KHW-1:
Khewat-level default, inherited by Khatauni(s) KHT-1, KHT-2: area 8 kanal 10 marla 0 sarsahi, share 1/2

**Calculated:** 1/2 of 8 kanal 10 marla 0 sarsahi = 4 kanal 5 marla 0 sarsahi

**Interpretation:** CAUTION: An approved/sanctioned mutation exists against this owner or Khewat. Per the Approved Mutation Rule, ownership as recorded in this Fard row may no longer be current. Digital Patwari does not compute a new share or owner from free-text mutation wording -- verify against the mutation record.

**Evidence:** p.1: "Chaman Lal s/o Sohan Lal -- 1/2 hissa"; p.1: "Khewat No. 1"

**Confidence:** high

**Verification required:** YES -- An approved mutation affecting this owner or their Khewat is recorded; the figure above reflects the Fard as recorded and may no longer be current.

### 2. How much land does Ram Lal have?

**Record says:** Ownership interests for Ram Lal s/o Sohan Lal in Khewat KHW-1:
Khewat-level default, inherited by Khatauni(s) KHT-1, KHT-2: area 8 kanal 10 marla 0 sarsahi, share 1/4

**Calculated:** 1/4 of 8 kanal 10 marla 0 sarsahi = 2 kanal 2 marla 4 sarsahi (exact: 765/2 sarsahi, truncated for display)

**Interpretation:** No mutation is recorded against this owner or Khewat; ownership as recorded is currently active.

**Evidence:** p.1: "Ram Lal s/o Sohan Lal -- 1/4 hissa"; p.1: "Khewat No. 1"

**Confidence:** high

**Verification required:** No

### 2. How much land does Ki[smudged]an Lal have?

**Record says:** Ownership interests for Ki[smudged]an Lal s/o Sohan Lal in Khewat KHW-1:
Khewat-level default, inherited by Khatauni(s) KHT-1, KHT-2: area 8 kanal 10 marla 0 sarsahi, share 1/4

**Calculated:** (not calculated -- see verification note)

**Interpretation:** No mutation is recorded against this owner or Khewat; ownership as recorded is currently active.

**Evidence:** p.1: "Ki...an Lal s/o Sohan Lal -- 1/4 hissa"; p.1: "Khewat No. 1"

**Confidence:** (not applicable)

**Verification required:** YES -- Owner extraction status is uncertain/illegible/not_present on one or more rows.

### 3. What is the total area of the Khewat?

**Record says:** Sum of each Khatauni's own recorded_total_area under Khewat KHW-1 (each counted once).

**Calculated:** 8 kanal 10 marla 0 sarsahi

**Interpretation:** (none)

**Evidence:** (none attached)

**Confidence:** (not applicable)

**Verification required:** No

### 4. Which Khataunis belong to the Khewat?

**Record says:** KHT-1, KHT-2 (both khewat_id=KHW-1).

**Calculated:** 2 Khataunis.

**Interpretation:** Confirmed via AG-02's Khatauni.khewat_id cross-check (passed).

**Evidence:** p.2: "Khatauni 1, total 5-0"; p.3: "Khatauni 2, total 3-10"

**Confidence:** high

**Verification required:** No

### 5. Which Khasras are connected to Chaman Lal?

**Record says:** Khasra numbers recorded under Khatauni(s) KHT-1, KHT-2: 17, 18, 22, 23.

**Calculated:** (not calculated -- see verification note)

**Interpretation:** Khasra numbers are a spatial description of the Khewat/Khatauni, not a direct owner-to-parcel assignment -- this Fard does not establish that this owner individually possesses any specific Khasra among these.

**Evidence:** p.1: "Khewat No. 1"

**Confidence:** (not applicable)

**Verification required:** No

### 5. Which Khasras are connected to Ram Lal?

**Record says:** Khasra numbers recorded under Khatauni(s) KHT-1, KHT-2: 17, 18, 22, 23.

**Calculated:** (not calculated -- see verification note)

**Interpretation:** Khasra numbers are a spatial description of the Khewat/Khatauni, not a direct owner-to-parcel assignment -- this Fard does not establish that this owner individually possesses any specific Khasra among these.

**Evidence:** p.1: "Khewat No. 1"

**Confidence:** (not applicable)

**Verification required:** No

### 6. Has any owner sold or purchased land?

**Record says:** [Approved] Sale scope=Specific_Khasra khasra(s)=17 -- "Mutation No. 245: Chaman Lal sold Khasra No. 17 (3 Kanal) to Ram Lal, sanctioned 12-03-2021." (meaning: Sale of a specific Khasra (No. 17), not an undivided share, sanctioned and approved.)

**Calculated:** (not calculated -- see verification note)

**Interpretation:** CAUTION: one or more of these mutations is approved/sanctioned. Per the Approved Mutation Rule, active ownership may differ from the plain Fard row -- verify against the mutation record rather than assuming the row alone.

**Evidence:** p.1: "Inteqal No. 245 dated 12-03-2021, sanctioned"

**Confidence:** (not applicable)

**Verification required:** No

### 7. Is the mutation an undivided-share transfer or a specific-Khasra transfer?

**Record says:** Mutation MUT-1 has transfer_scope=Specific_Khasra, affected_khasra_numbers=['17'].

**Calculated:** N/A (categorical, not numeric).

**Interpretation:** This is a specific-Khasra transfer (Khasra 17), not an undivided-share transfer.

**Evidence:** p.1: "Inteqal No. 245 dated 12-03-2021, sanctioned"

**Confidence:** high

**Verification required:** No

### 8. Explain Column 8.

**Record says:** [Informational] "Column 8 note: field boundary re-verified by Patwari during 2019 girdawari." (meaning: Informational field note; no effect on ownership or mutation status.)

**Calculated:** (not calculated -- see verification note)

**Interpretation:** (none)

**Evidence:** p.1: "Khana Kaifiyat: boundary re-verified 2019"

**Confidence:** (not applicable)

**Verification required:** No

### 9. Is anything uncertain or inconsistent?

**Record says:** Raw share as recorded: 1/4

**Calculated:** Normalized exact share: 1/4

**Interpretation:** No mutation is recorded against this owner or Khewat; ownership as recorded is currently active.

**Evidence:** p.1: "Ki...an Lal s/o Sohan Lal -- 1/4 hissa"

**Confidence:** low

**Verification required:** YES -- Owner extraction status is 'uncertain'/'illegible'/'not_present' on one or more of this owner's rows.

### 10. Explain the Fard in simple English.

**Record says:** Village: Sanghol (Hadbast 142), Jamabandi year 2020-21.
This Fard records 1 Khewat(s) with 3 owner entr(y/ies).
Total recorded area: 8 kanal 10 marla 0 sarsahi.
Mutations: 1 approved, 0 pending.
Axiom gate validation: PASSED.

**Calculated:** (not calculated -- see verification note)

**Interpretation:** (none)

**Evidence:** (none attached)

**Confidence:** (not applicable)

**Verification required:** No
