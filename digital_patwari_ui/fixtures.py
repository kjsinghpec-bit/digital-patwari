"""Representative synthetic Fard fixtures for the beta UI.

Nothing here is a real land record. The village, Hadbast, owners, Khewats,
Khataunis, Khasras, mutations and remarks are invented, and every rendered
page is stamped "SYNTHETIC SAMPLE".

These fixtures are NOT a replacement backend. Each scenario is a set of
``PageObservation`` objects served by ``FixtureProvider``, which satisfies
``digital_patwari.extraction.ExtractionProvider`` and never touches the
network. The observations then flow through the real
``FardExtractionParser`` -> ``assemble_page_observations`` -> merge ->
``run_axiom_gates`` -> ``reconcile`` pipeline, so the statuses, warnings,
gate results and verification questions the UI displays are produced by the
production engines, not authored by hand.
"""
from __future__ import annotations

import base64
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any

from digital_patwari.extraction import DocumentStatus
from digital_patwari.observations import (
    FieldObservation,
    PageCellObservation,
    PageObservation,
    VerificationIssue,
    VerificationReason,
    VerificationStatus,
)
from digital_patwari_ui.page_render import (
    Cell,
    PageSpec,
    Row,
    compute_regions,
    region_key,
    render_page_svg,
)

HEADER = {
    "village": "ਨਾਨਕਪੁਰਾ / Nanakpura (sample)",
    "hadbast_number": "412",
    "jamabandi_year": "2018-2019",
    "lr_number": "SYN/2018/0007",
    "district": "Sample District",
    "tehsil": "Sample Tehsil",
}

TOTAL_PAGES = 3


def _header_payload(page: int) -> dict[str, Any]:
    return {
        **HEADER,
        "source": {
            "page_number": page,
            "total_pages": TOTAL_PAGES,
            "column_ref": "header",
            "status": "present",
            "confidence": "high",
            "raw_text": f"ਜਮ੍ਹਾਂਬੰਦੀ ਸਾਲ 2018-2019 — ਪਿੰਡ ਨਾਨਕਪੁਰਾ, ਹਦਬਸਤ 412 (ਸਫ਼ਾ {page}/{TOTAL_PAGES})",
        },
    }


def _source(page: int, column_ref: str, raw_text: str, *, status: str = "present", confidence: str = "high") -> dict[str, Any]:
    return {
        "page_number": page,
        "total_pages": TOTAL_PAGES,
        "column_ref": column_ref,
        "status": status,
        "confidence": confidence,
        "raw_text": raw_text,
    }


def _area(kanal: int, marla: int, sarsahi: int, raw_text: str) -> dict[str, Any]:
    return {"kanal": kanal, "marla": marla, "sarsahi": sarsahi, "raw_text": raw_text}


# =====================================================================
# EVIDENCE ENTRIES
#
# One entry per visible cell we also extract a value from. Cells and
# FieldObservations are generated from these so the printed text, the
# highlight region and the extracted value can never drift apart.
# =====================================================================


@dataclass(frozen=True)
class Evidence:
    row_id: str
    col: int
    lines: tuple[str, ...]
    raw_text: str
    field_path: tuple[str | int, ...]
    entity_type: str
    entity_id: str | None
    extracted_value: Any
    confidence: str = "high"
    status: str = "present"
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED
    verification_reason: VerificationReason | None = None
    uncertainty_reason: str | None = None
    faint: bool = False
    blank: bool = False


@dataclass(frozen=True)
class PageFixture:
    page_number: int
    spec: PageSpec
    evidence: tuple[Evidence, ...]
    canonical_payload: dict[str, Any]
    issues: tuple[VerificationIssue, ...] = ()
    extra_cells: tuple[PageCellObservation, ...] = ()

    def observation(self) -> PageObservation:
        regions = compute_regions(self.spec)
        cells: list[PageCellObservation] = []
        fields: list[FieldObservation] = []
        for index, item in enumerate(self.evidence, start=1):
            cells.append(PageCellObservation(
                column_ref=str(item.col),
                raw_text="" if item.blank else item.raw_text,
                is_blank=item.blank,
                row_ref=item.row_id,
                region=regions.get(region_key(item.row_id, item.col)),
                status=item.status,
                confidence=item.confidence,
                uncertainty=item.uncertainty_reason,
            ))
            fields.append(FieldObservation(
                observation_id=f"p{self.page_number}-f{index}",
                field_path=list(item.field_path),
                entity_type=item.entity_type,
                entity_id=item.entity_id,
                extracted_value=item.extracted_value,
                raw_text=item.raw_text,
                confidence=item.confidence,
                page_number=self.page_number,
                column_ref=str(item.col),
                evidence_region=regions.get(region_key(item.row_id, item.col)),
                verification_status=item.verification_status,
                verification_reason=item.verification_reason,
                uncertainty_reason=item.uncertainty_reason,
            ))
        return PageObservation(
            page_number=self.page_number,
            cells=cells + list(self.extra_cells),
            fields=fields,
            verification_issues=list(self.issues),
            canonical_payload=self.canonical_payload,
        )

    def svg(self) -> str:
        return render_page_svg(self.spec)


