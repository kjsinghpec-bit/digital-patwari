from __future__ import annotations

import argparse
import os
from pathlib import Path

from digital_patwari.extraction import FardExtractionParser
from digital_patwari.providers.gemini import MyLLMAdapter

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def main() -> int:
    if load_dotenv is not None:
        load_dotenv()

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
        "--output-dir", default=".",
        help="Directory to atomically write <document>.json and <document>.validation.json into.",
    )
    parser_cli.add_argument(
        "--batch-size", type=int, default=3,
        help="Number of pages to extract concurrently per batch (default: %(default)s).",
    )
    args = parser_cli.parse_args()

    adapter = MyLLMAdapter(model_name=args.model)
    extraction_parser = FardExtractionParser(llm_client=adapter, batch_size=args.batch_size)

    print(f"Digital Patwari: extracting {len(args.inputs)} input path(s) with model '{args.model}'...")
    result = extraction_parser.extract(args.inputs)

    if not result.succeeded:
        print("\n--- EXTRACTION FAILED ---")
        print("\n".join(result.parser_errors))
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    doc_path = output_dir / "digital_patwari_document.json"
    report_path = output_dir / "digital_patwari_validation.json"
    _atomic_write_text(doc_path, result.document.model_dump_json(indent=2))
    _atomic_write_text(report_path, result.validation_report.model_dump_json(indent=2))

    print("\n--- EXTRACTION SUCCESS ---")
    print(f"Document saved to:   {doc_path}")
    print(f"Validation saved to: {report_path}")
    print(f"Axiom gates passed:  {result.validation_report.passed}")
    if result.page_warnings:
        print("\n--- WARNINGS ---")
        print("\n".join(result.page_warnings))
    return 0
