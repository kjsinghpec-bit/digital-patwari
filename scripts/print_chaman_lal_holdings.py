import fractions
import json
from pathlib import Path

SEARCH_NAME = "ਚਮਨ ਲਾਲ"


def parse_area(area_dict):
    if not area_dict:
        return fractions.Fraction(0)
    kanal = fractions.Fraction(area_dict.get("kanal", 0))
    marla = fractions.Fraction(area_dict.get("marla", 0))
    sarsahi = fractions.Fraction(area_dict.get("sarsahi", 0))
    return kanal * 20 * 9 + marla * 9 + sarsahi


def format_area(total_sarsahi):
    kanal = total_sarsahi // 180
    remainder = total_sarsahi % 180
    marla = remainder // 9
    sarsahi = remainder % 9
    return f"{kanal} Kanal {marla} Marla {sarsahi} Sarsahi"


def total_area_for_khewat(khewat):
    total = fractions.Fraction(0)
    # Prefer khatauni recorded totals where available.
    khatauni_totals = []
    for kh in khewat.get("khataunis", []):
        area = parse_area(kh.get("recorded_total_area"))
        if area > 0:
            khatauni_totals.append(area)
        else:
            khatauni_totals.append(sum(parse_area(kh.get("area_kanal_marla")) for kh in kh.get("khasras", [])))
    if any(a > 0 for a in khatauni_totals):
        return sum(khatauni_totals)
    # fallback to summing all khasras under all khataunis
    total = sum(
        parse_area(khasra.get("area_kanal_marla"))
        for kh in khewat.get("khataunis", [])
        for khasra in kh.get("khasras", [])
    )
    return total


def main():
    document_path = Path("samples/real_fard/output/digital_patwari_document.json")
    if not document_path.exists():
        raise SystemExit(f"Missing output JSON: {document_path}")

    document = json.loads(document_path.read_text(encoding="utf-8"))
    khewats_by_id = {k.get("khewat_id"): k for k in document.get("khewats", [])}

    matches = []
    for khewat in document.get("khewats", []):
        for owner in khewat.get("owners", []):
            name = owner.get("normalized_owner_name") or ""
            raw = owner.get("raw_owner_name_parentage") or ""
            if SEARCH_NAME in name or SEARCH_NAME in raw:
                khewat_number = khewat.get("khewat_number")
                share_fraction = owner.get("share_fraction")
                total_area = total_area_for_khewat(khewat)
                matches.append({
                    "khewat_id": khewat.get("khewat_id"),
                    "khewat_number": khewat_number,
                    "share_fraction": share_fraction,
                    "total_area_sarsahi": total_area,
                    "total_area_str": format_area(total_area),
                    "raw_owner_name_parentage": raw,
                })

    if not matches:
        print(f"No holdings found for {SEARCH_NAME}.")
        return

    print(f"Land holdings for {SEARCH_NAME}:\n")
    for match in matches:
        print(f"Khewat: {match['khewat_number']}")
        print(f"  Share Fraction: {match['share_fraction']}")
        print(f"  Total Area: {match['total_area_str']}")
        print(f"  Raw owner text: {match['raw_owner_name_parentage']}")
        print()


if __name__ == "__main__":
    main()
