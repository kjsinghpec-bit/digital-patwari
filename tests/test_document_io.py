from pathlib import Path

from patwari_agent import load_document_parts, resolve_input_paths


def test_load_document_parts_splits_pdf_into_pages(tmp_path):
    pdf_path = tmp_path / "fard.pdf"
    # Create a minimal 2-page PDF using pypdf
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    parts = load_document_parts([str(pdf_path)])
    assert len(parts) == 2
    assert all(part["mime_type"] == "application/pdf" for part in parts)
    assert parts[0]["page_number"] == 1
    assert parts[1]["page_number"] == 2
    assert parts[0]["filename"] == "fard.pdf"
    assert parts[1]["filename"] == "fard.pdf"
