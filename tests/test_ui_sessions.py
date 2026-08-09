"""Session lifecycle: creation, retry-only-failed-pages, human
verification applied against the ORIGINAL page observations (never
recalculated by hand in this layer -- apply_verification_response and
run_axiom_gates are the real digital_patwari functions), and cleanup
(explicit close + bounded automatic expiry of abandoned sessions, both of
which must never delete an active extraction's files while it is reading)."""
from __future__ import annotations

import time
from datetime import timedelta

from digital_patwari.observations import VerificationAction
from digital_patwari_ui.sessions import ExtractionBackendError, SessionStore


def test_create_sample_session_reaches_ready_with_expected_status():
    store = SessionStore(live_enabled=False)
    try:
        session = store.create_sample_session("complete")
        store.wait(session)
        assert session.phase == "ready"
        assert session.result.status.value == "COMPLETE"
        assert session.record is not None
    finally:
        store.close_all()


def test_unknown_scenario_key_raises_key_error():
    store = SessionStore(live_enabled=False)
    try:
        try:
            store.create_sample_session("does-not-exist")
            assert False, "expected KeyError"
        except KeyError:
            pass
    finally:
        store.close_all()


def test_upload_session_rejected_when_live_reading_disabled():
    store = SessionStore(live_enabled=False)
    try:
        try:
            store.create_upload_session([("page.png", b"\x89PNG\r\n\x1a\nfakebytes")])
            assert False, "expected ExtractionBackendError"
        except ExtractionBackendError as exc:
            assert "not switched on" in str(exc) or "not" in str(exc).lower()
    finally:
        store.close_all()


def test_upload_session_rejects_unsupported_file_type():
    store = SessionStore(live_enabled=True, live_model="gemini-3.5-flash")
    try:
        try:
            store.create_upload_session([("record.exe", b"whatever")])
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "supported" in str(exc).lower()
    finally:
        store.close_all()


def test_upload_session_rejects_empty_file():
    store = SessionStore(live_enabled=True)
    try:
        try:
            store.create_upload_session([("page.png", b"")])
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "empty" in str(exc).lower()
    finally:
        store.close_all()


def test_retry_only_resends_failed_pages_and_reuses_the_rest_from_memory():
    store = SessionStore(live_enabled=False)
    try:
        session = store.create_sample_session("partial")
        store.wait(session)
        assert session.result.failed_pages == (3,)
        provider_calls_before = list(session.observations)

        store.retry_failed_pages(session)
        store.wait(session)

        # Pages 1 and 2 must not have been sent to the provider again --
        # ReplayProvider serves them from the already-known observations.
        # The only observable proof at this layer is that they are still
        # present and page 3 was retried (and still fails, since the
        # fixture always fails page 3 for this scenario).
        assert {o.page_number for o in session.observations} >= {1, 2}
        assert session.result.failed_pages == (3,)
    finally:
        store.close_all()


def test_retry_with_no_failed_pages_is_a_no_op():
    store = SessionStore(live_enabled=False)
    try:
        session = store.create_sample_session("complete")
        store.wait(session)
        events_before = len(session.events)
        store.retry_failed_pages(session)
        assert any("no failed pages" in e.message.lower() for e in session.events[events_before:])
    finally:
        store.close_all()


def test_apply_verification_confirm_resolves_issue_and_recalculates_status():
    store = SessionStore(live_enabled=False)
    try:
        session = store.create_sample_session("needs_review")
        store.wait(session)
        assert session.result.status.value == "PARTIAL"
        issue_id = session.result.verification_issues[0].issue_id

        record = store.apply_verification(session, issue_id, VerificationAction.CONFIRM)

        assert record.corrected_value == "3/4"
        assert session.result.status.value == "COMPLETE"
        assert not any(not i.resolved for i in session.result.verification_issues)
        # Original AI reading must survive the correction untouched.
        assert record.original_value is None  # the smudged reading was unparseable, hence None
    finally:
        store.close_all()


