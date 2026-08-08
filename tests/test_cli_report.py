import json
from pathlib import Path

from patwari_agent import main


def test_cli_report_prints_summary(tmp_path, capsys):
    document_path = tmp_path / "digital_patwari_document.json"
    payload = {
        "document_header": {
            "village": "Sanghol",
            "hadbast_number": "12",
            "jamabandi_year": "2020-21",
            "lr_number": "LR-123",
        },
        "layout": "modern_8_column",
        "khewats": [
            {
                "khewat_id": "KHW-1",
                "khewat_number": "219",
                "owners": [
                    {
                        "owner_id": "OWN-1",
                        "khewat_id": "KHW-1",
                        "raw_owner_name_parentage": "Chaman Lal s/o Sohan Lal",
                        "normalized_owner_name": "Chaman Lal",
                        "raw_share_fraction": "1/1",
                        "share_fraction": "1/1"
                    }
                ],
                "khataunis": []
            }
        ],
        "remarks": [],
        "mutations": [],
        "parcel_interests": [],
        "cultivation_interests": [],
        "area_observations": []
    }
    document_path.write_text(json.dumps(payload), encoding="utf-8")

    ret = main(["report", str(document_path)])
    captured = capsys.readouterr()

    assert ret == 0
    assert "Digital Patwari Document Summary" in captured.out
    assert "Village: Sanghol" in captured.out
    assert "Khewats: 1" in captured.out
    assert "Owners: 1" in captured.out