def _spec_from_evidence(page_number: int, evidence: tuple[Evidence, ...], row_heights: dict[str, int], *, unreadable: bool = False) -> PageSpec:
    by_row: dict[str, list[Cell]] = {}
    order: list[str] = []
    for item in evidence:
        if item.row_id not in by_row:
            by_row[item.row_id] = []
            order.append(item.row_id)
        by_row[item.row_id].append(Cell(col=item.col, lines=item.lines, blank=item.blank, faint=item.faint))
    return PageSpec(
        page_number=page_number,
        total_pages=TOTAL_PAGES,
        title_lines=(
            "ਜ਼ਿਲ੍ਹਾ ਮਾਲ ਰਿਕਾਰਡ — ਜਮ੍ਹਾਂਬੰਦੀ / Jamabandi 2018-2019",
            f"ਪਿੰਡ ਨਾਨਕਪੁਰਾ (sample) · ਹਦਬਸਤ 412 · {HEADER['tehsil']}, {HEADER['district']}",
        ),
        rows=tuple(Row(row_id, tuple(by_row[row_id]), row_heights.get(row_id, 84)) for row_id in order),
        footer=f"ਸਫ਼ਾ {page_number} / {TOTAL_PAGES}   ·   Page {page_number} of {TOTAL_PAGES}",
        unreadable=unreadable,
    )


# =====================================================================
# PAGE 1 — Khewat 45/40, Khatauni 101
# =====================================================================

_PAGE1_EVIDENCE: tuple[Evidence, ...] = (
    Evidence("o1", 1, ("45/40",), "45/40", ("khewats", 0, "khewat_number"), "Khewat", "KHW-1", "45/40"),
    Evidence("o1", 2, ("101",), "101", ("khewats", 0, "khataunis", 0, "khatauni_number"), "Khatauni", "KHT-1", "101"),
    Evidence("o1", 3, ("ਜਸਵੀਰ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ", "Jasvir Singh s/o Gurdev Singh — 1/2"),
             "ਜਸਵੀਰ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ 1/2 ਹਿੱਸਾ",
             ("khewats", 0, "owners", 0), "Owner", "OWN-1", "Jasvir Singh s/o Gurdev Singh"),
    Evidence("o1", 4, ("ਖੁਦਕਾਸ਼ਤ", "Khud Kasht"), "ਖੁਦਕਾਸ਼ਤ",
             ("cultivation_interests", 0, "raw_relationship_text"), "CultivationInterest", "CUL-1", "khud_kasht"),
    Evidence("o1", 5, ("ਨਹਿਰੀ", "Nehri"), "ਨਹਿਰੀ",
             ("khewats", 0, "khataunis", 0, "khasras", 0, "normalized_irrigation_source"), "Khasra", "KHS-1", "Nehri"),
    Evidence("o1", 6, ("31 // 18",), "31 // 18",
             ("khewats", 0, "khataunis", 0, "khasras", 0, "khasra_number"), "Khasra", "KHS-1", "18"),
    Evidence("o1", 7, ("5-0-0",), "5-0-0",
             ("khewats", 0, "khataunis", 0, "khasras", 0, "area_kanal_marla"), "Khasra", "KHS-1", "5 kanal 0 marla 0 sarsahi"),
    Evidence("o1", 8, ("—",), "", ("khewats", 0, "source"), "Khewat", "KHW-1", None, blank=True),

    Evidence("o2", 3, ("ਹਰਬੰਸ ਕੌਰ ਪਤਨੀ ਗੁਰਦੇਵ ਸਿੰਘ", "Harbans Kaur w/o Gurdev Singh — 1/4"),
             "ਹਰਬੰਸ ਕੌਰ ਪਤਨੀ ਗੁਰਦੇਵ ਸਿੰਘ 1/4 ਹਿੱਸਾ",
             ("khewats", 0, "owners", 1), "Owner", "OWN-2", "Harbans Kaur w/o Gurdev Singh"),
    Evidence("o2", 6, ("31 // 19",), "31 // 19",
             ("khewats", 0, "khataunis", 0, "khasras", 1, "khasra_number"), "Khasra", "KHS-2", "19"),
    Evidence("o2", 7, ("3-0-0",), "3-0-0",
             ("khewats", 0, "khataunis", 0, "khasras", 1, "area_kanal_marla"), "Khasra", "KHS-2", "3 kanal 0 marla 0 sarsahi"),

    Evidence("o3", 3, ("ਬਲਵੰਤ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ", "Balwant Singh s/o Gurdev Singh — 1/4"),
             "ਬਲਵੰਤ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ 1/4 ਹਿੱਸਾ",
             ("khewats", 0, "owners", 2), "Owner", "OWN-3", "Balwant Singh s/o Gurdev Singh"),

    Evidence("tot", 7, ("ਜੋੜ ਖਤੌਨੀ 8-0-0",), "ਜੋੜ ਖਤੌਨੀ 8-0-0",
             ("khewats", 0, "khataunis", 0, "recorded_total_area"), "Khatauni", "KHT-1", "8 kanal 0 marla 0 sarsahi"),
)

