"""Framework-free JSON API.

``handle`` is a pure function of (method, path, body) -> ``Response``. The
HTTP server in ``server.py`` is a thin shell around it, which means every
route is testable without opening a socket.

No secret is ever read, logged or returned here. The only environment
variable the UI layer consults at all is ``GEMINI_API_KEY``, and only to
answer the boolean question "is live reading possible?" — its value is
never read into a response.
"""
from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from digital_patwari.observations import VerificationAction
from digital_patwari_ui import fixtures
from digital_patwari_ui.ask import AskRequest
from digital_patwari_ui.sessions import (
    ExtractionBackendError,
    MAX_UPLOAD_BYTES,
    Session,
    SessionStore,
)

STATIC_ROOT = Path(__file__).parent / "static"

_SAFE_STATIC_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".woff2", ".ico", ".webmanifest"}


@dataclass
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def _json(payload: Any, status: int = 200) -> Response:
    return Response(
        status=status,
        body=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
    )


def _error(message: str, status: int = 400, **extra: Any) -> Response:
    return _json({"error": message, **extra}, status=status)


def _static(relative: str) -> Response:
    """Serve a file from the static root. Refuses anything outside it."""
    candidate = (STATIC_ROOT / relative.lstrip("/")).resolve()
    try:
        candidate.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return _error("Not found", 404)
    if not candidate.is_file() or candidate.suffix not in _SAFE_STATIC_SUFFIXES:
        return _error("Not found", 404)
    content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    if content_type.startswith("text/") or content_type in ("application/javascript", "application/json", "image/svg+xml"):
        content_type = f"{content_type}; charset=utf-8"
    return Response(
        status=200,
        body=candidate.read_bytes(),
        headers={"Content-Type": content_type, "Cache-Control": "no-store"},
    )


def _session_payload(session: Session, store: SessionStore) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": session.session_id,
        "phase": session.phase,
        "backend": session.backend.name,
        "live_reading_enabled": store.live_enabled,
        "scenario_key": session.scenario_key,
        "scenario_label": session.scenario_label,
        "uploaded_pages": list(session.uploaded_pages),
        "error": session.error,
        "events": [
            {"at": event.at, "kind": event.kind, "message": event.message}
            for event in session.events
        ],
        "deferred_issue_ids": list(session.deferred_issue_ids),
        "corrections": [
            {
                "issue_id": record.issue_id,
                "action": record.action.value,
                "original_value": record.original_value,
                "corrected_value": record.corrected_value,
                "at": record.timestamp.isoformat(timespec="seconds"),
                "by": record.verifier_id,
            }
            for record in session.verification_records
        ],
        "document": None,
    }
    if session.phase == "ready" and session.result is not None:
        payload["document"] = session.document_vm().model_dump(mode="json")
    return payload


