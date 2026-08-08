"""Structured data hand-transcribed from an independent manual reading of
samples/real_fard/Chaman Lal Sanghol.pdf (Jamabandi 2020-21, Village Sanghol,
Hadbast 310, Tehsil Khamano, District Fatehgarh Sahib), fed through the
UNMODIFIED digital_patwari pipeline (axiom gates -> reconciliation -> query).

This is NOT run through Gemini. It is a manual-reading -> pipeline
comparison: does the deterministic engine, given a human's transcription,
compute the same numbers the human derived by hand?

Chaman Lal (s/o Dharampal s/o Sambhu Nath) appears in three separate
Khewats in this Jamabandi. Each is modeled as its own Khewat per the
schema (Owner belongs to exactly one Khewat).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from digital_patwari.models import (
    AreaKanalMarlaSarsahi,
    DigitalPatwariDocument,
    DocumentHeader,
    ExtractionStatus,
    Khasra,
    Khatauni,
    Khewat,
    Mutation,
    MutationStatus,
    MutationType,
    Owner,
    Remark,
    RemarkCategory,
    RemarkTarget,
)
from digital_patwari.query import FardQueryEngine
from digital_patwari.reconciliation import reconcile
from digital_patwari.validation import run_axiom_gates


def area(kanal: int, marla: int) -> AreaKanalMarlaSarsahi:
    return AreaKanalMarlaSarsahi(kanal=kanal, marla=marla)


# ---------------------------------------------------------------------
# Khewat 44, Khatauni 53
# ---------------------------------------------------------------------
khatauni_53 = Khatauni(
    khatauni_id="KHT-53", khewat_id="KHW-44",
    raw_cultivator_name="Khudkasht (self-cultivated)",
    recorded_total_area=area(27, 11),
    khasras=[
        Khasra(khasra_id="KHS-44-1", khasra_number="30//16/1", khatauni_id="KHT-53",
               area_kanal_marla=area(1, 17), normalized_irrigation_source="Chahi"),
        Khasra(khasra_id="KHS-44-2", khasra_number="31//17/2", khatauni_id="KHT-53",
               area_kanal_marla=area(1, 16), normalized_irrigation_source="Chahi"),
        Khasra(khasra_id="KHS-44-3", khasra_number="31//18", khatauni_id="KHT-53",
               area_kanal_marla=area(8, 0), normalized_irrigation_source="Chahi"),
        Khasra(khasra_id="KHS-44-4", khasra_number="31//19", khatauni_id="KHT-53",
               area_kanal_marla=area(8, 0), normalized_irrigation_source="Chahi"),
        Khasra(khasra_id="KHS-44-5", khasra_number="31//20", khatauni_id="KHT-53",
               area_kanal_marla=area(7, 18), normalized_irrigation_source="Chahi"),
    ],
)
khewat_44 = Khewat(
    khewat_id="KHW-44", total_share="1/1", raw_total_share="1/1",
    owners=[
        Owner(owner_id="OWN-44-CL", khewat_id="KHW-44",
              raw_owner_name_parentage="Chaman Lal s/o Dharampal s/o Sambhu Nath",
              raw_share_fraction="23/551", share_fraction="23/551"),
        Owner(owner_id="OWN-44-2", khewat_id="KHW-44",
              raw_owner_name_parentage="Raj Rani d/o Ram Parsad",
              raw_share_fraction="5/551", share_fraction="5/551"),
        Owner(owner_id="OWN-44-3", khewat_id="KHW-44",
              raw_owner_name_parentage="Parmjeet Singh s/o Amar Singh s/o Rala Singh",
              raw_share_fraction="523/1653", share_fraction="523/1653"),
        Owner(owner_id="OWN-44-4", khewat_id="KHW-44",
              raw_owner_name_parentage="Gurjeet Singh s/o Amar Singh s/o Rala Singh",
              raw_share_fraction="523/1653", share_fraction="523/1653"),
        Owner(owner_id="OWN-44-5", khewat_id="KHW-44",
              raw_owner_name_parentage="Sujinder/Rajinder Singh s/o Amar Singh s/o Rala Singh",
              raw_share_fraction="523/1653", share_fraction="523/1653"),
    ],
    khataunis=[khatauni_53],
)

# ---------------------------------------------------------------------
# Khewat 217 (modeled standalone -- see caveats in the chat report about
# whether 217/218 are two Khataunis of one Khewat; Chaman Lal only
# appears in 217, and 217's own owner list independently sums to 1/1,
# so this simplification does not affect his figure).
# ---------------------------------------------------------------------
khatauni_217 = Khatauni(
    khatauni_id="KHT-217", khewat_id="KHW-217",
    recorded_total_area=area(0, 8),
    khasras=[
        Khasra(khasra_id="KHS-217-1", khasra_number="23//5/1", khatauni_id="KHT-217",
               area_kanal_marla=area(0, 8), raw_soil_classification="Gair Mumkin",
               normalized_soil_classification="Gair Mumkin (non-cultivable)"),
    ],
)
khewat_217 = Khewat(
    khewat_id="KHW-217", total_share="1/1", raw_total_share="1/1",
    owners=[
        Owner(owner_id="OWN-217-CL", khewat_id="KHW-217",
              raw_owner_name_parentage="Chaman Lal s/o Dharampal s/o Sambhu Nath",
              raw_share_fraction="1/7", share_fraction="1/7"),
        Owner(owner_id="OWN-217-2", khewat_id="KHW-217",
              raw_owner_name_parentage="Charanjeet Kaur w/o Amritjeet Singh s/o Nand Lal",
              raw_share_fraction="1/14", share_fraction="1/14"),
        Owner(owner_id="OWN-217-3", khewat_id="KHW-217",
              raw_owner_name_parentage="Rakesh Kumar s/o Ram Lal s/o Ronak Ram",
              raw_share_fraction="1/14", share_fraction="1/14"),
        Owner(owner_id="OWN-217-4", khewat_id="KHW-217",
              raw_owner_name_parentage="Jaswir Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/70", share_fraction="1/70"),
        Owner(owner_id="OWN-217-5", khewat_id="KHW-217",
              raw_owner_name_parentage="Balkar Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/70", share_fraction="1/70"),
        Owner(owner_id="OWN-217-6", khewat_id="KHW-217",
              raw_owner_name_parentage="Amrik Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/70", share_fraction="1/70"),
        Owner(owner_id="OWN-217-7", khewat_id="KHW-217",
              raw_owner_name_parentage="Sukhwinder Kaur w/o Jaswir Singh s/o Dhera Singh",
              raw_share_fraction="5/14", share_fraction="5/14"),
        Owner(owner_id="OWN-217-8", khewat_id="KHW-217",
              raw_owner_name_parentage="Kulwir Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/70", share_fraction="1/70"),
        Owner(owner_id="OWN-217-9", khewat_id="KHW-217",
              raw_owner_name_parentage="Hardinder Singh s/o Charanjeet Singh s/o Labh Singh",
              raw_share_fraction="1/140", share_fraction="1/140"),
        Owner(owner_id="OWN-217-10", khewat_id="KHW-217",
              raw_owner_name_parentage="Jagwinder Singh s/o Charanjeet Singh s/o Labh Singh",
              raw_share_fraction="1/140", share_fraction="1/140"),
        Owner(owner_id="OWN-217-11", khewat_id="KHW-217",
              raw_owner_name_parentage="Haris Kumar s/o Jeevan Lal s/o Dharampal",
              raw_share_fraction="1/7", share_fraction="1/7"),
        Owner(owner_id="OWN-217-12", khewat_id="KHW-217",
              raw_owner_name_parentage="Manish Kumar s/o Jeevan Lal s/o Dharampal",
              raw_share_fraction="1/7", share_fraction="1/7"),
    ],
    khataunis=[khatauni_217],
)

# ---------------------------------------------------------------------
# Khewat 219 -- CORRECTED: has TWO Khataunis, not one. The first pass at
# this transcription only included Khatauni 219 itself and missed that
# Khatauni "220" (originally misread as a separate Khewat) is its
# second Khatauni -- confirmed by the printed Khewat-level rollup on
# p.11 ("Rakba 23 Kanal 12 Marla", "Jamaan Kitte 6") and by three owners
# (Ashok Kumar, Vipan Kumar, Boj Nath) appearing in BOTH Khataunis with
# different fractions (28/177 in 219, 1/3 in 220).
#
# NOTE: entries OWN-219-15/16 (Haris Kumar 1/2, Manish Kumar 1/2) appear
# as a SECOND, separate line for names that already appear earlier in
# the same owner column with 1/7 each. This may be an OCR duplication
# artifact, or two genuinely distinct legal interests -- I cannot tell
# from the extracted text alone. Transcribed as read and marked
# UNCERTAIN; AG-01 below reports the real sum, not a forced one.
# ---------------------------------------------------------------------
khatauni_219 = Khatauni(
    khatauni_id="KHT-219", khewat_id="KHW-219",
    recorded_total_area=area(11, 17),
    khasras=[
        Khasra(khasra_id="KHS-219-1", khasra_number="18//5/2", khatauni_id="KHT-219",
               area_kanal_marla=area(4, 13), raw_soil_classification="Gair Mumkin"),
        Khasra(khasra_id="KHS-219-2", khasra_number="18//6/1", khatauni_id="KHT-219",
               area_kanal_marla=area(7, 4), raw_soil_classification="Gair Mumkin"),
    ],
)
khatauni_220 = Khatauni(
    khatauni_id="KHT-220", khewat_id="KHW-219",
    recorded_total_area=area(11, 15),
    khasras=[
        Khasra(khasra_id="KHS-220-1", khasra_number="8//25", khatauni_id="KHT-220",
               area_kanal_marla=area(8, 0), normalized_irrigation_source="Chahi"),
        Khasra(khasra_id="KHS-220-2", khasra_number="18//5/1", khatauni_id="KHT-220",
               area_kanal_marla=area(3, 2), raw_soil_classification="Gair Mumkin"),
        Khasra(khasra_id="KHS-220-3", khasra_number="18//5/3", khatauni_id="KHT-220",
               area_kanal_marla=area(0, 5), raw_soil_classification="Gair Mumkin"),
        Khasra(khasra_id="KHS-220-4", khasra_number="18//6/2", khatauni_id="KHT-220",
               area_kanal_marla=area(0, 8), raw_soil_classification="Gair Mumkin"),
    ],
)
khewat_219 = Khewat(
    khewat_id="KHW-219", total_share="1/1", raw_total_share="1/1",
    owners=[
        Owner(owner_id="OWN-219-1", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Boj Nath alias Boj s/o Kapoor Chand s/o Sambhu Nath",
              raw_share_fraction="28/177", share_fraction="28/177"),
        Owner(owner_id="OWN-219-2", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Ashok Kumar s/o Kapoor Chand s/o Sambhu Nath",
              raw_share_fraction="28/177", share_fraction="28/177"),
        Owner(owner_id="OWN-219-CL", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Chaman Lal s/o Dharampal s/o Sambhu Nath",
              raw_share_fraction="209/944", share_fraction="209/944"),
        Owner(owner_id="OWN-219-4", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Rakesh Kumar s/o Ram Lal s/o Ronak Ram",
              raw_share_fraction="27/944", share_fraction="27/944"),
        Owner(owner_id="OWN-219-5", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Jaswir Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/295", share_fraction="1/295"),
        Owner(owner_id="OWN-219-6", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Balkar Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/295", share_fraction="1/295"),
        Owner(owner_id="OWN-219-7", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Amrik Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/295", share_fraction="1/295"),
        Owner(owner_id="OWN-219-8", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Sukhwinder Kaur w/o Jaswir Singh s/o Dhera Singh",
              raw_share_fraction="5/14", share_fraction="5/14"),
        Owner(owner_id="OWN-219-9", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Kulwir Singh s/o Labh Singh s/o Chhota Singh",
              raw_share_fraction="1/295", share_fraction="1/295"),
        Owner(owner_id="OWN-219-10", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Hardinder Singh s/o Charanjeet Singh s/o Labh Singh",
              raw_share_fraction="1/590", share_fraction="1/590"),
        Owner(owner_id="OWN-219-11", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Jagwinder Singh s/o Charanjeet Singh s/o Labh Singh",
              raw_share_fraction="1/590", share_fraction="1/590"),
        Owner(owner_id="OWN-219-12", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Vipan Kumar s/o Kapoor Chand s/o Sambhu Nath",
              raw_share_fraction="28/177", share_fraction="28/177"),
        Owner(owner_id="OWN-219-13", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Haris Kumar s/o Jeevan Lal s/o Dharampal",
              raw_share_fraction="1/7", share_fraction="1/7"),
        Owner(owner_id="OWN-219-14", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Manish Kumar s/o Jeevan Lal s/o Dharampal",
              raw_share_fraction="1/7", share_fraction="1/7"),
        Owner(owner_id="OWN-219-15", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Haris Kumar s/o Jeevan Lal s/o Dharampal (2nd line, duplicate?)",
              raw_share_fraction="1/2", share_fraction="1/2", status=ExtractionStatus.UNCERTAIN),
        Owner(owner_id="OWN-219-16", khewat_id="KHW-219", khatauni_id="KHT-219",
              raw_owner_name_parentage="Manish Kumar s/o Jeevan Lal s/o Dharampal (2nd line, duplicate?)",
              raw_share_fraction="1/2", share_fraction="1/2", status=ExtractionStatus.UNCERTAIN),
        # Second Khatauni under this SAME Khewat -- previously misread as a
        # separate "Khewat 220". Confirmed via the printed Khewat-level
        # rollup on p.11 ("23 Kanal 12 Marla", "Jamaan Kitte 6" = 11-17 +
        # 11-15, 2 parcels + 4 parcels). Chaman Lal holds no share here.
        Owner(owner_id="OWN-220-1", khewat_id="KHW-219", khatauni_id="KHT-220",
              raw_owner_name_parentage="Ashok Kumar s/o Kapoor Chand s/o Sambhu Nath",
              raw_share_fraction="1/3", share_fraction="1/3"),
        Owner(owner_id="OWN-220-2", khewat_id="KHW-219", khatauni_id="KHT-220",
              raw_owner_name_parentage="Vipan Kumar s/o Kapoor Chand s/o Sambhu Nath",
              raw_share_fraction="1/3", share_fraction="1/3"),
        Owner(owner_id="OWN-220-3", khewat_id="KHW-219", khatauni_id="KHT-220",
              raw_owner_name_parentage="Boj Nath alias Boj s/o Kapoor Chand s/o Sambhu Nath",
              raw_share_fraction="1/3", share_fraction="1/3"),
    ],
    khataunis=[khatauni_219, khatauni_220],
)

remarks = [
    Remark(target_type=RemarkTarget.OWNER, target_id="OWN-44-CL",
           remark_category=RemarkCategory.LEGAL_ENCUMBRANCE,
           raw_text="Report No. 212 dated 30/1/2006: attachment (Kurki) re: 'Puri Oil Mill' matter, "
                    "served on the shares of Chaman Lal, Sukhdev Kumar, and Surjeet Kumar.",
           parsed_meaning="Legal attachment on Chaman Lal's share; not a mutation, does not itself transfer ownership."),
    Remark(target_type=RemarkTarget.OWNER, target_id="OWN-217-CL",
           remark_category=RemarkCategory.LEGAL_ENCUMBRANCE,
           raw_text="Report No. 25 -- OCR-uncertain term ('Sahaya'/possibly 'Stay') -- Kumar Chand vs. "
                    "Chaman Lal and Rakesh Kumar's shares. Also: Dina Rani vs. Chaman Lal, same uncertain term.",
           parsed_meaning=None),
]

document = DigitalPatwariDocument(
    document_header=DocumentHeader(
        village="Sanghol", hadbast_number="310", jamabandi_year="2020-21",
        lr_number="LR26-18046550", district="Fatehgarh Sahib", tehsil="Khamano",
    ),
    khewats=[khewat_44, khewat_217, khewat_219],
    remarks=remarks,
    mutations=[],
)


def main() -> None:
    report = run_axiom_gates(document)
    record = reconcile(document, report)
    engine = FardQueryEngine(record)

    print("=== AXIOM GATES ===")
    for gate in report.gates:
        print(f"{gate.gate_id}: passed={gate.passed} checked={gate.checked_entities} skipped={gate.skipped_entities}")
        for issue in gate.issues:
            print(f"    [{issue.severity.value}] {issue.entity_type} {issue.entity_id}: {issue.message}"
                  + (f" expected={issue.expected} actual={issue.actual} diff={issue.difference}" if issue.expected else ""))
    print(f"\nOverall passed: {report.passed}\n")

    # owner_land() disambiguates by name across the WHOLE document, and
    # "Chaman Lal" legitimately matches 3 different Khewats here --
    # correctly ambiguous, refuses to guess which one.
    ambiguous_answer = engine.owner_share("Chaman Lal")
    print("engine.owner_share('Chaman Lal') across the whole document ->")
    print(f"  record_says: {ambiguous_answer.record_says}")
    print(f"  uncertain: {ambiguous_answer.uncertain}")
    print()

    print("=== KHEWAT 219 TOTAL AREA (now correctly includes BOTH Khataunis) ===")
    khw219_total = engine.total_area("KHW-219")
    print(f"  calculated: {khw219_total.calculated}")
    print(f"  (previous, wrong transcription only counted Khatauni 219 alone: 11 kanal 17 marla)")
    print()

    print("=== CHAMAN LAL -- PER KHEWAT, via the FIXED FardQueryEngine.owner_land() ===")
    for khewat in [khewat_44, khewat_217, khewat_219]:
        solo_document = DigitalPatwariDocument(document_header=document.document_header, khewats=[khewat])
        solo_engine = FardQueryEngine(reconcile(solo_document, run_axiom_gates(solo_document)))
        answer = solo_engine.owner_land("Chaman Lal")
        print(f"-- Khewat {khewat.khewat_id} --")
        print(f"  record_says: {answer.record_says}")
        print(f"  calculated: {answer.calculated}")
        print(f"  uncertain: {answer.uncertain}" + (f" ({answer.uncertainty_reason})" if answer.uncertainty_reason else ""))
        print()


if __name__ == "__main__":
    main()
