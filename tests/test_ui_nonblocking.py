"""P1: session creation and retry must return promptly -- the citizen's
browser is not left with a hung network request while pages are read.
The frontend already polls GET /api/sessions/{id} for progress
(pollUntilReady in app.js); the server must not ALSO block the initial
POST/retry response until the whole extraction finishes.
"""
from __future__ import annotations

import json
import time

import pytest

from digital_patwari_ui import fixtures as F
from digital_patwari_ui.api import Api
from digital_patwari_ui.sessions import SessionStore


@pytest.fixture
def api():
    store = SessionStore(live_enabled=False)
    yield Api(store)
    store.close_all()


def post_json(api, path, payload):
    return api.handle("POST", path, json.dumps(payload).encode("utf-8"))


def _slow_extract_structured(monkeypatch, delay: float) -> None:
    original = F.FixtureProvider.extract_structured

    def slow(self, **kwargs):
        time.sleep(delay)
        return original(self, **kwargs)

    monkeypatch.setattr(F.FixtureProvider, "extract_structured", slow)


def test_create_session_never_calls_the_blocking_wait_primitive(monkeypatch, api):
    def forbidden_wait(self, session, timeout=60.0):
        raise AssertionError("Api._create_session must not block on SessionStore.wait()")

    monkeypatch.setattr(SessionStore, "wait", forbidden_wait)
    response = post_json(api, "/api/sessions", {"scenario_key": "complete"})
    assert response.status == 201
    assert "session_id" in response.json


def test_create_session_returns_promptly_even_though_extraction_is_slow(monkeypatch, api):
    _slow_extract_structured(monkeypatch, delay=0.3)
    started = time.monotonic()
    response = post_json(api, "/api/sessions", {"scenario_key": "complete"})
    elapsed = time.monotonic() - started

    assert response.status == 201
    assert elapsed < 0.15, f"POST /api/sessions took {elapsed:.3f}s -- it must not wait for extraction"
    assert "session_id" in response.json

    # Clean up: let the slow extraction actually finish before the store
    # tears down, so it's not accessing torn-down fixtures.
    session = api.store.get(response.json["session_id"])
    api.store.wait(session, timeout=5)


def test_upload_session_returns_promptly_when_live_reading_is_enabled(monkeypatch):
    """Same contract for real uploads, not just sample scenarios."""
    import base64

    store = SessionStore(live_enabled=True)
    api = Api(store)

    def slow_build_parser(self):
        time.sleep(0.3)
        raise RuntimeError("simulated slow, then-failing live backend")

    from digital_patwari_ui.sessions import LiveBackend
    monkeypatch.setattr(LiveBackend, "build_parser", slow_build_parser)

    encoded = base64.b64encode(F.blank_page_png()).decode("ascii")
    started = time.monotonic()
    response = post_json(api, "/api/sessions", {"files": [{"name": "page.png", "data": encoded}]})
    elapsed = time.monotonic() - started

    assert response.status == 201
    assert elapsed < 0.15
    session = store.get(response.json["session_id"])
    store.wait(session, timeout=5)
    store.close_all()


def test_retry_runs_in_the_background_and_returns_before_it_finishes(monkeypatch):
    store = SessionStore(live_enabled=False)
    try:
        session = store.create_sample_session("partial")
        store.wait(session)
        assert session.result.failed_pages == (3,)

        _slow_extract_structured(monkeypatch, delay=0.3)

        started = time.monotonic()
        store.retry_failed_pages(session)
        elapsed = time.monotonic() - started

        assert elapsed < 0.15, f"retry_failed_pages took {elapsed:.3f}s -- it must spawn a background thread"
        # The phase flips to "reading" synchronously, before the thread
        # does any real work, so a citizen who immediately re-fetches the
        # session sees accurate progress rather than a stale "ready".
        assert session.phase == "reading"

        store.wait(session, timeout=5)
    finally:
        store.close_all()


def test_retry_via_the_api_also_returns_promptly(monkeypatch, api):
    created = post_json(api, "/api/sessions", {"scenario_key": "partial"}).json
    session_id = created["session_id"]
    session = api.store.get(session_id)
    api.store.wait(session)
    assert session.result.failed_pages == (3,)

    _slow_extract_structured(monkeypatch, delay=0.3)

    started = time.monotonic()
    response = post_json(api, f"/api/sessions/{session_id}/retry", {})
    elapsed = time.monotonic() - started

    assert response.status == 200
    assert elapsed < 0.15
    api.store.wait(session, timeout=5)