_PAGE1_OWNERS = [
    {
        "owner_id": "OWN-1", "khewat_id": "KHW-1",
        "raw_owner_name_parentage": "ਜਸਵੀਰ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ",
        "normalized_owner_name": "Jasvir Singh s/o Gurdev Singh",
        "raw_share_fraction": "1/2", "share_fraction": "1/2",
        "source": _source(1, "3", "ਜਸਵੀਰ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ 1/2 ਹਿੱਸਾ"),
    },
    {
        "owner_id": "OWN-2", "khewat_id": "KHW-1",
        "raw_owner_name_parentage": "ਹਰਬੰਸ ਕੌਰ ਪਤਨੀ ਗੁਰਦੇਵ ਸਿੰਘ",
        "normalized_owner_name": "Harbans Kaur w/o Gurdev Singh",
        "raw_share_fraction": "1/4", "share_fraction": "1/4",
        "source": _source(1, "3", "ਹਰਬੰਸ ਕੌਰ ਪਤਨੀ ਗੁਰਦੇਵ ਸਿੰਘ 1/4 ਹਿੱਸਾ"),
    },
    {
        "owner_id": "OWN-3", "khewat_id": "KHW-1",
        "raw_owner_name_parentage": "ਬਲਵੰਤ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ",
        "normalized_owner_name": "Balwant Singh s/o Gurdev Singh",
        "raw_share_fraction": "1/4", "share_fraction": "1/4",
        "source": _source(1, "3", "ਬਲਵੰਤ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ 1/4 ਹਿੱਸਾ"),
    },
]


def _page1_payload() -> dict[str, Any]:
    return {
        "document_header": _header_payload(1),
        "layout": "modern_8_column",
        "khewats": [{
            "khewat_id": "KHW-1",
            "khewat_number": "45/40",
            "continued_from_previous_page": False,
            "raw_total_share": "1/1", "total_share": "1/1",
            "owners": _PAGE1_OWNERS,
            "khataunis": [{
                "khatauni_id": "KHT-1",
                "khatauni_number": "101",
                "khewat_id": "KHW-1",
                "raw_cultivator_name": "ਜਸਵੀਰ ਸਿੰਘ",
                "raw_possession_type": "ਖੁਦਕਾਸ਼ਤ",
                "recorded_total_area": _area(8, 0, 0, "ਜੋੜ ਖਤੌਨੀ 8-0-0"),
                "khasras": [
                    {
                        "khasra_id": "KHS-1", "khasra_number": "18", "murabba_number": "31",
                        "khatauni_id": "KHT-1",
                        "area_kanal_marla": _area(5, 0, 0, "5-0-0"),
                        "raw_soil_classification": "ਨਹਿਰੀ",
                        "normalized_irrigation_source": "Nehri",
                        "source": _source(1, "6", "31 // 18"),
                    },
                    {
                        "khasra_id": "KHS-2", "khasra_number": "19", "murabba_number": "31",
                        "khatauni_id": "KHT-1",
                        "area_kanal_marla": _area(3, 0, 0, "3-0-0"),
                        "raw_soil_classification": "ਨਹਿਰੀ",
                        "normalized_irrigation_source": "Nehri",
                        "source": _source(1, "6", "31 // 19"),
                    },
                ],
                "source": _source(1, "2", "101"),
            }],
            "source": _source(1, "1", "45/40"),
        }],
        "cultivation_interests": [{
            "cultivation_interest_id": "CUL-1",
            "person_name": "ਜਸਵੀਰ ਸਿੰਘ",
            "khewat_id": "KHW-1",
            "khatauni_id": "KHT-1",
            "relationship": "khud_kasht",
            "raw_relationship_text": "ਖੁਦਕਾਸ਼ਤ",
            "source": _source(1, "4", "ਖੁਦਕਾਸ਼ਤ"),
        }],
        "area_observations": [{
            "observation_id": "AO-1-1", "scope": "khatauni_subtotal",
            "area": _area(8, 0, 0, "ਜੋੜ ਖਤੌਨੀ 8-0-0"),
            "khewat_id": "KHW-1", "khatauni_id": "KHT-1",
            "source": _source(1, "7", "ਜੋੜ ਖਤੌਨੀ 8-0-0"),
        }],
    }


PAGE_1 = PageFixture(
    page_number=1,
    spec=_spec_from_evidence(1, _PAGE1_EVIDENCE, {"o1": 96, "o2": 90, "o3": 90, "tot": 70}),
    evidence=_PAGE1_EVIDENCE,
    canonical_payload=_page1_payload(),
)


# =====================================================================
# PAGE 2 — Column 1 BLANK: Khewat 45/40 continues, Khatauni 102
# =====================================================================

