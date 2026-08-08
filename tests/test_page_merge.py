from digital_patwari.merge import merge_page_documents
from digital_patwari.ownership import resolve_owner_entitlements
from digital_patwari.query import FardQueryEngine
from digital_patwari.reconciliation import reconcile
from digital_patwari.validation import run_axiom_gates
from tests.factories import (
    make_area,
    make_document,
    make_khasra,
    make_khatauni,
    make_khewat,
    make_owner,
    make_remark,
    make_source,
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


def test_remark_on_reprinted_owner_targets_retained_canonical_owner():
    page1_owner = make_owner(
        "page-1-owner",
        "page-1-khewat",
        "1/2",
        raw_owner_name_parentage="Same Owner s/o Same Parent",
    )
    page1 = make_document(
        khewats=[
            make_khewat(
                "page-1-khewat",
                khewat_number="45",
                total_share="1/2",
                owners=[page1_owner],
            )
        ]
    )

    repeated_owner = make_owner(
        "page-2-owner",
        "page-2-khewat",
        "1/2",
        raw_owner_name_parentage="Same Owner s/o Same Parent",
    )
    page2 = make_document(
        khewats=[
            make_khewat(
                "page-2-khewat",
                khewat_number="45",
                total_share="1/2",
                owners=[repeated_owner],
            )
        ],
        remarks=[
            make_remark(
                RemarkTarget.OWNER,
                "page-2-owner",
                RemarkCategory.INFORMATIONAL,
            )
        ],
    )

    document = merge_page_documents([(1, page1), (2, page2)]).document

    assert len(document.khewats[0].owners) == 1
    assert document.remarks[0].target_id == document.khewats[0].owners[0].owner_id
    ag02 = next(gate for gate in run_axiom_gates(document).gates if gate.gate_id == "AG-02")
    assert ag02.passed


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


def test_blank_khewat_cells_continue_198_185_across_khataunis_219_and_220():
    """Catches the real failure where Column 2 value 219 was promoted to a Khewat."""
    page4 = make_document(khewats=[
        make_khewat("page4-khewat", khewat_number="198/185")
    ])

    khatauni_219 = make_khatauni(
        "page5-khatauni", "page5-continuation",
        khatauni_number="219",
        recorded_area=make_area(kanal=11, marla=17),
        khasras=[
            make_khasra("page5-khasra-1", "page5-khatauni", kanal=4, marla=13, khasra_number="18//5/2"),
            make_khasra("page5-khasra-2", "page5-khatauni", kanal=7, marla=4, khasra_number="18//6/1"),
        ],
    )
    chaman_lal = make_owner(
        "page5-chaman", "page5-continuation", "209/944",
        raw_owner_name_parentage="Chaman Lal",
        normalized_owner_name="Chaman Lal",
        khatauni_id=None,
    )
    page5 = make_document(khewats=[
        make_khewat(
            "page5-continuation",
            khewat_number=None,
            continued_from_previous_page=True,
            owners=[chaman_lal],
            khataunis=[khatauni_219],
        )
    ])

    khatauni_220 = make_khatauni(
        "page6-khatauni", "page6-continuation",
        khatauni_number="220",
        recorded_area=make_area(kanal=11, marla=15),
        khasras=[
            make_khasra("page6-khasra-1", "page6-khatauni", kanal=8, marla=0, khasra_number="8//25"),
            make_khasra("page6-khasra-2", "page6-khatauni", kanal=3, marla=2, khasra_number="18//5/1"),
            make_khasra("page6-khasra-3", "page6-khatauni", kanal=0, marla=5, khasra_number="18//5/3"),
            make_khasra("page6-khasra-4", "page6-khatauni", kanal=0, marla=8, khasra_number="18//6/2"),
        ],
    )
    page6 = make_document(khewats=[
        make_khewat(
            "page6-continuation",
            khewat_number=None,
            continued_from_previous_page=True,
            khataunis=[khatauni_220],
        )
    ])

    merged = merge_page_documents([(6, page6), (4, page4), (5, page5)]).document

    assert [k.khewat_number for k in merged.khewats] == ["198/185"]
    khewat = merged.khewats[0]
    assert [k.khatauni_number for k in khewat.khataunis] == ["219", "220"]
    assert [len(k.khasras) for k in khewat.khataunis] == [2, 4]
    assert [(k.recorded_total_area.kanal, k.recorded_total_area.marla) for k in khewat.khataunis] == [
        (11, 17),
        (11, 15),
    ]

    owner = next(o for o in khewat.owners if o.normalized_owner_name == "Chaman Lal")
    assert owner.khatauni_id is None
    [interest] = resolve_owner_entitlements([owner], khewat)
    assert interest.khatauni_ids == tuple(k.khatauni_id for k in khewat.khataunis)
    assert interest.area_sarsahi == 4248
    assert interest.entitlement_sarsahi().numerator == 1881
    assert interest.entitlement_sarsahi().denominator == 2


def test_unresolved_blank_khewat_continuation_is_not_promoted_to_khewat():
    orphan = make_document(khewats=[
        make_khewat(
            "orphan",
            khewat_number=None,
            continued_from_previous_page=True,
            khataunis=[make_khatauni("KHT-1", "orphan", khatauni_number="219")],
        )
    ])

    result = merge_page_documents([(5, orphan)])

    assert result.document.khewats == []
    assert any("no preceding printed Khewat" in warning for warning in result.warnings)


def test_page_documents_out_of_order_are_merged_based_on_page_number():
    page1_khewat = make_khewat(
        "KHW-1",
        khewat_number="198/185",
        owners=[make_owner("OWN-1", "KHW-1", "1/2")],
        khataunis=[
            make_khatauni(
                "KHT-1",
                "KHW-1",
                khatauni_number="219",
                recorded_area=make_area(kanal=11),
                khasras=[
                    make_khasra("KHS-1", "KHT-1", kanal=4),
                    make_khasra("KHS-2", "KHT-1", kanal=7),
                ],
            )
        ],
    )
    page2_khewat = make_khewat(
        "KHW-1",
        khewat_number="198/185",
        khataunis=[
            make_khatauni(
                "KHT-2",
                "KHW-1",
                khatauni_number="220",
                recorded_area=make_area(kanal=11),
                khasras=[
                    make_khasra("KHS-3", "KHT-2", kanal=8),
                    make_khasra("KHS-4", "KHT-2", kanal=3),
                    make_khasra("KHS-5", "KHT-2", marla=5),
                    make_khasra("KHS-6", "KHT-2", marla=8),
                ],
            )
        ],
    )

    page1 = make_document(khewats=[page1_khewat])
    page2 = make_document(khewats=[page2_khewat])

    # Intentionally provide pages out of order to ensure the merge sorts by
    # the embedded page numbers rather than by the input list order.
    merged = merge_page_documents([(2, page2), (1, page1)]).document

    assert len(merged.khewats) == 1
    merged_khewat = merged.khewats[0]
    assert merged_khewat.khewat_number == "198/185"
    assert len(merged_khewat.owners) == 1
    assert [k.khatauni_number for k in merged_khewat.khataunis] == ["219", "220"]


def test_khewat_continuation_with_blank_owner_column_preserves_owner_and_inherits_area():
    page1_khewat = make_khewat(
        "KHW-1",
        khewat_number="198/185",
        owners=[
            make_owner(
                "OWN-1", "KHW-1", "209/944",
                raw_owner_name_parentage="Chaman Lal s/o Dharampal s/o Sambhu Nath",
                source=make_source(page=1, column_ref="3"),
            )
        ],
        khataunis=[
            make_khatauni(
                "KHT-1", "KHW-1", khatauni_number="219",
                recorded_area=make_area(kanal=11, marla=17),
                source=make_source(page=1, column_ref="2"),
                khasras=[
                    make_khasra("KHS-1", "KHT-1", kanal=4, marla=13, khasra_number="18//5/2", source=make_source(page=1, column_ref="6")),
                    make_khasra("KHS-2", "KHT-1", kanal=7, marla=4, khasra_number="18//6/1", source=make_source(page=1, column_ref="6")),
                ],
            )
        ],
    )
    # Page 2's Column 1 is visually blank -- the Khewat continues from page 1
    # rather than reprinting "198/185", matching the real Column-1 blank-cell
    # continuation semantics rather than a repeated explicit Khewat number.
    page2_khewat = make_khewat(
        "KHW-2",
        khewat_number=None,
        continued_from_previous_page=True,
        owners=[],
        khataunis=[
            make_khatauni(
                "KHT-2", "KHW-2", khatauni_number="220",
                recorded_area=make_area(kanal=11, marla=15),
                source=make_source(page=2, column_ref="2"),
                khasras=[
                    make_khasra("KHS-3", "KHT-2", kanal=8, khasra_number="8//25", source=make_source(page=2, column_ref="6")),
                    make_khasra("KHS-4", "KHT-2", kanal=3, marla=2, khasra_number="18//5/1", source=make_source(page=2, column_ref="6")),
                    make_khasra("KHS-5", "KHT-2", marla=5, khasra_number="18//5/3", source=make_source(page=2, column_ref="6")),
                    make_khasra("KHS-6", "KHT-2", marla=8, khasra_number="18//6/2", source=make_source(page=2, column_ref="6")),
                ],
            )
        ],
    )

    page1 = make_document(khewats=[page1_khewat])
    page2 = make_document(khewats=[page2_khewat])
    merged = merge_page_documents([(2, page2), (1, page1)]).document

    assert len(merged.khewats) == 1
    merged_khewat = merged.khewats[0]
    assert merged_khewat.khewat_number == "198/185"
    assert [k.khatauni_number for k in merged_khewat.khataunis] == ["219", "220"]
    assert len(merged_khewat.owners) == 1
    assert merged_khewat.owners[0].raw_owner_name_parentage == "Chaman Lal s/o Dharampal s/o Sambhu Nath"
    assert merged_khewat.owners[0].source.page_number == 1
    assert merged_khewat.khataunis[1].source.page_number == 2

    answer = FardQueryEngine(reconcile(merged, run_axiom_gates(merged))).owner_land("Chaman Lal s/o Dharampal s/o Sambhu Nath")
    assert not answer.uncertain, answer.uncertainty_reason
    assert "5 kanal 4 marla 4 sarsahi" in answer.calculated.lower()
