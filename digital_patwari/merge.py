"""Deterministic merge of independently-extracted per-page partial documents
into one DigitalPatwariDocument.

Each page of a Fard is extracted independently (see extraction.py's async
batching), so a Khewat/Khatauni spanning a page boundary is seen once per
page it appears on, each time with its own page-local IDs (KHW-1, KHT-1, ...)
that only happen to look alike across pages. This module recognises the same
real-world entity across pages by its PRINTED number (khewat_number,
khatauni_number, khasra_number) -- never by the page-local ID -- and
regenerates final IDs from post-merge position, per CLAUDE.md's rule that IDs
must be deterministic from document identity, hierarchy, and position.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from digital_patwari.models import (
    AreaKanalMarlaSarsahi,
    AreaObservation,
    CultivationInterest,
    DigitalPatwariDocument,
    DocumentHeader,
    ExtractionStatus,
    Khasra,
    Khatauni,
    Khewat,
    Mutation,
    Owner,
    ParcelInterest,
    Remark,
    RemarkTarget,
)

# (entity_kind, page_number, page-local id) -> regenerated document-wide id
_IdMap = dict[tuple[str, int, str], str]

_TARGET_KIND_BY_REMARK_TARGET = {
    RemarkTarget.KHEWAT: "Khewat",
    RemarkTarget.KHATAUNI: "Khatauni",
    RemarkTarget.OWNER: "Owner",
    RemarkTarget.KHASRA: "Khasra",
}


@dataclass(frozen=True)
class MergeResult:
    document: DigitalPatwariDocument
    warnings: list[str]


def _first_non_none(values: Iterable):
    for value in values:
        if value is not None:
            return value
    return None


def merge_page_documents(pages: list[tuple[int, DigitalPatwariDocument]]) -> MergeResult:
    """Merge a list of (page_number, per-page DigitalPatwariDocument) pairs,
    in page order, into one document. Every page independently validated
    against the full DigitalPatwariDocument schema; this only recombines
    them -- it does not invent or drop any extracted entity."""
    if not pages:
        raise ValueError("merge_page_documents requires at least one page")

    warnings: list[str] = []
    id_map: _IdMap = {}

    document_header, layout, schema_version = _merge_document_header(pages, warnings)
    merged_khewats, id_map = _merge_khewats(pages)

    merged_mutations, mutation_id_map = _merge_mutations(pages, id_map)
    id_map.update(mutation_id_map)

    merged_remarks = _merge_remarks(pages, id_map)
    merged_parcel_interests = _merge_parcel_interests(pages, id_map)
    merged_cultivation_interests = _merge_cultivation_interests(pages, id_map)
    merged_area_observations = _merge_area_observations(pages, id_map)

    document = DigitalPatwariDocument(
        schema_version=schema_version,
        document_header=document_header,
        layout=layout,
        khewats=merged_khewats,
        remarks=merged_remarks,
        mutations=merged_mutations,
        parcel_interests=merged_parcel_interests,
        cultivation_interests=merged_cultivation_interests,
        area_observations=merged_area_observations,
    )
    return MergeResult(document=document, warnings=warnings)


def _merge_document_header(pages, warnings: list[str]):
    first_page_number, first_doc = pages[0]
    header = first_doc.document_header
    for page_number, doc in pages[1:]:
        other = doc.document_header
        if (
            other.village != header.village
            or other.hadbast_number != header.hadbast_number
            or other.jamabandi_year != header.jamabandi_year
        ):
            warnings.append(
                f"page {page_number} document_header disagrees with page "
                f"{first_page_number}: {other!r} vs {header!r}"
            )
    return header, first_doc.layout, first_doc.schema_version


def _merge_khewats(pages) -> tuple[list[Khewat], _IdMap]:
    id_map: _IdMap = {}

    khewat_order: list[str] = []
    khewat_groups: dict[str, list[tuple[int, Khewat]]] = {}
    for page_number, doc in pages:
        for khewat in doc.khewats:
            if khewat.khewat_number not in khewat_groups:
                khewat_groups[khewat.khewat_number] = []
                khewat_order.append(khewat.khewat_number)
            khewat_groups[khewat.khewat_number].append((page_number, khewat))

    khatauni_counter = 0
    khasra_counter = 0
    owner_counter = 0
    merged_khewats: list[Khewat] = []

    for khewat_index, khewat_number in enumerate(khewat_order, start=1):
        new_khewat_id = f"KHW-{khewat_index}"
        group = khewat_groups[khewat_number]
        for page_number, khewat in group:
            id_map[("Khewat", page_number, khewat.khewat_id)] = new_khewat_id

        khatauni_order: list[str] = []
        khatauni_groups: dict[str, list[tuple[int, Khatauni]]] = {}
        for page_number, khewat_page in group:
            for khatauni in khewat_page.khataunis:
                if khatauni.khatauni_number not in khatauni_groups:
                    khatauni_groups[khatauni.khatauni_number] = []
                    khatauni_order.append(khatauni.khatauni_number)
                khatauni_groups[khatauni.khatauni_number].append((page_number, khatauni))

        merged_khataunis: list[Khatauni] = []
        for khatauni_number in khatauni_order:
            khatauni_counter += 1
            new_khatauni_id = f"KHT-{khatauni_counter}"
            kgroup = khatauni_groups[khatauni_number]
            for page_number, khatauni in kgroup:
                id_map[("Khatauni", page_number, khatauni.khatauni_id)] = new_khatauni_id

            # Khasras are matched within this merged Khatauni by khasra_number.
            # A khasra_number repeated across pages is treated as the same
            # physical row (e.g. a continuation page reprinting it) and kept
            # once, using the first page's data -- this is a deliberate
            # simplifying assumption, not a guarantee every reprint is
            # byte-identical.
            khasra_order: list[str] = []
            khasra_first_seen: dict[str, Khasra] = {}
            for page_number, khatauni in kgroup:
                for khasra in khatauni.khasras:
                    if khasra.khasra_number not in khasra_first_seen:
                        khasra_first_seen[khasra.khasra_number] = khasra
                        khasra_order.append(khasra.khasra_number)
                    else:
                        khasra_first_seen[khasra.khasra_number] = _merge_khasra_rows(
                            khasra_first_seen[khasra.khasra_number], khasra
                        )

            merged_khasras: list[Khasra] = []
            for khasra_number in khasra_order:
                khasra_counter += 1
                new_khasra_id = f"KHS-{khasra_counter}"
                merged_khasras.append(
                    khasra_first_seen[khasra_number].model_copy(
                        update={"khasra_id": new_khasra_id, "khatauni_id": new_khatauni_id}
                    )
                )
                for page_number, khatauni in kgroup:
                    for khasra in khatauni.khasras:
                        if khasra.khasra_number == khasra_number:
                            id_map[("Khasra", page_number, khasra.khasra_id)] = new_khasra_id

            merged_khataunis.append(
                Khatauni(
                    khatauni_id=new_khatauni_id,
                    khatauni_number=khatauni_number,
                    khewat_id=new_khewat_id,
                    raw_cultivator_name=_first_non_none(k.raw_cultivator_name for _, k in kgroup),
                    raw_possession_type=_first_non_none(k.raw_possession_type for _, k in kgroup),
                    raw_total_share=_first_non_none(k.raw_total_share for _, k in kgroup) or "1/1",
                    total_share=_first_non_none(k.total_share for _, k in kgroup) or "1/1",
                    recorded_total_area=_prefer_area_values(
                        _first_non_none(k.recorded_total_area for _, k in kgroup),
                        _first_non_none(k.recorded_total_area for _, k in reversed(kgroup)),
                    ),
                    khasras=merged_khasras,
                    source=_first_non_none(k.source for _, k in kgroup),
                )
            )

        # Owners are concatenated across this Khewat's pages, deduped by
        # (resolved Khatauni scope, raw name+parentage, raw share) -- real
        # Fards commonly reprint a Khewat's owner block on every continuation
        # page, and counting each reprint would double the share in AG-01.
        seen_owner_keys: set[tuple[str | None, str, str]] = set()
        merged_owners: list[Owner] = []
        for page_number, khewat_page in group:
            for owner in khewat_page.owners:
                mapped_khatauni_id = (
                    id_map.get(("Khatauni", page_number, owner.khatauni_id))
                    if owner.khatauni_id is not None
                    else None
                )
                dedup_key = (mapped_khatauni_id, owner.raw_owner_name_parentage, owner.raw_share_fraction)
                if dedup_key in seen_owner_keys:
                    continue
                seen_owner_keys.add(dedup_key)
                owner_counter += 1
                new_owner_id = f"OWN-{owner_counter}"
                id_map[("Owner", page_number, owner.owner_id)] = new_owner_id
                merged_owners.append(
                    owner.model_copy(
                        update={
                            "owner_id": new_owner_id,
                            "khewat_id": new_khewat_id,
                            "khatauni_id": mapped_khatauni_id,
                        }
                    )
                )

        merged_khewats.append(
            Khewat(
                khewat_id=new_khewat_id,
                khewat_number=khewat_number,
                owner_group_ref=_first_non_none(k.owner_group_ref for _, k in group),
                raw_total_share=_first_non_none(k.raw_total_share for _, k in group) or "1/1",
                total_share=_first_non_none(k.total_share for _, k in group) or "1/1",
                owners=merged_owners,
                khataunis=merged_khataunis,
                source=_first_non_none(k.source for _, k in group),
            )
        )

    return merged_khewats, id_map


def _prefer_non_empty(old_value: str | None, new_value: str | None) -> str | None:
    if new_value is None or new_value == "":
        return old_value
    if old_value is None or old_value == "":
        return new_value
    return old_value


def _prefer_area_values(
    old_area: AreaKanalMarlaSarsahi | None,
    new_area: AreaKanalMarlaSarsahi | None,
) -> AreaKanalMarlaSarsahi | None:
    if old_area is None:
        return new_area
    if new_area is None:
        return old_area
    old_sarsahi = old_area.total_sarsahi(20, 9)
    new_sarsahi = new_area.total_sarsahi(20, 9)
    return new_area if new_sarsahi >= old_sarsahi else old_area


def _merge_khasra_rows(existing: Khasra, candidate: Khasra) -> Khasra:
    return existing.model_copy(update={
        "murabba_number": _prefer_non_empty(existing.murabba_number, candidate.murabba_number),
        "area_kanal_marla": candidate.area_kanal_marla
        if existing.area_kanal_marla.total_sarsahi(20, 9) == 0
        and candidate.area_kanal_marla.total_sarsahi(20, 9) != 0
        else existing.area_kanal_marla,
        "raw_soil_classification": _prefer_non_empty(existing.raw_soil_classification, candidate.raw_soil_classification),
        "normalized_soil_classification": _prefer_non_empty(existing.normalized_soil_classification, candidate.normalized_soil_classification),
        "normalized_irrigation_source": _prefer_non_empty(existing.normalized_irrigation_source, candidate.normalized_irrigation_source),
        "normalized_cultivation_status": _prefer_non_empty(existing.normalized_cultivation_status, candidate.normalized_cultivation_status),
        "status": candidate.status if existing.status != ExtractionStatus.PRESENT and candidate.status == ExtractionStatus.PRESENT else existing.status,
        "source": _first_non_none(existing.source, candidate.source),
    })


def _resolve(id_map: _IdMap, kind: str, page_number: int, old_id: str | None) -> str | None:
    if old_id is None:
        return None
    return id_map.get((kind, page_number, old_id), old_id)


def _resolve_target(id_map: _IdMap, page_number: int, target_type: RemarkTarget, target_id: str) -> str:
    kind = _TARGET_KIND_BY_REMARK_TARGET[target_type]
    return _resolve(id_map, kind, page_number, target_id) or target_id


def _merge_mutations(pages, id_map: _IdMap) -> tuple[list[Mutation], _IdMap]:
    mutation_id_map: _IdMap = {}
    counter = 0
    for page_number, doc in pages:
        for mutation in doc.mutations:
            counter += 1
            mutation_id_map[("Mutation", page_number, mutation.mutation_id)] = f"MUT-{counter}"

    combined_map = {**id_map, **mutation_id_map}
    merged: list[Mutation] = []
    for page_number, doc in pages:
        for mutation in doc.mutations:
            merged.append(
                mutation.model_copy(
                    update={
                        "mutation_id": mutation_id_map[("Mutation", page_number, mutation.mutation_id)],
                        "target_id": _resolve_target(combined_map, page_number, mutation.target_type, mutation.target_id),
                        "transferor_owner_id": _resolve(combined_map, "Owner", page_number, mutation.transferor_owner_id),
                        # discharges_mutation_id can only be resolved against
                        # a mutation the model saw on the SAME page -- pages
                        # are extracted independently, so it has no way to
                        # reference another page's mutation IDs. Left
                        # unrewritten (dangling) if not found so AG-02
                        # surfaces it rather than silently dropping it.
                        "discharges_mutation_id": _resolve(
                            mutation_id_map, "Mutation", page_number, mutation.discharges_mutation_id
                        ) or mutation.discharges_mutation_id,
                    }
                )
            )
    return merged, mutation_id_map


def _merge_remarks(pages, id_map: _IdMap) -> list[Remark]:
    merged: list[Remark] = []
    for page_number, doc in pages:
        for remark in doc.remarks:
            merged.append(
                remark.model_copy(
                    update={
                        "target_id": _resolve_target(id_map, page_number, remark.target_type, remark.target_id),
                    }
                )
            )
    return merged


def _merge_parcel_interests(pages, id_map: _IdMap) -> list[ParcelInterest]:
    merged: list[ParcelInterest] = []
    counter = 0
    for page_number, doc in pages:
        for interest in doc.parcel_interests:
            counter += 1
            merged.append(
                interest.model_copy(
                    update={
                        "parcel_interest_id": f"PI-{counter}",
                        "khewat_id": _resolve(id_map, "Khewat", page_number, interest.khewat_id) or interest.khewat_id,
                        "khatauni_id": _resolve(id_map, "Khatauni", page_number, interest.khatauni_id),
                        "khasra_ids": [
                            _resolve(id_map, "Khasra", page_number, khasra_id) or khasra_id
                            for khasra_id in interest.khasra_ids
                        ],
                        "mutation_id": _resolve(id_map, "Mutation", page_number, interest.mutation_id),
                    }
                )
            )
    return merged


def _merge_cultivation_interests(pages, id_map: _IdMap) -> list[CultivationInterest]:
    merged: list[CultivationInterest] = []
    counter = 0
    for page_number, doc in pages:
        for interest in doc.cultivation_interests:
            counter += 1
            merged.append(
                interest.model_copy(
                    update={
                        "cultivation_interest_id": f"CI-{counter}",
                        "khewat_id": _resolve(id_map, "Khewat", page_number, interest.khewat_id) or interest.khewat_id,
                        "khatauni_id": _resolve(id_map, "Khatauni", page_number, interest.khatauni_id) or interest.khatauni_id,
                    }
                )
            )
    return merged


def _merge_area_observations(pages, id_map: _IdMap) -> list[AreaObservation]:
    merged: list[AreaObservation] = []
    counter = 0
    for page_number, doc in pages:
        for observation in doc.area_observations:
            counter += 1
            merged.append(
                observation.model_copy(
                    update={
                        "observation_id": f"AOBS-{counter}",
                        "khewat_id": _resolve(id_map, "Khewat", page_number, observation.khewat_id),
                        "khatauni_id": _resolve(id_map, "Khatauni", page_number, observation.khatauni_id),
                        "khasra_id": _resolve(id_map, "Khasra", page_number, observation.khasra_id),
                    }
                )
            )
    return merged


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _load_document_from_json(path: Path) -> DigitalPatwariDocument:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return DigitalPatwariDocument.model_validate(payload)


def _resolve_input_paths(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        paths = sorted([p for p in input_path.iterdir() if p.is_file() and p.suffix == ".json"])
        if not paths:
            raise ValueError(f"Directory has no JSON files: {input_path}")
        return paths
    if input_path.is_file():
        return [input_path]
    raise FileNotFoundError(input_path)


def _load_documents(input_paths: list[Path]) -> list[tuple[int, DigitalPatwariDocument]]:
    documents: list[tuple[int, DigitalPatwariDocument]] = []
    for path in sorted(input_paths):
        if path.name.endswith("validation.json"):
            continue
        document = _load_document_from_json(path)
        documents.append((len(documents) + 1, document))
    if not documents:
        raise ValueError("No valid DigitalPatwariDocument JSON files found in input path.")
    return documents


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge extracted per-page DigitalPatwariDocument JSON files into a single merged document."
    )
    parser.add_argument("input", help="Input directory containing page JSON files or a single JSON file.")
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path. Defaults to <input>/digital_patwari_document.json for directories and <input>.merged.json for a single file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    input_path = Path(args.input)
    input_paths = _resolve_input_paths(input_path)
    documents = _load_documents(input_paths)
    merge_result = merge_page_documents(documents)

    if args.output is not None:
        output_path = Path(args.output)
    elif input_path.is_dir():
        output_path = input_path / "digital_patwari_document.json"
    else:
        output_path = input_path.with_name(input_path.stem + ".merged.json")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(output_path, merge_result.document.model_dump_json(indent=2))

    print(f"Merged {len(documents)} document(s) into: {output_path}")
    if merge_result.warnings:
        print("Warnings:")
        for warning in merge_result.warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