_PAGE2_EVIDENCE: tuple[Evidence, ...] = (
    Evidence("o1", 1, ("",), "", ("khewats", 0, "khewat_number"), "Khewat", "KHW-1", None, blank=True,
             uncertainty_reason="Column 1 is a blank ruled cell continuing from the previous page."),
    Evidence("o1", 2, ("102",), "102", ("khewats", 0, "khataunis", 0, "khatauni_number"), "Khatauni", "KHT-1", "102"),
    Evidence("o1", 3, ("ਜਸਵੀਰ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ", "Jasvir Singh s/o Gurdev Singh — 1/2"),
             "ਜਸਵੀਰ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ 1/2 ਹਿੱਸਾ",
             ("khewats", 0, "owners", 0), "Owner", "OWN-1", "Jasvir Singh s/o Gurdev Singh"),
    Evidence("o1", 4, ("ਮੁਜ਼ਾਰਾ", "Muzara — Sohan Singh"), "ਮੁਜ਼ਾਰਾ ਸੋਹਣ ਸਿੰਘ",
             ("cultivation_interests", 0, "raw_relationship_text"), "CultivationInterest", "CUL-2", "muzara"),
    Evidence("o1", 5, ("ਬਰਾਨੀ", "Barani"), "ਬਰਾਨੀ",
             ("khewats", 0, "khataunis", 0, "khasras", 0, "normalized_irrigation_source"), "Khasra", "KHS-1", "Barani"),
    Evidence("o1", 6, ("31 // 20",), "31 // 20",
             ("khewats", 0, "khataunis", 0, "khasras", 0, "khasra_number"), "Khasra", "KHS-1", "20"),
    Evidence("o1", 7, ("4-0-0",), "4-0-0",
             ("khewats", 0, "khataunis", 0, "khasras", 0, "area_kanal_marla"), "Khasra", "KHS-1", "4 kanal 0 marla 0 sarsahi"),
    Evidence("o1", 8, ("ਇੰਤਕਾਲ ਨੰ: 1187", "ਦਰਜ, ਮਨਜ਼ੂਰ ਨਹੀਂ"), "ਇੰਤਕਾਲ ਨੰ: 1187 ਦਰਜ — ਮਨਜ਼ੂਰ ਨਹੀਂ ਹੋਇਆ",
             ("mutations", 0), "Mutation", "MUT-1187", "Pending"),

    Evidence("o2", 3, ("ਹਰਬੰਸ ਕੌਰ ਪਤਨੀ ਗੁਰਦੇਵ ਸਿੰਘ", "Harbans Kaur w/o Gurdev Singh — 1/4"),
             "ਹਰਬੰਸ ਕੌਰ ਪਤਨੀ ਗੁਰਦੇਵ ਸਿੰਘ 1/4 ਹਿੱਸਾ",
             ("khewats", 0, "owners", 1), "Owner", "OWN-2", "Harbans Kaur w/o Gurdev Singh"),
    Evidence("o2", 6, ("31 // 21",), "31 // 21",
             ("khewats", 0, "khataunis", 0, "khasras", 1, "khasra_number"), "Khasra", "KHS-2", "21"),
    Evidence("o2", 7, ("2-10-0",), "2-10-0",
             ("khewats", 0, "khataunis", 0, "khasras", 1, "area_kanal_marla"), "Khasra", "KHS-2", "2 kanal 10 marla 0 sarsahi"),

    Evidence("o3", 3, ("ਬਲਵੰਤ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ", "Balwant Singh s/o Gurdev Singh — 1/4"),
             "ਬਲਵੰਤ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ 1/4 ਹਿੱਸਾ",
             ("khewats", 0, "owners", 2), "Owner", "OWN-3", "Balwant Singh s/o Gurdev Singh"),

    Evidence("tot", 7, ("ਜੋੜ ਖਤੌਨੀ 6-10-0",), "ਜੋੜ ਖਤੌਨੀ 6-10-0",
             ("khewats", 0, "khataunis", 0, "recorded_total_area"), "Khatauni", "KHT-1", "6 kanal 10 marla 0 sarsahi"),
)


