import pytest

from digital_patwari.assembly import assemble_page_observation, assemble_page_observations
from digital_patwari.observations import PageCellObservation, PageObservation
from patwari_agent import EvidenceProvenance, ExtractionConfidence, ExtractionStatus
from tests.factories import make_document, make_khatauni, make_khewat


def observation(page, document, cells=None):
    return PageObservation(
        page_number=page,
        cells=cells or [],
        canonical_payload=document.model_dump(mode="json"),
    )


def test_literal_cell_preserves_page_column_blank_provenance_and_uncertainty():
    cell = PageCellObservation(
        column_ref="1",
        row_ref="row-7",
        raw_text="",
        is_blank=True,
        status=ExtractionStatus.UNCERTAIN,
        confidence=ExtractionConfidence.LOW,
        provenance=EvidenceProvenance.USER_CORRECTED,
        uncertainty="ruled cell is blank; continuation supported by geometry",
    )
    page = observation(5, make_document(), [cell])

    assert page.page_number == 5
    assert page.cells[0].raw_text == ""
    assert page.cells[0].is_blank
    assert page.cells[0].column_ref == "1"
    assert page.cells[0].provenance == EvidenceProvenance.USER_CORRECTED
    assert page.cells[0].uncertainty.startswith("ruled cell")


def test_explicit_blank_cell_cannot_hide_nonblank_raw_text():
    with pytest.raises(ValueError):
        PageCellObservation(column_ref="1", raw_text="219", is_blank=True)


def test_assembler_resolves_blank_khewat_198_185_to_khataunis_219_and_220():
    page4 = observation(4, make_document(khewats=[make_khewat("p4", khewat_number="198/185")]))
    page5 = observation(5, make_document(khewats=[make_khewat(
        "p5", khewat_number=None, continued_from_previous_page=True,
        khataunis=[make_khatauni("p5-kht", "p5", khatauni_number="219")],
    )]))
    page6 = observation(6, make_document(khewats=[make_khewat(
        "p6", khewat_number=None, continued_from_previous_page=True,
        khataunis=[make_khatauni("p6-kht", "p6", khatauni_number="220")],
    )]))

    result = assemble_page_observations([page6, page4, page5])

    assert result.errors == []
    assert [k.khewat_number for k in result.document.khewats] == ["198/185"]
    assert [k.khatauni_number for k in result.document.khewats[0].khataunis] == ["219", "220"]


def test_malformed_owner_fraction_is_preserved_and_warned_without_losing_page():
    payload = make_document(khewats=[make_khewat("p1", khewat_number="9")]).model_dump(mode="json")
    payload["khewats"][0]["owners"] = [{
        "owner_id": "bad-owner",
        "khewat_id": "p1",
        "raw_owner_name_parentage": "Visible Owner",
        "raw_share_fraction": "1//??",
        "share_fraction": "1//??",
    }]
    page = PageObservation(
        page_number=1,
        cells=[PageCellObservation(column_ref="3", raw_text="Visible Owner 1//??", status="uncertain")],
        canonical_payload=payload,
    )

    result = assemble_page_observation(page)

    assert result.document is not None
    assert len(result.document.khewats[0].owners) == 1
    assert result.document.khewats[0].owners[0].raw_share_fraction == "1//??"
    assert result.document.khewats[0].owners[0].share_fraction is None
    assert any("retained row" in warning for warning in result.warnings)
    assert page.canonical_payload["khewats"][0]["owners"][0]["raw_share_fraction"] == "1//??"
    assert page.cells[0].raw_text == "Visible Owner 1//??"
