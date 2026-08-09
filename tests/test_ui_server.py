"""Socket-level tests for the actual HTTP server (not just Api.handle()).

These exist specifically to catch header/transport-layer defects that a
pure-function test of Api.handle() cannot see -- e.g. a Content-Security-
Policy that is correct in intent but wrong in practice, which a live
browser check caught: style-src 'self' blocked every inline style="" the
UI's own view code sets (layout only, never user content), making every
page render unstyled. The fix allows 'unsafe-inline' for style-src while
keeping script-src strict; this file pins that down so it can't regress
silently.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from digital_patwari_ui.api import Api
from digital_patwari_ui.sessions import SessionStore
from digital_patwari_ui.server import build_handler


@pytest.fixture
def live_server():
    store = SessionStore(live_enabled=False)
    api = Api(store)
    server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(api))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()
        store.close_all()


def _get(url, as_json=False):
    with urllib.request.urlopen(url) as response:
        raw = response.read()
        return response, (json.loads(raw) if as_json else raw)


def _post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request) as response:
        return response, json.loads(response.read())


def _wait_ready(session_url, timeout=5.0):
    """P1: session creation returns promptly (phase='reading') and the
    real frontend polls GET for completion -- do the same here over a
    real socket rather than assuming synchronous readiness."""
    import time as _time

    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        _, body = _get(session_url, as_json=True)
        if body["phase"] == "ready":
            return body
        _time.sleep(0.02)
    raise AssertionError(f"session at {session_url} did not become ready within {timeout}s")


def test_style_src_allows_the_ui_own_inline_styles(live_server):
    response, _ = _get(f"{live_server}/")
    csp = response.headers.get("Content-Security-Policy")
    assert csp is not None
    assert "style-src 'self' 'unsafe-inline'" in csp


def test_script_src_stays_strict_with_no_inline_or_eval(live_server):
    response, _ = _get(f"{live_server}/")
    csp = response.headers.get("Content-Security-Policy")
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp.split("script-src", 1)[1].split(";", 1)[0]
    assert "unsafe-eval" not in csp


def test_security_headers_present_on_every_response(live_server):
    response, _ = _get(f"{live_server}/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "no-referrer"


def test_index_html_served_with_csp_and_no_cache(live_server):
    response, body = _get(f"{live_server}/")
    assert response.status == 200
    assert b"Digital Patwari" in body
    assert response.headers.get("Cache-Control") == "no-store"


def test_app_js_and_styles_css_are_reachable_over_real_sockets(live_server):
    response, body = _get(f"{live_server}/static/js/app.js")
    assert response.status == 200
    assert b"import" in body  # a real ES module, not an error page

    response, body = _get(f"{live_server}/static/styles.css")
    assert response.status == 200
    assert b"--brand" in body


def test_full_sample_session_round_trip_over_real_sockets(live_server):
    _, created = _post(f"{live_server}/api/sessions", {"scenario_key": "complete"})
    assert created["session_id"]

    session_url = f"{live_server}/api/sessions/{created['session_id']}"
    fetched = _wait_ready(session_url)
    assert fetched["document"]["summary"]["status"] == "COMPLETE"

    response, fetched_again = _get(session_url, as_json=True)
    assert response.status == 200
    assert fetched_again["document"]["summary"]["status"] == "COMPLETE"


def test_unhandled_error_returns_generic_message_never_a_traceback(live_server, monkeypatch):
    def boom(self, method, path, body):
        raise RuntimeError("something exploded with a secret stack trace")

    monkeypatch.setattr(Api, "handle", boom)
    try:
        urllib.request.urlopen(f"{live_server}/")
        assert False, "expected an HTTP error"
    except urllib.error.HTTPError as exc:
        assert exc.code == 500
        body = exc.read()
        assert b"RuntimeError" not in body
        assert b"secret stack trace" not in body
        assert b"Something went wrong" in body