def _page2_payload() -> dict[str, Any]:
    owners = []
    for owner in _PAGE1_OWNERS:
        copied = dict(owner)
        copied["source"] = _source(2, "3", owner["source"]["raw_text"])
        owners.append(copied)
    return {
        "document_header": _header_payload(2),
        "layout": "modern_8_column",
        "khewats": [{
            "khewat_id": "KHW-1",
            "khewat_number": None,
            "continued_from_previous_page": True,
            "raw_total_share": "1/1", "total_share": "1/1",
            "owners": owners,
            "khataunis": [{
                "khatauni_id": "KHT-1",
                "khatauni_number": "102",
                "khewat_id": "KHW-1",
                "raw_cultivator_name": "ਸੋਹਣ ਸਿੰਘ",
                "raw_possession_type": "ਮੁਜ਼ਾਰਾ",
                "recorded_total_area": _area(6, 10, 0, "ਜੋੜ ਖਤੌਨੀ 6-10-0"),
                "khasras": [
                    {
                        "khasra_id": "KHS-1", "khasra_number": "20", "murabba_number": "31",
                        "khatauni_id": "KHT-1",
                        "area_kanal_marla": _area(4, 0, 0, "4-0-0"),
                        "raw_soil_classification": "ਬਰਾਨੀ",
                        "normalized_irrigation_source": "Barani",
                        "source": _source(2, "6", "31 // 20"),
                    },
                    {
                        "khasra_id": "KHS-2", "khasra_number": "21", "murabba_number": "31",
                        "khatauni_id": "KHT-1",
                        "area_kanal_marla": _area(2, 10, 0, "2-10-0"),
                        "raw_soil_classification": "ਬਰਾਨੀ",
                        "normalized_irrigation_source": "Barani",
                        "source": _source(2, "6", "31 // 21"),
                    },
                ],
                "source": _source(2, "2", "102"),
            }],
            "source": _source(2, "1", ""),
        }],
        "mutations": [{
            "mutation_id": "MUT-1187",
            "target_type": "Khewat", "target_id": "KHW-1",
            "status": "Pending",
            "mutation_type": "Sale",
            "mutation_date": "12-03-2019",
            "transferor_name": "ਬਲਵੰਤ ਸਿੰਘ ਪੁੱਤਰ ਗੁਰਦੇਵ ਸਿੰਘ",
            "transferee_name": "ਰਣਜੀਤ ਸਿੰਘ ਪੁੱਤਰ ਮੱਖਣ ਸਿੰਘ",
            "sanction_wording": "ਦਰਜ — ਮਨਜ਼ੂਰ ਨਹੀਂ ਹੋਇਆ",
            "raw_text": "ਇੰਤਕਾਲ ਨੰ: 1187 ਦਰਜ — ਮਨਜ਼ੂਰ ਨਹੀਂ ਹੋਇਆ",
            "parsed_meaning": "Mutation 1187 is entered but not sanctioned.",
            "source": _source(2, "8", "ਇੰਤਕਾਲ ਨੰ: 1187 ਦਰਜ — ਮਨਜ਼ੂਰ ਨਹੀਂ ਹੋਇਆ"),
        }],
        "remarks": [{
            "target_type": "Khewat", "target_id": "KHW-1",
            "remark_category": "Pending_Mutation",
            "raw_text": "ਇੰਤਕਾਲ ਨੰ: 1187 ਦਰਜ — ਮਨਜ਼ੂਰ ਨਹੀਂ ਹੋਇਆ",
            "parsed_meaning": "A sale mutation has been entered against this Khewat but has not been sanctioned.",
            "source": _source(2, "8", "ਇੰਤਕਾਲ ਨੰ: 1187 ਦਰਜ — ਮਨਜ਼ੂਰ ਨਹੀਂ ਹੋਇਆ"),
        }],
        "cultivation_interests": [{
            "cultivation_interest_id": "CUL-2",
            "person_name": "ਸੋਹਣ ਸਿੰਘ",
            "khewat_id": "KHW-1",
            "khatauni_id": "KHT-1",
            "relationship": "muzara",
            "raw_relationship_text": "ਮੁਜ਼ਾਰਾ ਸੋਹਣ ਸਿੰਘ",
            "source": _source(2, "4", "ਮੁਜ਼ਾਰਾ ਸੋਹਣ ਸਿੰਘ"),
        }],
        "area_observations": [{
            "observation_id": "AO-2-1", "scope": "khatauni_subtotal",
            "area": _area(6, 10, 0, "ਜੋੜ ਖਤੌਨੀ 6-10-0"),
            "khewat_id": "KHW-1", "khatauni_id": "KHT-1",
            "source": _source(2, "7", "ਜੋੜ ਖਤੌਨੀ 6-10-0"),
        }],
    }


PAGE_2 = PageFixture(
    page_number=2,
    spec=_spec_from_evidence(2, _PAGE2_EVIDENCE, {"o1": 110, "o2": 90, "o3": 90, "tot": 70}),
    evidence=_PAGE2_EVIDENCE,
    canonical_payload=_page2_payload(),
)


# =====================================================================
# PAGE 3 — Khewat 77, Khatauni 210, with a mortgage entry
# =====================================================================