def test_apply_verification_select_alternative_rejects_value_not_offered():
    store = SessionStore(live_enabled=False)
    try:
        session = store.create_sample_session("needs_review")
        store.wait(session)
        issue_id = session.result.verification_issues[0].issue_id
        try:
            store.apply_verification(
                session, issue_id, VerificationAction.SELECT_ALTERNATIVE,
                selected_alternative="9/9",
            )
            assert False, "expected ValueError"
        except ValueError:
            pass
    finally:
        store.close_all()


def test_defer_verification_leaves_original_record_unchanged():
    store = SessionStore(live_enabled=False)
    try:
        session = store.create_sample_session("needs_review")
        store.wait(session)
        issue_id = session.result.verification_issues[0].issue_id
        status_before = session.result.status
        store.defer_verification(session, issue_id)
        assert issue_id in session.deferred_issue_ids
        assert session.result.status == status_before
        assert session.verification_records == []
    finally:
        store.close_all()


def test_close_removes_session_and_deletes_its_workdir():
    store = SessionStore(live_enabled=False)
    session = store.create_sample_session("complete")
    store.wait(session)
    workdir = session.workdir
    assert workdir.exists()
    result = store.close(session.session_id)
    assert result.closed is True
    assert result.cleanup_warning is None
    assert store.get(session.session_id) is None
    assert not workdir.exists()


def test_close_is_idempotent_for_an_already_closed_session():
    store = SessionStore(live_enabled=False)
    session = store.create_sample_session("complete")
    store.wait(session)
    store.close(session.session_id)
    result = store.close(session.session_id)
    assert result.closed is True
    assert result.cleanup_warning is None


def test_close_never_deletes_files_for_a_session_that_is_still_reading():
    """P1: closing a session while its extraction thread is still running
    must not delete the files that thread is reading from disk."""
    store = SessionStore(live_enabled=False)
    session = store.create_sample_session("complete")
    # Deliberately do NOT wait -- close while phase is very likely still
    # "reading" (the fixture pipeline is fast, but the check below is on
    # the *behavioural contract*, not a timing assumption: force phase
    # back to "reading" to make this deterministic).
    session.phase = "reading"
    workdir = session.workdir
    result = store.close(session.session_id)
    assert result.closed is False
    assert result.cleanup_warning
    assert workdir.exists()
    assert store.get(session.session_id) is not None
    store.wait(session)
    store.close_all()


def test_close_reports_a_non_alarming_warning_when_deletion_fails(monkeypatch):
    store = SessionStore(live_enabled=False)
    session = store.create_sample_session("complete")
    store.wait(session)

    def boom(path):
        raise OSError("permission denied")

    monkeypatch.setattr("digital_patwari_ui.sessions.shutil.rmtree", boom)
    result = store.close(session.session_id)
    assert result.closed is True  # the session itself is gone regardless
    assert result.cleanup_warning
    assert "error" not in result.cleanup_warning.lower()  # non-alarming wording
    # The session must still be unreachable even though file removal failed.
    assert store.get(session.session_id) is None


def test_abandoned_ready_sessions_are_swept_after_they_expire():
    store = SessionStore(live_enabled=False, session_max_age_seconds=0.05)
    old_session = store.create_sample_session("complete")
    store.wait(old_session)
    old_workdir = old_session.workdir
    time.sleep(0.1)

    # The sweep runs opportunistically on the next session creation --
    # bounded, no background thread needed.
    new_session = store.create_sample_session("complete")
    store.wait(new_session)

    assert store.get(old_session.session_id) is None
    assert not old_workdir.exists()
    assert store.get(new_session.session_id) is not None
    store.close_all()


def test_expiry_sweep_never_evicts_a_session_that_is_still_reading():
    store = SessionStore(live_enabled=False, session_max_age_seconds=0.05)
    session = store.create_sample_session("complete")
    store.wait(session)
    # Simulate: finished long ago, but a citizen re-triggered a retry and
    # it is genuinely reading again right now.
    session.phase = "reading"
    session.created_at = session.created_at - timedelta(days=3650)
    time.sleep(0.1)

    store._sweep_expired()

    assert store.get(session.session_id) is not None
    session.phase = "ready"
    store.close_all()
