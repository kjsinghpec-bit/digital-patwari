import json
from pathlib import Path

from digital_patwari.merge import main


def test_merge_cli_merges_json_files_in_directory(tmp_path):
    page1 = tmp_path / "page1.json"
    page2 = tmp_path / "page2.json"

    page1.write_text(json.dumps({
        "document_header": {
            "village": "Village A",
            "hadbast_number": "1",
            "jamabandi_year": "2020-21",
            "lr_number": "LR-1",
        },
        "layout": "modern_8_column",
        "khewats": [
            {
                "khewat_id": "KHW-1",
                "khewat_number": "45",
                "owners": [
                    {
                        "owner_id": "OWN-1",
                        "khewat_id": "KHW-1",
                        "raw_owner_name_parentage": "Owner 1 s/o Father",
                        "raw_share_fraction": "1/2",
                        "share_fraction": "1/2",
                    }
                ],
                "khataunis": [],
            }
        ],
        "remarks": [],
        "mutations": [],
        "parcel_interests": [],
        "cultivation_interests": [],
        "area_observations": [],
    }), encoding="utf-8")

    page2.write_text(json.dumps({
        "document_header": {
            "village": "Village A",
            "hadbast_number": "1",
            "jamabandi_year": "2020-21",
            "lr_number": "LR-1",
        },
        "layout": "modern_8_column",
        "khewats": [
            {
                "khewat_id": "KHW-1",
                "khewat_number": "45",
                "owners": [],
                "khataunis": [
                    {
                        "khatauni_id": "KHT-1",
                        "khatauni_number": "12",
                        "khewat_id": "KHW-1",
                        "khasras": [],
                    }
                ],
            }
        ],
        "remarks": [],
        "mutations": [],
        "parcel_interests": [],
        "cultivation_interests": [],
        "area_observations": [],
    }), encoding="utf-8")

    output_path = tmp_path / "digital_patwari_document.json"
    assert not output_path.exists()

    result = main([str(tmp_path)])

    assert result == 0
    assert output_path.exists()

    merged = json.loads(output_path.read_text(encoding="utf-8"))
    assert merged["khewats"][0]["khewat_number"] == "45"
    assert len(merged["khewats"][0]["owners"]) == 1
    assert len(merged["khewats"][0]["khataunis"]) == 1
