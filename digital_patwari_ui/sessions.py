"""Session state and the extraction-backend boundary.

A session is one uploaded (or sample) document and everything derived from
it. Sessions live in memory for the life of the process and their working
files live in the operating system's temporary directory — never inside the
repository, and never in a location that outlives the process by design.

Two extraction backends exist:

``FixtureBackend``   serves synthetic pages through the real pipeline with
                     no network access. This is the default and the only one
                     used during UI development.
``LiveBackend``      constructs the real Gemini provider. It is opt-in via an
                     explicit flag AND a present ``GEMINI_API_KEY``; when it
                     is not enabled the UI says so plainly rather than
                     pretending an upload was analysed.
"""
from __future__ import annotations

import base64
import binascii
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from digital_patwari.assembly import apply_verification_response
from digital_patwari.document_io import load_document_parts
from digital_patwari.extraction import DocumentStatus, ExtractionResult, FardExtractionParser
from digital_patwari.observations import (
    PageObservation,
    VerificationAction,
    VerificationRecord,
    VerificationResponse,
)
from digital_patwari.reconciliation import ReconciledFardRecord, reconcile
from digital_patwari.validation import run_axiom_gates
from digital_patwari_ui import fixtures
from digital_patwari_ui.absence import compute_unread_pages
from digital_patwari_ui.ask import AskAdapter, UnavailableAskAdapter, build_ask_adapter
from digital_patwari_ui.viewmodels import DocumentVM, EvidenceIndex, build_document_vm

Phase = Literal["reading", "ready"]

SUPPORTED_UPLOAD_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

#: Bounded, opportunistic cleanup for sessions nobody ever came back to.
#: A citizen who closes the tab mid-flow, or never clicks "Upload another
#: document", must not leak temp files forever -- see the SessionStore
#: constructor's ``session_max_age_seconds`` for how this is applied.
DEFAULT_SESSION_MAX_AGE_SECONDS = 60 * 60


@dataclass(frozen=True)
class CloseResult:
    """Outcome of closing one session.

    ``closed`` is False only when the session is actively reading -- its
    files must never be deleted out from under the background extraction
    thread. ``cleanup_warning`` is set whenever file removal itself failed
    (the session is still made unreachable either way); the wording is
    deliberately calm, never alarming, since the citizen's own document is
    safe regardless of whether a temp file lingered.
    """

    closed: bool
    cleanup_warning: str | None = None


class ExtractionBackendError(RuntimeError):
    pass


class ExtractionBackend(Protocol):
    """Produces an ``ExtractionResult`` from a list of page files."""

    name: str

    def build_parser(self) -> FardExtractionParser: ...


class ReplayProvider:
    """Serves already-known observations, deferring to a fallback provider.

    Used after a human correction: corrected pages replay from memory
    (nothing is re-read, and no provider is contacted for them), while a
    page that previously failed is genuinely retried against the original
    provider.
    """

    model_name = "replay"
    cache_identity = "digital-patwari-ui-replay-v1"

    def __init__(self, observations: dict[int, PageObservation], fallback: Any) -> None:
        self.observations = observations
        self.fallback = fallback

    def extract_structured(self, **kwargs: Any) -> Any:
        parts = kwargs["document_parts"]
        page_number = int(parts[0]["page_number"])
        known = self.observations.get(page_number)
        if known is not None:
            return known.model_dump(mode="json")
        return self.fallback.extract_structured(**kwargs)


@dataclass
class FixtureBackend:
    scenario: fixtures.FixtureScenario
    name: str = "fixture"

    def build_parser(self) -> FardExtractionParser:
        return FardExtractionParser(
            provider=fixtures.FixtureProvider(self.scenario),
            batch_size=3,
            max_page_retries=0,
        )


@dataclass
class LiveBackend:
    """The real provider. Never constructed unless explicitly enabled."""

    model_name: str
    name: str = "live"

    def build_parser(self) -> FardExtractionParser:
        if not os.environ.get("GEMINI_API_KEY"):
            raise ExtractionBackendError(
                "Live reading is enabled but GEMINI_API_KEY is not set in the environment."
            )
        from digital_patwari.providers.gemini import MyLLMAdapter

        return FardExtractionParser(
            provider=MyLLMAdapter(model_name=self.model_name),
            batch_size=3,
            max_page_retries=2,
        )


@dataclass
class SessionEvent:
    at: str
    kind: str
    message: str


