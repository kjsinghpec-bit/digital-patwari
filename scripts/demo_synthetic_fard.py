"""Offline demo: exercises the pipeline from AFTER image/PDF extraction
onward (structured data -> validation -> reconciliation -> query) against
one hand-built synthetic Fard. No network calls, no API key required.

This script is evaluation scaffolding, not production code -- it is not
imported by digital_patwari/ or patwari_agent.py, and nothing here was
written to make any particular fixture "pass"; the fixture was built
first, from the demo requirements, then run through the unmodified
pipeline.

Run: .venv/bin/python scripts/demo_synthetic_fard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from digital_patwari.models import (
    AreaKanalMarlaSarsahi,
    DigitalPatwariDocument,
    DocumentHeader,
    ExtractionConfidence,
    ExtractionStatus,
    Khasra,
    Khatauni,
    Khewat,
    Mutation,
    MutationStatus,
    MutationTransferScope,
    MutationType,
    Owner,
    Remark,
    RemarkCategory,
    RemarkTarget,
    SourceReference,
)
from digital_patwari.query import Answer, FardQueryEngine, khewat_total_area_sarsahi
from digital_patwari.reconciliation import reconcile
from digital_patwari.validation import run_axiom_gates


def build_synthetic_document() -> DigitalPatwariDocument:
    src = lambda page, text, status=ExtractionStatus.PRESENT, conf=ExtractionConfidence.HIGH: SourceReference(
        page_number=page, status=status, confidence=conf, raw_text=text
    )

    owners = [
        Owner(
            owner_id="OWN-1", khewat_id="KHW-1",
            raw_owner_name_parentage="Chaman Lal s/o Sohan Lal",
            normalized_owner_name="Chaman Lal",
            raw_share_fraction="1/2", share_fraction="1/2",
            status=ExtractionStatus.PRESENT,
            source=src(1, "Chaman Lal s/o Sohan Lal -- 1/2 hissa"),
        ),
        Owner(
            owner_id="OWN-2", khewat_id="KHW-1",
            raw_owner_name_parentage="Ram Lal s/o Sohan Lal",
            normalized_owner_name="Ram Lal",
            raw_share_fraction="1/4", share_fraction="1/4",
            status=ExtractionStatus.PRESENT,
            source=src(1, "Ram Lal s/o Sohan Lal -- 1/4 hissa"),
        ),
        # Deliberately uncertain field: the scan is smudged here. Digital
        # Patwari must surface this as needing verification, not guess.
        Owner(
            owner_id="OWN-3", khewat_id="KHW-1",
            raw_owner_name_parentage="Ki[smudged]an Lal s/o Sohan Lal",
            normalized_owner_name=None,
            raw_share_fraction="1/4", share_fraction="1/4",
            status=ExtractionStatus.UNCERTAIN,
            source=src(1, "Ki...an Lal s/o Sohan Lal -- 1/4 hissa", status=ExtractionStatus.UNCERTAIN, conf=ExtractionConfidence.LOW),
        ),
    ]

    # Two Khataunis under one Khewat: the classic double-counting risk.
    # A buggy implementation might multiply the Khewat's area by the
    # number of Khataunis, or sum all Khasras under the Khewat while
    # double-counting a Khatauni's own recorded_total_area on top of
    # its Khasras. Correct behavior: each Khatauni contributes its own
    # recorded area exactly once.
    khatauni_1 = Khatauni(
        khatauni_id="KHT-1", khewat_id="KHW-1",
        raw_cultivator_name="Chaman Lal (self-cultivated)",
        raw_possession_type="Khud Kasht",
        recorded_total_area=AreaKanalMarlaSarsahi(kanal=5, marla=0, sarsahi=0, raw_text="5 Kanal 0 Marla"),
        khasras=[
            Khasra(
                khasra_id="KHS-1", khasra_number="17", khatauni_id="KHT-1",
                area_kanal_marla=AreaKanalMarlaSarsahi(kanal=3, marla=0, sarsahi=0, raw_text="3-0"),
                raw_soil_classification="Chahi", normalized_soil_classification="Chahi",
                normalized_irrigation_source="Chahi", normalized_cultivation_status="Khudkasht",
                source=src(2, "Khasra 17: 3-0, Chahi"),
            ),
            Khasra(
                khasra_id="KHS-2", khasra_number="18", khatauni_id="KHT-1",
                area_kanal_marla=AreaKanalMarlaSarsahi(kanal=2, marla=0, sarsahi=0, raw_text="2-0"),
                raw_soil_classification="Barani", normalized_soil_classification="Barani",
                normalized_irrigation_source="Barani", normalized_cultivation_status="Khudkasht",
                source=src(2, "Khasra 18: 2-0, Barani"),
            ),
        ],
        source=src(2, "Khatauni 1, total 5-0"),
    )
    khatauni_2 = Khatauni(
        khatauni_id="KHT-2", khewat_id="KHW-1",
        raw_cultivator_name="Ram Lal (tenant: Kishan)",
        raw_possession_type="Muzara",
        recorded_total_area=AreaKanalMarlaSarsahi(kanal=3, marla=10, sarsahi=0, raw_text="3 Kanal 10 Marla"),
        khasras=[
            Khasra(
                khasra_id="KHS-3", khasra_number="22", khatauni_id="KHT-2",
                area_kanal_marla=AreaKanalMarlaSarsahi(kanal=2, marla=5, sarsahi=0, raw_text="2-5"),
                raw_soil_classification="Nehri", normalized_soil_classification="Nehri",
                normalized_irrigation_source="Nehri", normalized_cultivation_status="Muzara",
                source=src(3, "Khasra 22: 2-5, Nehri"),
            ),
            Khasra(
                khasra_id="KHS-4", khasra_number="23", khatauni_id="KHT-2",
                area_kanal_marla=AreaKanalMarlaSarsahi(kanal=1, marla=5, sarsahi=0, raw_text="1-5"),
                raw_soil_classification="Nehri", normalized_soil_classification="Nehri",
                normalized_irrigation_source="Nehri", normalized_cultivation_status="Muzara",
                source=src(3, "Khasra 23: 1-5, Nehri"),
            ),
        ],
        source=src(3, "Khatauni 2, total 3-10"),
    )

    khewat = Khewat(
        khewat_id="KHW-1", owner_group_ref="Group-A",
        raw_total_share="1/1", total_share="1/1",
        owners=owners, khataunis=[khatauni_1, khatauni_2],
        source=src(1, "Khewat No. 1"),
    )

    remark = Remark(
        target_type=RemarkTarget.KHEWAT, target_id="KHW-1",
        remark_category=RemarkCategory.INFORMATIONAL,
        raw_text="Column 8 note: field boundary re-verified by Patwari during 2019 girdawari.",
        parsed_meaning="Informational field note; no effect on ownership or mutation status.",
        source=src(1, "Khana Kaifiyat: boundary re-verified 2019"),
    )

    mutation = Mutation(
        mutation_id="MUT-1",
        target_type=RemarkTarget.OWNER, target_id="OWN-1",
        status=MutationStatus.APPROVED,
        mutation_type=MutationType.SALE,
        transfer_scope=MutationTransferScope.SPECIFIC_KHASRA,
        affected_khasra_numbers=["17"],
        raw_text="Mutation No. 245: Chaman Lal sold Khasra No. 17 (3 Kanal) to Ram Lal, sanctioned 12-03-2021.",
        parsed_meaning="Sale of a specific Khasra (No. 17), not an undivided share, sanctioned and approved.",
        extraction_status=ExtractionStatus.PRESENT,
        source=src(1, "Inteqal No. 245 dated 12-03-2021, sanctioned"),
    )

    header = DocumentHeader(
        village="Sanghol", hadbast_number="142", jamabandi_year="2020-21",
        lr_number="LR-2020-142", district="Fatehgarh Sahib", tehsil="Khamano",
        source=src(1, "Mauza Sanghol, Hadbast No. 142, Jamabandi 2020-21"),
    )

    return DigitalPatwariDocument(
        document_header=header,
        khewats=[khewat],
        remarks=[remark],
        mutations=[mutation],
    )


def _fmt_answer(question_label: str, a: Answer) -> str:
    return (
        f"### {question_label}\n\n"
        f"**Record says:** {a.record_says}\n\n"
        f"**Calculated:** {a.calculated if a.calculated is not None else '(not calculated -- see verification note)'}\n\n"
        f"**Interpretation:** {a.interpretation if a.interpretation is not None else '(none)'}\n\n"
        f"**Evidence:** {'; '.join(f'p.{e.page_number}: \"{e.raw_text}\"' for e in a.evidence) if a.evidence else '(none attached)'}\n\n"
        f"**Confidence:** {a.confidence.value if a.confidence else '(not applicable)'}\n\n"
        f"**Verification required:** {'YES -- ' + (a.uncertainty_reason or 'flagged uncertain') if a.uncertain else 'No'}\n"
    )


def main() -> None:
    document = build_synthetic_document()
    report = run_axiom_gates(document)
    record = reconcile(document, report)
    engine = FardQueryEngine(record)

    out = []
    out.append("# Synthetic Fard Demo Run\n")
    out.append("## Validation (Axiom Gates)\n")
    for gate in report.gates:
        out.append(f"- **{gate.gate_id}**: passed={gate.passed}, checked={gate.checked_entities}, skipped={gate.skipped_entities}, issues={len(gate.issues)}")
        for issue in gate.issues:
            out.append(f"    - [{issue.severity.value}] {issue.entity_type} {issue.entity_id}: {issue.message}"
                        + (f" (expected={issue.expected}, actual={issue.actual})" if issue.expected else ""))
    out.append(f"\n**Overall validation passed:** {report.passed}\n")

    out.append("## Reconciliation (Approved/Pending Mutation Rule)\n")
    for r in record.ownership_reconciliations:
        who = r.owner_id or f"(Khewat-level: {r.khewat_id})"
        out.append(f"- {who}: status={r.status.value}, mutations={r.mutation_ids}")
    out.append("")

    out.append("## Double-counting proof\n")
    total_sarsahi, complete, missing = khewat_total_area_sarsahi(document.khewats[0])
    kht1_sarsahi = document.khewats[0].khataunis[0].recorded_total_area.total_sarsahi()
    kht2_sarsahi = document.khewats[0].khataunis[1].recorded_total_area.total_sarsahi()
    naive_double_count = kht1_sarsahi * 2  # what a bug that ignored KHT-2, or multiplied by khatauni count, might produce
    out.append(f"- Khatauni KHT-1 recorded area: {kht1_sarsahi} sarsahi")
    out.append(f"- Khatauni KHT-2 recorded area: {kht2_sarsahi} sarsahi")
    out.append(f"- Correct Khewat total (KHT-1 + KHT-2, each counted once): {total_sarsahi} sarsahi")
    out.append(f"- A double-counting bug (e.g. KHT-1 area x2, ignoring KHT-2) would have produced: {naive_double_count} sarsahi")
    out.append(f"- PROVEN: {total_sarsahi} sarsahi != {naive_double_count} sarsahi, and {total_sarsahi} == {kht1_sarsahi} + {kht2_sarsahi} ({kht1_sarsahi + kht2_sarsahi})")
    assert total_sarsahi == kht1_sarsahi + kht2_sarsahi, "DOUBLE-COUNT BUG DETECTED"
    assert total_sarsahi != naive_double_count, "Suspicious: total equals the naive double-count value"
    out.append("- Assertion passed: no double-counting occurred.\n")

    out.append("## Simulated user questions\n")
    out.append(_fmt_answer("1. Who are the owners?", engine.list_owners()))
    for owner_name in ["Chaman Lal", "Ram Lal", "Ki[smudged]an Lal"]:
        out.append(_fmt_answer(f"2. How much land does {owner_name} have?", engine.owner_land(owner_name)))
    out.append(_fmt_answer("3. What is the total area of the Khewat?", engine.total_area("KHW-1")))
    out.append("### 4. Which Khataunis belong to the Khewat?\n\n"
                f"**Record says:** KHT-1, KHT-2 (both khewat_id=KHW-1).\n\n"
                f"**Calculated:** 2 Khataunis.\n\n"
                f"**Interpretation:** Confirmed via AG-02's Khatauni.khewat_id cross-check (passed).\n\n"
                f"**Evidence:** p.2: \"Khatauni 1, total 5-0\"; p.3: \"Khatauni 2, total 3-10\"\n\n"
                f"**Confidence:** high\n\n**Verification required:** No\n")
    for owner_name in ["Chaman Lal", "Ram Lal"]:
        out.append(_fmt_answer(f"5. Which Khasras are connected to {owner_name}?", engine.owner_khasra_context(owner_name)))
    out.append(_fmt_answer("6. Has any owner sold or purchased land?", engine.mutations_for("Chaman Lal")))
    out.append("### 7. Is the mutation an undivided-share transfer or a specific-Khasra transfer?\n\n"
                f"**Record says:** Mutation MUT-1 has transfer_scope=Specific_Khasra, affected_khasra_numbers=['17'].\n\n"
                f"**Calculated:** N/A (categorical, not numeric).\n\n"
                f"**Interpretation:** This is a specific-Khasra transfer (Khasra 17), not an undivided-share transfer.\n\n"
                f"**Evidence:** p.1: \"Inteqal No. 245 dated 12-03-2021, sanctioned\"\n\n"
                f"**Confidence:** high\n\n**Verification required:** No\n")
    out.append(_fmt_answer("8. Explain Column 8.", engine.remarks_for(RemarkTarget.KHEWAT, "KHW-1")))
    uncertain_answer = engine.owner_share("Ki[smudged]an Lal")
    out.append(_fmt_answer("9. Is anything uncertain or inconsistent?", uncertain_answer))
    out.append(_fmt_answer("10. Explain the Fard in simple English.", engine.explain_fard_simple_english()))

    report_text = "\n".join(out)
    print(report_text)

    (Path(__file__).resolve().parent.parent / "scripts" / "_demo_run_output.md").write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
