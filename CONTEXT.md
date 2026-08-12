# Digital Patwari

Digital Patwari explains Punjab Fard and Jamabandi land records while preserving the distinction between what the record states, what can be calculated, and what still requires human verification.

## Land Record Structure

**Fard**:
An extract of information recorded in Punjab land records for a particular landholding context. It is evidence of what the revenue record states, not by itself a final legal determination.
_Avoid_: Ownership certificate, title guarantee

**Jamabandi**:
The record-of-rights snapshot for a stated village and period from which ownership, cultivation, parcel, and related revenue entries are read.
_Avoid_: Current title deed

**Khewat**:
The ownership account in a Fard or Jamabandi. Ownership is read at this level by default and applies to the Khataunis governed by the account unless the record explicitly provides a Khatauni-level ownership group.
_Avoid_: Khatauni, cultivation account

**Khatauni**:
The cultivation or possession account under a Khewat that groups the relevant Khasras. A Khatauni does not create a separate ownership group merely because its ownership cell is blank.
_Avoid_: Khewat, ownership account

**Khasra**:
A numbered land parcel recorded under a Khatauni, with its own recorded area and land-use context.
_Avoid_: Murabba, owner share

**Murabba**:
A larger mapped land grouping within which Khasras are identified. Its identifier must remain distinct from the Khasra number.
_Avoid_: Khasra

**Document Header**:
The shared identity of the land record, including its village, Hadbast number, Jamabandi year, and other printed record identifiers.
_Avoid_: Page header

**Vishesh Kathan**:
The special-remarks part of the record, also known as Khana Kaifiyat, containing entries such as mutations, encumbrances, rent details, or other qualifications.
_Avoid_: Ownership column

## Ownership and Possession

**Owner**:
A person or legal party recorded with an ownership interest in a Khewat or in an explicitly scoped Khatauni ownership group.
_Avoid_: Cultivator, possessor

**Ownership Share**:
The exact fractional interest recorded for an owner within the ownership scope stated by the record.
_Avoid_: Calculated land area, cultivation share

**Khewat-Level Ownership**:
The default ownership group for a Khewat, governing every Khatauni under it that does not state its own owner group.
_Avoid_: Whole-document ownership

**Khatauni-Level Ownership Override**:
An owner group explicitly recorded for one Khatauni that governs only that Khatauni instead of the Khewat-level default.
_Avoid_: Blank ownership cell, duplicated Khewat ownership

**Blank Ownership Continuation**:
A blank ownership cell on a continued Khatauni that inherits the applicable Khewat ownership rather than representing no owner or unknown ownership.
_Avoid_: Ownerless Khatauni, zero ownership

**Undivided Khewat Share**:
An ownership interest expressed as a fraction of the applicable Khewat scope rather than as ownership of named Khasras.
_Avoid_: Specific-parcel ownership

**Specific-Khasra Interest**:
An interest limited by the record to named Khasras, whose extent comes from those parcels rather than from multiplying a fraction across the whole Khewat.
_Avoid_: Undivided Khewat share

**Cultivation Interest**:
A person's recorded cultivation or possession relationship to a Khatauni, kept separate from legal ownership.
_Avoid_: Ownership interest

**Girdawari**:
The cultivation and possession dimension of the revenue record. A Girdawari entry does not by itself establish ownership.
_Avoid_: Ownership record

## Transactions and Qualifications

**Mutation (Inteqal)**:
A revenue-record transaction entry concerning a change or claimed change affecting land interests. The existence of a mutation number alone does not establish that the mutation was sanctioned.
_Avoid_: Automatically completed transfer

**Approved Mutation**:
A mutation whose own record wording establishes that it was sanctioned or approved and may therefore affect the interpreted ownership position.
_Avoid_: Referenced mutation, pending mutation

**Pending Mutation**:
A mutation that has not been established by the record as sanctioned and therefore does not alter the recorded ownership position.
_Avoid_: Approved mutation

**Remark**:
A recorded qualification attached to a Khewat, Khatauni, Owner, or Khasra, preserved separately from the entity it qualifies.
_Avoid_: Silent ownership change

**Rehin**:
A mortgage entry in the revenue record. Its presence does not establish that the mortgage remains active without checking for a corresponding release or discharge.
_Avoid_: Automatically active mortgage

**Mushtari**:
A purchaser or buyer (`ਮੁਸ਼ਤਰੀ`) named in the record. The role identifies the party but does not by itself establish whether the purchase covers a whole Khewat share or specific Khasras.
_Avoid_: Whole-Khewat owner

**Baiyan**:
A seller (`ਬਾਇਆਂ`) named in a revenue transaction.
_Avoid_: Purchaser, Mushtari

## Area and Land Description

**Kanal, Marla, and Sarsahi**:
The ordered land-area units used to preserve and compare recorded areas exactly at the smallest unit present.
_Avoid_: Decimal approximation

**Area Scope**:
The level measured by a printed area figure, such as a Khasra area, Khatauni subtotal, Khewat total, or document total.
_Avoid_: Additional area

**Kita**:
A count of Khasra numbers or parcels, not a unit of land area.
_Avoid_: Kanal, Marla, Sarsahi

**Khud Kasht**:
Self-cultivation by an owner, showing that ownership and cultivation are recorded for the same party without making the two concepts interchangeable.
_Avoid_: Ownership alone

**Muzara**:
A tenant or non-owner cultivator recorded in relation to the land.
_Avoid_: Owner

**Chahi**:
Land classified as irrigated by a well.

**Nehri**:
Land classified as irrigated by a canal.

**Barani**:
Land classified as rain-fed.

**Gair Mumkin**:
Land (`ਗੈਰ ਮੁਮਕਿਨ ਜ਼ਮੀਨ`) classified as uncultivable or waste land.

**Mazru'a**:
Land (`ਮਜ਼ਰੂਆ ਜ਼ਮੀਨ`) classified as cultivated.
_Avoid_: Gair Mumkin, Banjar

## Evidence and Verification

**Page Observation**:
The evidence preserved from one physical page before facts from multiple pages are assembled into one document interpretation.
_Avoid_: Final document conclusion

**Field Observation**:
The extracted value and original visible evidence for one field, together with its page, column, confidence, and verification state.
_Avoid_: Corrected value only

**Verification Issue**:
A focused question asking a person to resolve one ambiguous, unreadable, conflicting, invalid, or arithmetically inconsistent observation.
_Avoid_: General warning

**Human Correction**:
An audited replacement or structural adjustment supplied by a verifier while the original machine-read evidence remains preserved.
_Avoid_: Overwritten evidence

**Canonical Document**:
The assembled interpretation of the Fard that contains only safely represented facts while retaining uncertainty and links to supporting evidence.
_Avoid_: Raw AI response, legal judgment

## Provisional Revenue Language

**Maqbuza Malkan — Provisional**:
A phrase read as meaning possession by the owners, currently treated as a useful interpretation rather than an independently confirmed rule.
_Avoid_: Conclusive proof of ownership