def _page3_evidence(*, smudged_share: bool = False) -> tuple[Evidence, ...]:
    kartar_share_lines = ("ਕਰਤਾਰ ਸਿੰਘ ਪੁੱਤਰ ਮੇਹਰ ਸਿੰਘ", "Kartar Singh s/o Mehar Singh — 3/4")
    kartar_raw = "ਕਰਤਾਰ ਸਿੰਘ ਪੁੱਤਰ ਮੇਹਰ ਸਿੰਘ 3/4 ਹਿੱਸਾ"
    kartar_value: Any = "3/4"
    kartar_conf = "high"
    kartar_status = "present"
    kartar_verification = VerificationStatus.NOT_REQUIRED
    kartar_reason: VerificationReason | None = None
    kartar_uncertainty = None
    if smudged_share:
        kartar_share_lines = ("ਕਰਤਾਰ ਸਿੰਘ ਪੁੱਤਰ ਮੇਹਰ ਸਿੰਘ", "Kartar Singh s/o Mehar Singh — ?/4")
        kartar_raw = "ਕਰਤਾਰ ਸਿੰਘ ਪੁੱਤਰ ਮੇਹਰ ਸਿੰਘ ੩/੪ ਹਿੱਸਾ"
        kartar_value = None
        kartar_conf = "low"
        kartar_status = "uncertain"
        kartar_verification = VerificationStatus.NEEDS_REVIEW
        kartar_reason = VerificationReason.UNREADABLE
        kartar_uncertainty = "The numerator of the share is smudged; it could be read as 3/4 or 1/4."

    return (
        Evidence("o1", 1, ("77",), "77", ("khewats", 0, "khewat_number"), "Khewat", "KHW-1", "77"),
        Evidence("o1", 2, ("210",), "210", ("khewats", 0, "khataunis", 0, "khatauni_number"), "Khatauni", "KHT-1", "210"),
        Evidence("o1", 3, kartar_share_lines, kartar_raw,
                 ("khewats", 0, "owners", 0, "share_fraction"), "Owner", "OWN-1", kartar_value,
                 confidence=kartar_conf, status=kartar_status,
                 verification_status=kartar_verification, verification_reason=kartar_reason,
                 uncertainty_reason=kartar_uncertainty, faint=smudged_share),
        Evidence("o1", 4, ("ਮਕਬੂਜ਼ਾ ਮਾਲਕਾਨ", "Maqbuza Malkan"), "ਮਕਬੂਜ਼ਾ ਮਾਲਕਾਨ",
                 ("cultivation_interests", 0, "raw_relationship_text"), "CultivationInterest", "CUL-3", "maqbuza_malkan"),
        Evidence("o1", 5, ("ਚਾਹੀ", "Chahi"), "ਚਾਹੀ",
                 ("khewats", 0, "khataunis", 0, "khasras", 0, "normalized_irrigation_source"), "Khasra", "KHS-1", "Chahi"),
        Evidence("o1", 6, ("44 // 7",), "44 // 7",
                 ("khewats", 0, "khataunis", 0, "khasras", 0, "khasra_number"), "Khasra", "KHS-1", "7"),
        Evidence("o1", 7, ("7-0-0",), "7-0-0",
                 ("khewats", 0, "khataunis", 0, "khasras", 0, "area_kanal_marla"), "Khasra", "KHS-1", "7 kanal 0 marla 0 sarsahi"),
        Evidence("o1", 8, ("ਰਹਿਨ ਬਵਜਾ ਬੈਂਕ", "Rehin — mortgage entry"), "ਰਹਿਨ ਬਵਜਾ ਬੈਂਕ, ਇੰਤਕਾਲ ਨੰ: 2201 ਦਰਜ",
                 ("mutations", 0), "Mutation", "MUT-2201", "Entered"),

        Evidence("o2", 3, ("ਨਿਰਮਲ ਕੌਰ ਪਤਨੀ ਕਰਤਾਰ ਸਿੰਘ", "Nirmal Kaur w/o Kartar Singh — 1/4"),
                 "ਨਿਰਮਲ ਕੌਰ ਪਤਨੀ ਕਰਤਾਰ ਸਿੰਘ 1/4 ਹਿੱਸਾ",
                 ("khewats", 0, "owners", 1), "Owner", "OWN-2", "Nirmal Kaur w/o Kartar Singh"),
        Evidence("o2", 6, ("44 // 8",), "44 // 8",
                 ("khewats", 0, "khataunis", 0, "khasras", 1, "khasra_number"), "Khasra", "KHS-2", "8"),
        Evidence("o2", 7, ("5-0-0",), "5-0-0",
                 ("khewats", 0, "khataunis", 0, "khasras", 1, "area_kanal_marla"), "Khasra", "KHS-2", "5 kanal 0 marla 0 sarsahi"),

        Evidence("tot", 7, ("ਜੋੜ ਖਤੌਨੀ 12-0-0",), "ਜੋੜ ਖਤੌਨੀ 12-0-0",
                 ("khewats", 0, "khataunis", 0, "recorded_total_area"), "Khatauni", "KHT-1", "12 kanal 0 marla 0 sarsahi"),
    )


