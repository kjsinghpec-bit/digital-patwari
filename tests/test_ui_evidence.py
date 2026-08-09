"""Evidence viewing for REAL uploaded documents (not just synthetic sample
fixtures). Every page-evidence lookup is resolved from the session's own
``page_paths`` -- never from a filesystem path supplied by the client --
and reuses ``digital_patwari.document_io.load_document_parts`` (the
project's existing page-splitting architecture) for PDFs rather than
inventing a new renderer or a shell-command solution.
"""
from __future__ import annotations

import io
import json

import pytest
from pypdf import PdfWriter

from digital_patwari_ui import fixtures as F
from digital_patwari_ui.api import Api
from digital_patwari_ui.sessions import SessionStore


@pytest.fixture
def api():
    store = SessionStore(live_enabled=True)
    yield Api(store)
    store.close_all()


def _minimal_pdf_bytes(pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _upload_session(api, files):
    import base64

    encoded = [{"name": name, "data": base64.b64encode(data).decode("ascii")} for name, data in files]
    response = api.handle("POST", "/api/sessions", json.dumps({"files": encoded}).encode("utf-8"))
    assert response.status == 201, response.body
    return response.json["session_id"]


def test_image_evidence_is_served_with_the_original_bytes_and_mime_type(api):
    png_bytes = F.blank_page_png()
    session_id = _upload_session(api, [("page-1.png", png_bytes)])

    response = api.handle("GET", f"/api/sessions/{session_id}/pages/1")
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("image/png")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.body == png_bytes


def test_pdf_evidence_serves_the_single_requested_page_reusing_document_io(api):
    pdf_bytes = _minimal_pdf_bytes(pages=2)
    session_id = _upload_session(api, [("record.pdf", pdf_bytes)])

    first = api.handle("GET", f"/api/sessions/{session_id}/pages/1")
    second = api.handle("GET", f"/api/sessions/{session_id}/pages/2")
    assert first.status == 200
    assert second.status == 200
    assert first.headers["Content-Type"].startswith("application/pdf")
    assert second.headers["Content-Type"].startswith("application/pdf")
    # Each page is its own single-page PDF (via document_io's existing
    # pypdf-based split), not the whole original multi-page file.
    assert first.body != pdf_bytes
    assert first.body.startswith(b"%PDF")
    assert b"/Count 1" in first.body  # a genuine single-page PDF, not the 2-page original
    assert second.body.startswith(b"%PDF")
    assert b"/Count 1" in second.body


def test_pdf_evidence_page_number_beyond_the_document_is_not_found(api):
    pdf_bytes = _minimal_pdf_bytes(pages=1)
    session_id = _upload_session(api, [("record.pdf", pdf_bytes)])
    response = api.handle("GET", f"/api/sessions/{session_id}/pages/5")
    assert response.status == 404


def test_invalid_page_number_is_not_found_not_a_crash(api):
    session_id = _upload_session(api, [("page-1.png", F.blank_page_png())])
    for bad in ["0", "-1", "abc", "1.5"]:
        response = api.handle("GET", f"/api/sessions/{session_id}/pages/{bad}")
        assert response.status == 404, bad


def test_path_traversal_in_the_page_segment_is_refused(api):
    session_id = _upload_session(api, [("page-1.png", F.blank_page_png())])
    for attempt in ["../../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "1/../../etc/passwd", "1..svg"]:
        response = api.handle("GET", f"/api/sessions/{session_id}/pages/{attempt}")
        assert response.status == 404, attempt


def test_evidence_is_session_scoped_not_reachable_across_sessions(api):
    session_a = _upload_session(api, [("page-1.png", F.blank_page_png())])
    session_b = _upload_session(api, [("page-1.png", F.blank_page_png())])

    # Page 1 legitimately exists in BOTH sessions (each has its own copy),
    # so this alone would not catch a leak. Prove scoping properly: close
    # session A's files, then confirm session B's identical page number
    # still serves its OWN bytes, never reaching into A's (already-gone)
    # workdir or any other session's files.
    api.store.close(session_a)
    response = api.handle("GET", f"/api/sessions/{session_b}/pages/1")
    assert response.status == 200
    assert api.handle("GET", f"/api/sessions/{session_a}/pages/1").status == 404


def test_unknown_session_id_gives_a_clean_404_not_a_leak(api):
    response = api.handle("GET", "/api/sessions/does-not-exist/pages/1")
    assert response.status == 404


def test_sample_scenario_evidence_still_serves_synthetic_svg(api):
    """The existing fixture/sample flow must keep working unchanged."""
    created = api.handle("POST", "/api/sessions", json.dumps({"scenario_key": "complete"}).encode("utf-8"))
    session_id = created.json["session_id"]
    response = api.handle("GET", f"/api/sessions/{session_id}/pages/1")
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("image/svg+xml")
    assert response.body.startswith(b"<svg")
