from digital_patwari.merge import merge_page_documents
from tests.factories import (
    make_area,
    make_document,
    make_khatauni,
    make_khewat,
    make_owner,
    make_remark,
)
from patwari_agent import RemarkCategory, RemarkTarget


def test_khewat_spanning_two_pages_merges_owners_and_khataunis():
    # Page 1: Khewat "45" with an owner, no Khataunis yet.
    page1_khewat = make_khewat(
        "KHW-1",
        khewat_number="45",
        owners=[make_owner("OWN-1", "KHW-1", "1/2")],
    )
    page1 = make_document(khewats=[page1_khewat])

    # Page 2: the SAME real Khewat "45" continues, now with a Khatauni.
    # Its page-local IDs (KHW-1) collide with page 1's by coincidence.
    page2_khatauni = make_khatauni("KHT-1", "KHW-1", khatauni_number="12")
    page2_khewat = make_khewat(
        "KHW-1",
        khewat_number="45",
        khataunis=[page2_khatauni],
    )
    page2 = make_document(khewats=[page2_khewat])

    result = merge_page_documents([(1, page1), (2, page2)])
    document = result.document

    assert len(document.khewats) == 1
    merged = document.khewats[0]
    assert merged.khewat_number == "45"
    assert len(merged.owners) == 1
    assert len(merged.khataunis) == 1
    assert merged.khataunis[0].khatauni_number == "12"
    # Khatauni's foreign key points at the regenerated Khewat id.
    assert merged.khataunis[0].khewat_id == merged.khewat_id


def test_owner_reprinted_on_continuation_page_is_not_double_counted():
    owner = make_owner("OWN-1", "KHW-1", "1/2")
    page1 = make_document(khewats=[make_khewat("KHW-1", khewat_number="45", owners=[owner])])
    # Page 2 reprints the same owner row verbatim, as continuation pages do.
    reprinted_owner = make_owner("OWN-1", "KHW-1", "1/2")
    page2 = make_document(khewats=[make_khewat("KHW-1", khewat_number="45", owners=[reprinted_owner])])

    result = merge_page_documents([(1, page1), (2, page2)])
    merged = result.document.khewats[0]

    assert len(merged.owners) == 1


def test_remark_target_id_rewritten_to_regenerated_khewat_id():
    khewat = make_khewat("KHW-1", khewat_number="45")
    remark = make_remark(RemarkTarget.KHEWAT, "KHW-1", RemarkCategory.INFORMATIONAL)
    page1 = make_document(khewats=[khewat], remarks=[remark])

    result = merge_page_documents([(1, page1)])
    document = result.document

    assert document.remarks[0].target_id == document.khewats[0].khewat_id


def test_khatauni_total_from_later_page_is_not_lost_during_merge():
    page1 = make_document(
        khewats=[
            make_khewat(
                "KHW-1",
                khewat_number="45",
                khataunis=[make_khatauni("KHT-1", "KHW-1", khatauni_number="12", recorded_area=make_area(kanal=0))],
            )
        ]
    )
    page2 = make_document(
        khewats=[
            make_khewat(
                "KHW-1",
                khewat_number="45",
                khataunis=[make_khatauni("KHT-1", "KHW-1", khatauni_number="12", recorded_area=make_area(kanal=5))],
            )
        ]
    )

    merged = merge_page_documents([(1, page1), (2, page2)]).document
    assert len(merged.khewats) == 1
    assert len(merged.khewats[0].khataunis) == 1
    assert merged.khewats[0].khataunis[0].recorded_total_area.kanal == 5


def test_final_page_khatauni_is_preserved_when_a_khewat_continues_across_pages():
    page1 = make_document(
        khewats=[
            make_khewat(
                "KHW-1",
                khewat_number="45",
                owners=[make_owner("OWN-1", "KHW-1", "1/2")],
                khataunis=[make_khatauni("KHT-1", "KHW-1", khatauni_number="12")],
            )
        ]
    )
    page2 = make_document(
        khewats=[
            make_khewat(
                "KHW-1",
                khewat_number="45",
                khataunis=[make_khatauni("KHT-2", "KHW-1", khatauni_number="13", recorded_area=make_area(kanal=7))],
            )
        ]
    )

    merged = merge_page_documents([(1, page1), (2, page2)]).document
    assert len(merged.khewats) == 1
    assert len(merged.khewats[0].khataunis) == 2
    assert merged.khewats[0].khataunis[1].khatauni_number == "13"


def test_document_header_disagreement_across_pages_is_a_warning_not_a_crash():
    page1 = make_document(khewats=[], village="Village A")
    page2 = make_document(khewats=[], village="Village B")

    result = merge_page_documents([(1, page1), (2, page2)])

    assert result.document.document_header.village == "Village A"
    assert any("document_header" in warning for warning in result.warnings)