def _page3_payload(*, smudged_share: bool = False, area_mismatch: bool = False) -> dict[str, Any]:
    kartar: dict[str, Any] = {
        "owner_id": "OWN-1", "khewat_id": "KHW-1",
        "raw_owner_name_parentage": "ਕਰਤਾਰ ਸਿੰਘ ਪੁੱਤਰ ਮੇਹਰ ਸਿੰਘ",
        "normalized_owner_name": "Kartar Singh s/o Mehar Singh",
        "raw_share_fraction": "3/4", "share_fraction": "3/4",
        "source": _source(3, "3", "ਕਰਤਾਰ ਸਿੰਘ ਪੁੱਤਰ ਮੇਹਰ ਸਿੰਘ 3/4 ਹਿੱਸਾ"),
    }
    if smudged_share:
        kartar["raw_share_fraction"] = "੩/੪"
        kartar["share_fraction"] = None
        kartar["status"] = "uncertain"
        kartar["source"] = _source(
            3, "3", "ਕਰਤਾਰ ਸਿੰਘ ਪੁੱਤਰ ਮੇਹਰ ਸਿੰਘ ੩/੪ ਹਿੱਸਾ",
            status="uncertain", confidence="low",
        )

    # The area-mismatch variant reproduces a real defect: the printed
    # Khatauni total does not equal the sum of its own Khasra rows. AG-03
    # is what reports it -- the UI never decides which figure is right.
    second_khasra_area = _area(4, 19, 0, "4-19-0") if area_mismatch else _area(5, 0, 0, "5-0-0")

    return {
        "document_header": _header_payload(3),
        "layout": "modern_8_column",
        "khewats": [{
            "khewat_id": "KHW-1",
            "khewat_number": "77",
            "continued_from_previous_page": False,
            "raw_total_share": "1/1", "total_share": "1/1",
            "owners": [kartar, {
                "owner_id": "OWN-2", "khewat_id": "KHW-1",
                "raw_owner_name_parentage": "ਨਿਰਮਲ ਕੌਰ ਪਤਨੀ ਕਰਤਾਰ ਸਿੰਘ",
                "normalized_owner_name": "Nirmal Kaur w/o Kartar Singh",
                "raw_share_fraction": "1/4", "share_fraction": "1/4",
                "source": _source(3, "3", "ਨਿਰਮਲ ਕੌਰ ਪਤਨੀ ਕਰਤਾਰ ਸਿੰਘ 1/4 ਹਿੱਸਾ"),
            }],
            "khataunis": [{
                "khatauni_id": "KHT-1",
                "khatauni_number": "210",
                "khewat_id": "KHW-1",
                "raw_cultivator_name": "ਮਾਲਕਾਨ",
                "raw_possession_type": "ਮਕਬੂਜ਼ਾ ਮਾਲਕਾਨ",
                "recorded_total_area": _area(12, 0, 0, "ਜੋੜ ਖਤੌਨੀ 12-0-0"),
                "khasras": [
                    {
                        "khasra_id": "KHS-1", "khasra_number": "7", "murabba_number": "44",
                        "khatauni_id": "KHT-1",
                        "area_kanal_marla": _area(7, 0, 0, "7-0-0"),
                        "raw_soil_classification": "ਚਾਹੀ",
                        "normalized_irrigation_source": "Chahi",
                        "source": _source(3, "6", "44 // 7"),
                    },
                    {
                        "khasra_id": "KHS-2", "khasra_number": "8", "murabba_number": "44",
                        "khatauni_id": "KHT-1",
                        "area_kanal_marla": second_khasra_area,
                        "raw_soil_classification": "ਚਾਹੀ",
                        "normalized_irrigation_source": "Chahi",
                        "source": _source(3, "6", "44 // 8"),
                    },
                ],
                "source": _source(3, "2", "210"),
            }],
            "source": _source(3, "1", "77"),
        }],
        "mutations": [{
            "mutation_id": "MUT-2201",
            "target_type": "Khewat", "target_id": "KHW-1",
            "status": "Entered",
            "mutation_type": "Mortgage",
            "mutation_date": "04-08-2018",
            "sanction_wording": "ਦਰਜ",
            "raw_text": "ਰਹਿਨ ਬਵਜਾ ਬੈਂਕ, ਇੰਤਕਾਲ ਨੰ: 2201 ਦਰਜ",
            "parsed_meaning": "A mortgage (Rehin) in favour of a bank is entered against this Khewat.",
            "source": _source(3, "8", "ਰਹਿਨ ਬਵਜਾ ਬੈਂਕ, ਇੰਤਕਾਲ ਨੰ: 2201 ਦਰਜ"),
        }],
        "remarks": [{
            "target_type": "Khewat", "target_id": "KHW-1",
            "remark_category": "Legal_Encumbrance",
            "raw_text": "ਰਹਿਨ ਬਵਜਾ ਬੈਂਕ, ਇੰਤਕਾਲ ਨੰ: 2201 ਦਰਜ",
            "parsed_meaning": "A bank mortgage is recorded against this Khewat.",
            "source": _source(3, "8", "ਰਹਿਨ ਬਵਜਾ ਬੈਂਕ, ਇੰਤਕਾਲ ਨੰ: 2201 ਦਰਜ"),
        }],
        "cultivation_interests": [{
            "cultivation_interest_id": "CUL-3",
            "person_name": "ਮਾਲਕਾਨ",
            "khewat_id": "KHW-1",
            "khatauni_id": "KHT-1",
            "relationship": "maqbuza_malkan",
            "raw_relationship_text": "ਮਕਬੂਜ਼ਾ ਮਾਲਕਾਨ",
            "source": _source(3, "4", "ਮਕਬੂਜ਼ਾ ਮਾਲਕਾਨ"),
        }],
        "area_observations": [{
            "observation_id": "AO-3-1", "scope": "khatauni_subtotal",
            "area": _area(12, 0, 0, "ਜੋੜ ਖਤੌਨੀ 12-0-0"),
            "khewat_id": "KHW-1", "khatauni_id": "KHT-1",
            "source": _source(3, "7", "ਜੋੜ ਖਤੌਨੀ 12-0-0"),
        }],
    }


_PAGE3_ROW_HEIGHTS = {"o1": 110, "o2": 90, "tot": 70}


def _page3(*, smudged_share: bool = False, area_mismatch: bool = False) -> PageFixture:
    evidence = _page3_evidence(smudged_share=smudged_share)
    issues: tuple[VerificationIssue, ...] = ()
    if smudged_share:
        issues = (VerificationIssue(
            issue_id="verify-p3-kartar-share",
            field_observation_id="p3-f3",
            page_number=3,
            field_path=["khewats", 0, "owners", 0, "share_fraction"],
            reason=VerificationReason.UNREADABLE,
            question="We could not read this share clearly. Is the printed value 3/4?",
            proposed_value="3/4",
            alternatives=["1/4", "2/4"],
            depends_on=(
                "Kartar Singh's recorded share, the land area calculated from it, and whether "
                "Khewat 77's shares add up to a whole all depend on this value."
            ),
            critical=True,
        ),)
    return PageFixture(
        page_number=3,
        spec=_spec_from_evidence(3, evidence, _PAGE3_ROW_HEIGHTS),
        evidence=evidence,
        canonical_payload=_page3_payload(smudged_share=smudged_share, area_mismatch=area_mismatch),
        issues=issues,
    )