@dataclass
class Session:
    session_id: str
    backend: ExtractionBackend
    page_paths: list[Path]
    uploaded_pages: tuple[int, ...]
    scenario_key: str | None = None
    scenario_label: str | None = None
    workdir: Path | None = None
    phase: Phase = "reading"
    result: ExtractionResult | None = None
    record: ReconciledFardRecord | None = None
    observations: tuple[PageObservation, ...] = ()
    verification_records: list[VerificationRecord] = field(default_factory=list)
    deferred_issue_ids: list[str] = field(default_factory=list)
    events: list[SessionEvent] = field(default_factory=list)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lock: threading.Lock = field(default_factory=threading.Lock)

    def log(self, kind: str, message: str) -> None:
        self.events.append(SessionEvent(
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            kind=kind,
            message=message,
        ))

    @property
    def evidence_index(self) -> EvidenceIndex:
        return EvidenceIndex(self.observations)

    def document_vm(self) -> DocumentVM:
        if self.result is None:
            raise RuntimeError("session has not finished reading")
        return build_document_vm(
            self.session_id,
            self.result,
            self.record,
            uploaded_pages=self.uploaded_pages,
            scenario_key=self.scenario_key,
            scenario_label=self.scenario_label,
        )

    def ask_adapter(self) -> AskAdapter:
        if self.result is None:
            return UnavailableAskAdapter(
                "This document is still being read. Questions can be answered once reading finishes."
            )
        return build_ask_adapter(
            self.record, self.evidence_index,
            unread_pages=compute_unread_pages(self.result, self.uploaded_pages),
        )

    def page_svg(self, page_number: int) -> str | None:
        if self.scenario_key is None:
            return None
        scenario = fixtures.SCENARIOS.get(self.scenario_key)
        if scenario is None:
            return None
        page = scenario.page(page_number)
        if page is None:
            return None
        if self.result is not None and page_number in (self.result.failed_pages or ()):
            unreadable = fixtures.PageFixture(
                page_number=page.page_number,
                spec=page.spec.__class__(**{**page.spec.__dict__, "unreadable": True}),
                evidence=page.evidence,
                canonical_payload=page.canonical_payload,
            )
            return unreadable.svg()
        return page.svg()

    def page_evidence_bytes(self, page_number: int) -> tuple[bytes, str] | None:
        """The page image/document evidence for the citizen-facing evidence
        viewer, resolved ONLY from this session's own files -- never from a
        filesystem path supplied by a caller. Works for both the synthetic
        sample scenarios (SVG) and real uploads (the original image bytes,
        or -- for a PDF -- that one page split out via
        ``digital_patwari.document_io.load_document_parts``, the project's
        existing page-handling architecture, reused rather than any new
        shell-command or rendering solution)."""
        if self.scenario_key is not None:
            svg = self.page_svg(page_number)
            return (svg.encode("utf-8"), "image/svg+xml") if svg is not None else None

        if not self.page_paths:
            return None
        try:
            parts = load_document_parts([str(path) for path in self.page_paths])
        except Exception:
            # A corrupted or unreadable original file must never crash the
            # evidence endpoint -- it simply has no evidence to show.
            return None
        for part in parts:
            if part.get("page_number") != page_number:
                continue
            try:
                data = base64.b64decode(part["base64_data"], validate=True)
            except (binascii.Error, ValueError, KeyError):
                return None
            return data, str(part.get("mime_type") or "application/octet-stream")
        return None