class Api:
    def __init__(self, store: SessionStore) -> None:
        self.store = store

    # -- routing --------------------------------------------------------

    def handle(self, method: str, path: str, body: bytes = b"") -> Response:
        path = unquote(path.split("?", 1)[0])
        if method == "GET" and path in ("/", "/index.html"):
            return _static("index.html")
        if method == "GET" and path.startswith("/static/"):
            return _static(path[len("/static/"):])
        if path.startswith("/api/"):
            return self._api(method, path, body)
        # Client-side routes fall back to the shell.
        if method == "GET" and "." not in Path(path).name:
            return _static("index.html")
        return _error("Not found", 404)

    def _api(self, method: str, path: str, body: bytes) -> Response:
        segments = [segment for segment in path.split("/") if segment][1:]  # drop "api"

        if segments == ["health"] and method == "GET":
            return _json({
                "ok": True,
                "live_reading_enabled": self.store.live_enabled,
                # A boolean only. The key's value is never read into a response.
                "live_credentials_present": bool(os.environ.get("GEMINI_API_KEY")),
            })

        if segments == ["scenarios"] and method == "GET":
            return _json({"scenarios": [
                {
                    "key": scenario.key,
                    "label": scenario.label,
                    "description": scenario.description,
                    "expected_status": scenario.expected_status.value,
                    "pages": len(scenario.uploaded_pages),
                }
                for scenario in fixtures.SCENARIOS.values()
            ]})

        if segments == ["sessions"] and method == "POST":
            return self._create_session(body)

        if len(segments) >= 2 and segments[0] == "sessions":
            session = self.store.get(segments[1])
            if session is None:
                return _error("This session is no longer available. Please upload again.", 404)
            rest = segments[2:]
            if not rest and method == "GET":
                return _json(_session_payload(session, self.store))
            if not rest and method == "DELETE":
                result = self.store.close(session.session_id)
                return _json({"closed": result.closed, "cleanup_warning": result.cleanup_warning})
            if rest == ["retry"] and method == "POST":
                self.store.retry_failed_pages(session)
                return _json(_session_payload(session, self.store))
            if rest == ["verify"] and method == "POST":
                return self._verify(session, body)
            if rest == ["ask"] and method == "POST":
                return self._ask(session, body)
            if rest == ["ask", "suggestions"] and method == "GET":
                adapter = session.ask_adapter()
                return _json({
                    "available": adapter.available,
                    "suggestions": [item.model_dump(mode="json") for item in adapter.suggestions()],
                })
            if len(rest) == 2 and rest[0] == "pages" and method == "GET":
                return self._page_image(session, rest[1])

        return _error("Not found", 404)

    # -- handlers -------------------------------------------------------

    def _create_session(self, body: bytes) -> Response:
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return _error("The request could not be read.")
        if not isinstance(payload, dict):
            return _error("The request could not be read.")

        scenario_key = payload.get("scenario_key")
        if scenario_key:
            try:
                session = self.store.create_sample_session(str(scenario_key))
            except KeyError:
                return _error(f"There is no sample record called '{scenario_key}'.", 404)
            # P1: return promptly -- reading runs in the background and the
            # citizen's browser polls GET /api/sessions/{id} for progress,
            # exactly like a real (slower) upload. Do not block here.
            return _json(_session_payload(session, self.store), status=201)

        raw_files = payload.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            return _error("Please choose a PDF or page images to upload.")
        files: list[tuple[str, bytes]] = []
        total = 0
        for item in raw_files:
            if not isinstance(item, dict) or "name" not in item or "data" not in item:
                return _error("The uploaded file could not be read.")
            try:
                data = base64.b64decode(str(item["data"]), validate=True)
            except (binascii.Error, ValueError):
                return _error(f"'{item.get('name')}' could not be read.")
            total += len(data)
            if total > MAX_UPLOAD_BYTES:
                return _error("The pages you selected add up to more than 25 MB.", 413)
            files.append((str(item["name"]), data))

        try:
            session = self.store.create_upload_session(files)
        except ExtractionBackendError as exc:
            return _json({
                "error": str(exc),
                "reading_unavailable": True,
                "sample_available": True,
            }, status=503)
        except ValueError as exc:
            return _error(str(exc), 415)
        # P1: same -- do not block the response on extraction completion.
        return _json(_session_payload(session, self.store), status=201)

    def _verify(self, session: Session, body: bytes) -> Response:
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return _error("The request could not be read.")
        issue_id = payload.get("issue_id")
        action = payload.get("action")
        if not issue_id or not action:
            return _error("A question and an answer are both required.")

        if action == "dont_know":
            self.store.defer_verification(session, str(issue_id))
            return _json(_session_payload(session, self.store))

        try:
            verification_action = VerificationAction(action)
        except ValueError:
            return _error(f"'{action}' is not a valid answer.")

        try:
            self.store.apply_verification(
                session,
                str(issue_id),
                verification_action,
                selected_alternative=payload.get("selected_alternative"),
                correction=payload.get("correction"),
            )
        except ValueError as exc:
            return _error(str(exc), 422)
        except RuntimeError as exc:
            return _error(str(exc), 409)
        return _json(_session_payload(session, self.store))

    def _ask(self, session: Session, body: bytes) -> Response:
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return _error("The request could not be read.")
        if not isinstance(payload, dict):
            return _error("The request could not be read.")
        try:
            request = AskRequest.model_validate(payload)
        except Exception:
            return _error("Please type a question of up to 500 characters.")
        adapter = session.ask_adapter()
        return _json(adapter.ask(request).model_dump(mode="json"))

    def _page_image(self, session: Session, page_segment: str) -> Response:
        # `page_segment` must be a bare positive integer -- never a path.
        # It is resolved ONLY against this session's own files (never an
        # arbitrary filesystem path), so this check exists to reject
        # malformed input cleanly, not to prevent traversal by itself (the
        # route dispatch above already only reaches here for exactly one
        # path segment).
        if not page_segment.isdigit() or page_segment.startswith("0"):
            return _error("Not found", 404)
        page_number = int(page_segment)
        if page_number < 1:
            return _error("Not found", 404)
        evidence = session.page_evidence_bytes(page_number)
        if evidence is None:
            return _error("No page image is available for this document.", 404)
        data, mime_type = evidence
        content_type = f"{mime_type}; charset=utf-8" if mime_type == "image/svg+xml" else mime_type
        return Response(
            status=200,
            body=data,
            headers={"Content-Type": content_type, "Cache-Control": "no-store"},
        )