PAGE_3 = _page3()


# =====================================================================
# SCENARIOS
# =====================================================================


@dataclass(frozen=True)
class FixtureScenario:
    key: str
    label: str
    description: str
    expected_status: DocumentStatus
    pages: tuple[PageFixture, ...]
    failing_pages: frozenset[int] = frozenset()
    #: Pages the citizen supplied at all. A page missing from here was never
    #: uploaded; a page in `failing_pages` was uploaded but could not be read.
    uploaded_pages: tuple[int, ...] = (1, 2, 3)

    def page(self, page_number: int) -> PageFixture | None:
        for page in self.pages:
            if page.page_number == page_number:
                return page
        return None


SCENARIOS: dict[str, FixtureScenario] = {}


def _register(scenario: FixtureScenario) -> FixtureScenario:
    SCENARIOS[scenario.key] = scenario
    return scenario


COMPLETE = _register(FixtureScenario(
    key="complete",
    label="All three pages read cleanly",
    description=(
        "A three-page Fard where every page was read, the Khewat continuing across "
        "pages 1 and 2 was joined correctly, and every check passed."
    ),
    expected_status=DocumentStatus.COMPLETE,
    pages=(PAGE_1, PAGE_2, PAGE_3),
))

WARNING = _register(FixtureScenario(
    key="warning",
    label="Read, but the printed area does not add up",
    description=(
        "Every page was read, but on page 3 the printed Khatauni total does not equal "
        "the sum of its own Khasra rows. Digital Patwari reports the disagreement; it "
        "does not pick a winner."
    ),
    expected_status=DocumentStatus.COMPLETE_WITH_WARNINGS,
    pages=(PAGE_1, PAGE_2, _page3(area_mismatch=True)),
))

NEEDS_REVIEW = _register(FixtureScenario(
    key="needs_review",
    label="A share could not be read — your help is needed",
    description=(
        "A smudged share fraction on page 3 could not be read with confidence. The "
        "reading is held back for human verification instead of being guessed."
    ),
    expected_status=DocumentStatus.PARTIAL,
    pages=(PAGE_1, PAGE_2, _page3(smudged_share=True)),
))

PAGE_FAILURE = _register(FixtureScenario(
    key="partial",
    label="One page could not be processed",
    description=(
        "Pages 1 and 2 were read. Page 3 could not be processed. The pages that were "
        "read are shown, and page 3's contents are reported as unknown — never as absent."
    ),
    expected_status=DocumentStatus.PARTIAL,
    pages=(PAGE_1, PAGE_2, PAGE_3),
    failing_pages=frozenset({3}),
))

FAILED = _register(FixtureScenario(
    key="failed",
    label="Nothing could be read",
    description=(
        "No page could be processed. There is no result to show, and no part of the "
        "document may be treated as read."
    ),
    expected_status=DocumentStatus.FAILED,
    pages=(PAGE_1, PAGE_2, PAGE_3),
    failing_pages=frozenset({1, 2, 3}),
))

DEFAULT_SCENARIO_KEY = "complete"


# =====================================================================
# PROVIDER
# =====================================================================


class FixtureProviderError(RuntimeError):
    """Raised for a page the scenario declares unreadable."""


class FixtureProvider:
    """An ``ExtractionProvider`` that serves canned page observations.

    It makes no network call and reads no pixel data. It exists so the UI
    can exercise the real extraction/assembly/validation pipeline offline.
    """

    model_name = "fixture-provider"
    cache_identity = "digital-patwari-ui-fixture-v1"

    def __init__(self, scenario: FixtureScenario) -> None:
        self.scenario = scenario
        self.calls: list[int] = []

    def extract_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        document_parts: list[dict[str, Any]],
        json_schema: Any,
    ) -> dict[str, Any]:
        if len(document_parts) != 1:
            raise FixtureProviderError(
                f"expected exactly one page per request, received {len(document_parts)}"
            )
        page_number = int(document_parts[0]["page_number"])
        self.calls.append(page_number)
        if page_number in self.scenario.failing_pages:
            raise FixtureProviderError(
                "the reading service could not process this page"
            )
        page = self.scenario.page(page_number)
        if page is None:
            raise FixtureProviderError(f"no fixture observation for page {page_number}")
        return page.observation().model_dump(mode="json")


# =====================================================================
# UPLOADED-PAGE STAND-INS
#
# `digital_patwari.document_io` loads real files from disk, so a fixture
# session needs a real supported file per page. The FixtureProvider never
# decodes these bytes; the human-visible rendering of the same synthetic
# page is the SVG from `page_render`, which is what the evidence viewer
# displays. Keeping the placeholder valid (rather than arbitrary bytes)
# means document_io's real MIME handling is exercised, not bypassed.
# =====================================================================


def blank_page_png(width: int = 64, height: int = 90, rgb: tuple[int, int, int] = (251, 250, 246)) -> bytes:
    """A valid, minimal PNG of a solid colour. No external dependency."""

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = bytes([0]) + bytes(rgb) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height, 9))
        + chunk(b"IEND", b"")
    )


def page_svg_data_uri(page: PageFixture) -> str:
    encoded = base64.b64encode(page.svg().encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
