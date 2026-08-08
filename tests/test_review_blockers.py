from digital_patwari.extraction import DocumentStatus, FardExtractionParser
from digital_patwari.observations import FieldObservation, PageObservation
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
)


class SequentialProvider:
    cache_identity = "offline-review-provider"

    def __init__(self, observations):
        self.observations = list(observations)

    def extract_structured(self, **kwargs):
        return self.observations.pop(0).model_dump(mode="json")


def field(observation_id, path, raw_text, page, column):
    return FieldObservation(
        observation_id=observation_id,
        field_path=path,
        entity_type="review-regression",
        extracted_value=raw_text,
        raw_text=raw_text,
        confidence="low",
        page_number=page,
        column_ref=column,
        evidence_region=f"page-{page}-column-{column}",
        verification_status="NEEDS_REVIEW",
        verification_reason="INVALID_FORMAT",
        uncertainty_reason="The printed value could not be normalized safely.",
    )


def extract_observations(monkeypatch, observations):
    parts = [
        {
            "page_number": observation.page_number,
            "filename": f"page-{observation.page_number}.png",
            "mime_type": "image/png",
            "base64_data": f"cGFnZS0{observation.page_number}",
        }
        for observation in observations
    ]
    monkeypatch.setattr("digital_patwari.extraction.load_document_parts", lambda paths: parts)
    return FardExtractionParser(
        provider=SequentialProvider(observations), batch_size=1, max_page_retries=0,
    ).extract(["offline-placeholder"])


def test_malformed_khewat_total_keeps_198_185_anchor_owner_and_continuation(monkeypatch):
    owner = make_owner(
        "P4-OWNER", "P4-KHEWAT", "209/944",
        raw_owner_name_parentage="Chaman Lal",
        normalized_owner_name="Chaman Lal",
    )
    page4_document = make_document(khewats=[make_khewat(
        "P4-KHEWAT", khewat_number="198/185", owners=[owner],
    )])
    page4_payload = page4_document.model_dump(mode="json")
    page4_payload["khewats"][0]["raw_total_share"] = "garbled!!"
    page4_payload["khewats"][0]["total_share"] = "garbled!!"
    page4 = PageObservation(
        page_number=4,
        fields=[field("p4-total", ["khewats", 0, "total_share"], "garbled!!", 4, "3")],
        canonical_payload=page4_payload,
    )

    page5_document = make_document(khewats=[make_khewat(
        "P5-CONTINUATION", khewat_number=None, continued_from_previous_page=True,
        khataunis=[make_khatauni("P5-KHT", "P5-CONTINUATION", khatauni_number="219")],
    )])
    page5 = PageObservation(page_number=5, canonical_payload=page5_document.model_dump(mode="json"))

    result = extract_observations(monkeypatch, [page4, page5])

    assert result.status == DocumentStatus.PARTIAL
    assert len(result.document.khewats) == 1
    khewat = result.document.khewats[0]
    assert khewat.khewat_number == "198/185"
    assert khewat.raw_total_share == "garbled!!"
    assert khewat.total_share is None
    assert khewat.owners[0].raw_owner_name_parentage == "Chaman Lal"
    assert [khatauni.khatauni_number for khatauni in khewat.khataunis] == ["219"]
    assert result.observations[0].fields[0].raw_text == "garbled!!"
    assert any(issue.reason.value == "INVALID_FORMAT" for issue in result.verification_issues)
    ag01 = next(gate for gate in result.validation_report.gates if gate.gate_id == "AG-01")
    assert any("Khewat total share needs verification" in issue.message for issue in ag01.issues)


def test_malformed_khatauni_total_preserves_row_and_siblings(monkeypatch):
    document = make_document(khewats=[make_khewat(
        "KHW-1", khewat_number="10",
        owners=[make_owner("OWN-1", "KHW-1", "1/1", khatauni_id="KHT-1")],
        khataunis=[
            make_khatauni("KHT-1", "KHW-1", khatauni_number="219"),
            make_khatauni("KHT-2", "KHW-1", khatauni_number="220"),
        ],
    )])
    payload = document.model_dump(mode="json")
    payload["khewats"][0]["khataunis"][0]["raw_total_share"] = "bad-total"
    payload["khewats"][0]["khataunis"][0]["total_share"] = "bad-total"
    observation = PageObservation(
        page_number=1,
        fields=[field(
            "kht-total", ["khewats", 0, "khataunis", 0, "total_share"], "bad-total", 1, "3",
        )],
        canonical_payload=payload,
    )

    result = extract_observations(monkeypatch, [observation])

    assert result.status == DocumentStatus.PARTIAL
    assert [k.khatauni_number for k in result.document.khewats[0].khataunis] == ["219", "220"]
    assert result.document.khewats[0].khataunis[0].total_share is None
    assert result.document.khewats[0].khataunis[0].raw_total_share == "bad-total"
    ag01 = next(gate for gate in result.validation_report.gates if gate.gate_id == "AG-01")
    assert any("Khatauni total share needs verification" in issue.message for issue in ag01.issues)


def test_non_numeric_area_component_preserves_khasra_and_withholds_area_check(monkeypatch):
    khasra = make_khasra("KHS-1", "KHT-1", kanal=4, marla=5)
    document = make_document(khewats=[make_khewat(
        "KHW-1", khewat_number="10",
        khataunis=[make_khatauni(
            "KHT-1", "KHW-1", khatauni_number="219",
            recorded_area=make_area(kanal=4, marla=5), khasras=[khasra],
        )],
    )])
    payload = document.model_dump(mode="json")
    area = payload["khewats"][0]["khataunis"][0]["khasras"][0]["area_kanal_marla"]
    area["kanal"] = "not-a-number"
    area["raw_text"] = "not-a-number-5"
    observation = PageObservation(
        page_number=1,
        fields=[field(
            "khasra-kanal",
            ["khewats", 0, "khataunis", 0, "khasras", 0, "area_kanal_marla", "kanal"],
            "not-a-number", 1, "7",
        )],
        canonical_payload=payload,
    )

    result = extract_observations(monkeypatch, [observation])

    assert result.status == DocumentStatus.PARTIAL
    kept = result.document.khewats[0].khataunis[0].khasras[0]
    assert kept.khasra_id == "KHS-1"
    assert kept.area_kanal_marla.kanal is None
    assert kept.area_kanal_marla.raw_text == "not-a-number-5"
    assert kept.area_kanal_marla.total_sarsahi() is None
    ag03 = next(gate for gate in result.validation_report.gates if gate.gate_id == "AG-03")
    assert ag03.skipped_entities == 1


def test_owner_total_across_khewats_abstains_for_unresolved_shares():
    name = "Chaman Lal s/o Parent"
    khewats = []
    for index in (1, 2):
        owner = make_owner(
            f"OWN-{index}", f"KHW-{index}", "1/2",
            raw_owner_name_parentage=name,
        ).model_copy(update={"raw_share_fraction": "unresolved", "share_fraction": None, "status": "uncertain"})
        khewats.append(make_khewat(
            f"KHW-{index}", owners=[owner],
            khataunis=[make_khatauni(
                f"KHT-{index}", f"KHW-{index}", recorded_area=make_area(kanal=5),
            )],
        ))
    document = make_document(khewats=khewats)
    engine = FardQueryEngine(reconcile(document, run_axiom_gates(document)))

    answer = engine.owner_total_across_khewats("Chaman Lal")

    assert answer.uncertain
    assert answer.calculated is None
    assert "share" in answer.uncertainty_reason.lower()
    assert "needs verification" in answer.record_says.lower()