class SessionStore:
    def __init__(
        self,
        *,
        live_enabled: bool = False,
        live_model: str = "gemini-3.5-flash",
        session_max_age_seconds: float = DEFAULT_SESSION_MAX_AGE_SECONDS,
    ) -> None:
        self.live_enabled = live_enabled
        self.live_model = live_model
        self.session_max_age_seconds = session_max_age_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    # -- lifecycle ------------------------------------------------------

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def _register(self, session: Session) -> Session:
        self._sweep_expired()
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def _sweep_expired(self) -> None:
        """Bounded, opportunistic cleanup for abandoned sessions: runs on
        every new session creation, evicting sessions past
        ``session_max_age_seconds`` -- except any session currently
        "reading", which is never touched no matter how old it is, since
        its background thread may still be reading its files from disk."""
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [
                session_id for session_id, session in self._sessions.items()
                if session.phase != "reading"
                and (now - session.created_at).total_seconds() > self.session_max_age_seconds
            ]
        for session_id in expired:
            self.close(session_id)

    def create_sample_session(self, scenario_key: str) -> Session:
        scenario = fixtures.SCENARIOS.get(scenario_key)
        if scenario is None:
            raise KeyError(scenario_key)
        workdir = Path(tempfile.mkdtemp(prefix="digital-patwari-ui-"))
        page_paths: list[Path] = []
        for page_number in scenario.uploaded_pages:
            path = workdir / f"page-{page_number}.png"
            path.write_bytes(fixtures.blank_page_png())
            page_paths.append(path)
        session = Session(
            session_id=uuid.uuid4().hex[:12],
            backend=FixtureBackend(scenario),
            page_paths=page_paths,
            uploaded_pages=scenario.uploaded_pages,
            scenario_key=scenario.key,
            scenario_label=scenario.label,
            workdir=workdir,
        )
        session.log("upload", f"{len(page_paths)} sample page(s) prepared. No file left this computer.")
        self._register(session)
        self._start(session)
        return session

    def create_upload_session(self, files: list[tuple[str, bytes]]) -> Session:
        """Accept caller-supplied pages. Raises on unsupported input."""
        if not files:
            raise ValueError("No file was supplied.")
        workdir = Path(tempfile.mkdtemp(prefix="digital-patwari-ui-"))
        page_paths: list[Path] = []
        for index, (filename, payload) in enumerate(files, start=1):
            suffix = Path(filename).suffix.lower()
            if suffix not in SUPPORTED_UPLOAD_SUFFIXES:
                shutil.rmtree(workdir, ignore_errors=True)
                raise ValueError(
                    f"'{filename}' is not a supported file. Please upload a PDF, or JPG/PNG/WEBP page images."
                )
            if len(payload) > MAX_UPLOAD_BYTES:
                shutil.rmtree(workdir, ignore_errors=True)
                raise ValueError(f"'{filename}' is larger than 25 MB.")
            if not payload:
                shutil.rmtree(workdir, ignore_errors=True)
                raise ValueError(f"'{filename}' is empty.")
            path = workdir / f"{index:03d}-{Path(filename).name}"
            path.write_bytes(payload)
            page_paths.append(path)

        if not self.live_enabled:
            shutil.rmtree(workdir, ignore_errors=True)
            raise ExtractionBackendError(
                "This build cannot read uploaded documents yet: the reading service is not "
                "switched on. Your file was not sent anywhere and has been discarded. You can "
                "explore Digital Patwari with a sample record instead."
            )

        session = Session(
            session_id=uuid.uuid4().hex[:12],
            backend=LiveBackend(self.live_model),
            page_paths=page_paths,
            uploaded_pages=tuple(range(1, len(page_paths) + 1)),
            workdir=workdir,
        )
        session.log("upload", f"{len(page_paths)} page(s) received.")
        self._register(session)
        self._start(session)
        return session

    # -- running --------------------------------------------------------

    def _start(self, session: Session, provider_override: Any = None) -> None:
        thread = threading.Thread(target=self._run, args=(session, provider_override), daemon=True)
        thread.start()
        session._thread = thread  # type: ignore[attr-defined]

    def _run(self, session: Session, provider_override: Any = None) -> None:
        with session.lock:
            session.phase = "reading"
            session.error = None
            session.log("reading", f"Reading {len(session.page_paths)} page(s).")
        try:
            parser = session.backend.build_parser()
            if provider_override is not None:
                parser.provider = provider_override
                parser.llm_client = provider_override
            result = parser.extract([str(path) for path in session.page_paths])
        except Exception as exc:  # noqa: BLE001 - surfaced to the citizen verbatim below
            with session.lock:
                session.phase = "ready"
                session.error = str(exc)
                session.log("error", str(exc))
            return
        self._absorb(session, result)

    def _absorb(self, session: Session, result: ExtractionResult) -> None:
        with session.lock:
            session.result = result
            session.observations = result.observations
            session.record = (
                reconcile(result.document, result.validation_report)
                if result.document is not None and result.validation_report is not None
                else None
            )
            session.phase = "ready"
            for page in result.successful_pages:
                session.log("page", f"Page {page} has been read.")
            for page in result.failed_pages:
                session.log("page_failed", f"Page {page} could not be processed.")
            if result.failed_pages:
                session.log(
                    "note",
                    "We will not treat a page we could not read as absent information.",
                )
            session.log("status", f"Result: {(result.status or DocumentStatus.FAILED).value}")

    def wait(self, session: Session, timeout: float = 60.0) -> Session:
        thread = getattr(session, "_thread", None)
        if thread is not None:
            thread.join(timeout)
        return session

    # -- retry ----------------------------------------------------------

    def retry_failed_pages(self, session: Session) -> Session:
        """Re-read only the pages that failed. Pages already read replay from
        memory and are not sent anywhere again.

        P1: runs in the background, like the initial extraction -- it must
        return promptly rather than blocking the caller (an HTTP request
        handler) for the full retry duration. ``phase`` flips to "reading"
        synchronously, before the thread starts any real work, so a
        citizen who immediately re-fetches the session sees accurate
        progress rather than a stale "ready"."""
        if session.result is None:
            return session
        if not session.result.failed_pages:
            session.log("note", "There are no failed pages to retry.")
            return session
        known = {observation.page_number: observation for observation in session.observations}
        session.log("retry", f"Retrying page(s) {', '.join(str(p) for p in session.result.failed_pages)}.")
        base_parser = session.backend.build_parser()
        provider = ReplayProvider(known, base_parser.provider)
        with session.lock:
            session.phase = "reading"
        self._start(session, provider_override=provider)
        return session

    # -- human verification ---------------------------------------------

    def apply_verification(
        self,
        session: Session,
        issue_id: str,
        action: VerificationAction,
        *,
        selected_alternative: Any = None,
        correction: Any = None,
        verifier_id: str = "citizen",
    ) -> VerificationRecord:
        """Apply one confirmed/corrected answer and recalculate.

        The original machine reading is never overwritten: it stays on the
        FieldObservation as ``extracted_value`` and in the immutable
        ``VerificationRecord`` this returns.
        """
        if session.result is None:
            raise RuntimeError("this document has not finished reading")

        response = VerificationResponse(
            issue_id=issue_id,
            action=action,
            verifier_id=verifier_id,
            verification_session_id=session.session_id,
            selected_alternative=selected_alternative,
            correction=correction,
        )
        applied = apply_verification_response(session.observations, response)
        assembly = applied.assembly
        if assembly.document is None:
            raise ValueError("the correction did not produce a readable record")

        report = run_axiom_gates(assembly.document)
        failed_pages = tuple(sorted(set(session.uploaded_pages) - set(assembly.successful_pages)))
        # Mirrors FardExtractionParser's status derivation over the same
        # assembly fields, applied to a corrected set of observations.
        if failed_pages or not assembly.has_trustworthy_header or assembly.unresolved_critical_issues:
            status = DocumentStatus.PARTIAL
        elif assembly.warnings or assembly.errors or not report.passed:
            status = DocumentStatus.COMPLETE_WITH_WARNINGS
        else:
            status = DocumentStatus.COMPLETE

        with session.lock:
            session.observations = applied.observations
            session.result = ExtractionResult(
                assembly.document,
                report,
                None,
                [],
                list(assembly.warnings) + list(assembly.errors),
                status=status,
                observations=applied.observations,
                successful_pages=assembly.successful_pages,
                failed_pages=failed_pages,
                verification_issues=assembly.verification_issues,
            )
            session.record = reconcile(assembly.document, report)
            session.verification_records.append(applied.record)
            if issue_id in session.deferred_issue_ids:
                session.deferred_issue_ids.remove(issue_id)
            session.log(
                "verification",
                f"Your answer to '{issue_id}' was recorded ({action.value}). "
                "The original reading has been kept alongside it.",
            )
        return applied.record

    def defer_verification(self, session: Session, issue_id: str) -> None:
        """Record 'I don't know' — no value is written to the record."""
        with session.lock:
            if issue_id not in session.deferred_issue_ids:
                session.deferred_issue_ids.append(issue_id)
            session.log(
                "verification",
                f"'{issue_id}' was left unanswered. Nothing was changed, and the question stays open.",
            )

    # -- cleanup --------------------------------------------------------

    def close(self, session_id: str) -> CloseResult:
        session = self._sessions.get(session_id)
        if session is None:
            return CloseResult(closed=True)  # already gone; closing is idempotent

        if session.phase == "reading":
            # Never delete an active extraction's files while it is
            # reading. Leave the session in place -- it becomes eligible
            # for the automatic expiry sweep once reading finishes and it
            # is never revisited.
            return CloseResult(
                closed=False,
                cleanup_warning=(
                    "This document is still being read, so it could not be fully cleared yet. "
                    "It will be cleared automatically once reading finishes."
                ),
            )

        with self._lock:
            self._sessions.pop(session_id, None)

        warning = None
        if session.workdir:
            try:
                shutil.rmtree(session.workdir)
            except OSError:
                warning = "Your document was cleared, but a temporary file could not be removed."
        return CloseResult(closed=True, cleanup_warning=warning)

    def close_all(self) -> None:
        for session_id in list(self._sessions):
            self.close(session_id)
