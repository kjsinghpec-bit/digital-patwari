from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from digital_patwari.cache import FilePageObservationCache
from digital_patwari.extraction import FardExtractionParser
from digital_patwari.models import DigitalPatwariDocument
from digital_patwari.providers.gemini import MyLLMAdapter

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def _find_repository_root(path: Path) -> Path | None:
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _safe_default_output_dir() -> Path:
    base = Path(os.environ.get(
        "DIGITAL_PATWARI_DATA_DIR",
        Path.home() / "Library" / "Application Support" / "DigitalPatwari",
    ))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return base / "outputs" / stamp


def _resolve_output_dir(
    supplied: str | None,
    *,
    allow_repository_output: bool,
    cwd: Path | None = None,
) -> Path:
    working_directory = (cwd or Path.cwd()).resolve()
    output = _safe_default_output_dir() if supplied is None else Path(supplied).expanduser().resolve()
    repository_root = _find_repository_root(working_directory)
    if repository_root is not None and not allow_repository_output:
        try:
            output.relative_to(repository_root)
        except ValueError:
            pass
        else:
            raise ValueError(
                "Refusing to write private Fard artifacts inside the repository. "
                "Choose an external --output-dir or explicitly pass --allow-unsafe-repository-output for development only."
            )
    return output


def _load_document_from_json(path: Path) -> DigitalPatwariDocument:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return DigitalPatwariDocument.model_validate(payload)


def _print_document_summary(document: DigitalPatwariDocument) -> None:
    header = document.document_header
    print("Digital Patwari Document Summary")
    print("================================")
    print(f"Village: {header.village}")
    print(f"Hadbast Number: {header.hadbast_number}")
    print(f"Jamabandi Year: {header.jamabandi_year}")
    print(f"LR Number: {header.lr_number}")
    if header.district:
        print(f"District: {header.district}")
    if header.tehsil:
        print(f"Tehsil: {header.tehsil}")
    print(f"Layout: {document.layout.value}")

    total_owners = sum(len(k.owners) for k in document.khewats)
    total_khataunis = sum(len(k.khataunis) for k in document.khewats)
    total_khasras = sum(len(kh.khasras) for k in document.khewats for kh in k.khataunis)
    print("")
    print(f"Khewats: {len(document.khewats)}")
    print(f"Owners: {total_owners}")
    print(f"Khataunis: {total_khataunis}")
    print(f"Khasras: {total_khasras}")
    print(f"Remarks: {len(document.remarks)}")
    print(f"Mutations: {len(document.mutations)}")
    print(f"Parcel interests: {len(document.parcel_interests)}")
    print(f"Cultivation interests: {len(document.cultivation_interests)}")
    print(f"Area observations: {len(document.area_observations)}")

    if document.khewats:
        print("\nKhewat details:")
        for khewat in document.khewats:
            khasra_count = sum(len(kh.khasras) for kh in khewat.khataunis)
            print(f"- Khewat {khewat.khewat_number}: owners={len(khewat.owners)}, khataunis={len(khewat.khataunis)}, khasras={khasra_count}")
            if khewat.owners:
                owner_names = [o.normalized_owner_name or o.raw_owner_name_parentage for o in khewat.owners]
                owner_names = owner_names[:3]
                print(f"  Owners: {', '.join(owner_names)}{('...' if len(khewat.owners) > 3 else '')}")


def _run_extract(argv: list[str]) -> int:
    parser_cli = argparse.ArgumentParser(
        description="Extract a Punjab Fard/Jamabandi into structured JSON and run the axiom gates."
    )
    parser_cli.add_argument(
        "inputs", nargs="+",
        help="One or more Fard page files (image/PDF) and/or directories of pages.",
    )
    parser_cli.add_argument(
        "--model", default=os.environ.get("DIGITAL_PATWARI_MODEL", "gemini-3.5-flash"),
        help="Gemini model name (default: %(default)s).",
    )
    parser_cli.add_argument(
        "--output-dir", default=None,
        help="External directory for private extraction artifacts. Defaults to OS application data, never the repository.",
    )
    parser_cli.add_argument(
        "--allow-unsafe-repository-output", action="store_true",
        help="Development-only override allowing private artifacts inside the Git repository.",
    )
    parser_cli.add_argument(
        "--batch-size", type=int, default=3,
        help="Number of pages to extract concurrently per batch (default: %(default)s).",
    )
    parser_cli.add_argument(
        "--page-retries", type=int, default=2,
        help="Retries for each failed page extraction (default: %(default)s).",
    )
    parser_cli.add_argument(
        "--no-cache", action="store_true",
        help="Disable reusable per-page observation caching.",
    )
    args = parser_cli.parse_args(argv)

    try:
        output_dir = _resolve_output_dir(
            args.output_dir,
            allow_repository_output=args.allow_unsafe_repository_output,
        )
    except ValueError as exc:
        parser_cli.error(str(exc))
    adapter = MyLLMAdapter(model_name=args.model)
    cache = None if args.no_cache else FilePageObservationCache(output_dir / ".page-observation-cache")
    extraction_parser = FardExtractionParser(
        provider=adapter,
        batch_size=args.batch_size,
        max_page_retries=args.page_retries,
        cache=cache,
    )

    print(f"Digital Patwari: extracting {len(args.inputs)} input path(s) with model '{args.model}'...")
    result = extraction_parser.extract(args.inputs)

    if not result.succeeded:
        print("\n--- EXTRACTION FAILED ---")
        print("\n".join(result.parser_errors))
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "digital_patwari_document.json"
    report_path = output_dir / "digital_patwari_validation.json"
    verification_path = output_dir / "digital_patwari_verification.json"
    _atomic_write_text(doc_path, result.document.model_dump_json(indent=2))
    _atomic_write_text(report_path, result.validation_report.model_dump_json(indent=2))
    _atomic_write_text(verification_path, json.dumps({
        "status": result.status.value,
        "issues": [issue.model_dump(mode="json") for issue in result.verification_issues],
        "observations": [observation.model_dump(mode="json") for observation in result.observations],
    }, ensure_ascii=False, indent=2, default=str))

    print(f"\n--- EXTRACTION {result.status.value} ---")
    print(f"Document saved to:   {doc_path}")
    print(f"Validation saved to: {report_path}")
    print(f"Verification saved:  {verification_path}")
    print(f"Axiom gates passed:  {result.validation_report.passed}")
    if result.page_warnings:
        print("\n--- WARNINGS ---")
        print("\n".join(result.page_warnings))
    return 0


def _run_report(argv: list[str]) -> int:
    parser_cli = argparse.ArgumentParser(
        description="Print a human-readable summary of a saved digital_patwari_document.json file."
    )
    parser_cli.add_argument(
        "document_path",
        help="Path to a saved digital_patwari_document.json file.",
    )
    args = parser_cli.parse_args(argv)
    document_path = Path(args.document_path)
    document = _load_document_from_json(document_path)
    _print_document_summary(document)
    return 0


def main(argv: list[str] | None = None) -> int:
    if load_dotenv is not None:
        load_dotenv()

    if argv is None:
        argv = sys.argv[1:]

    if len(argv) > 0 and argv[0] == "report":
        return _run_report(argv[1:])
    return _run_extract(argv)
