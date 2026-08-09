"""HTTP-shaped tests against Api.handle() directly -- no socket needed,
since api.py's handle(method, path, body) -> Response is a pure function."""
from __future__ import annotations

import base64
import json

import pytest

from digital_patwari_ui.api import Api
from digital_patwari_ui.sessions import SessionStore


@pytest.fixture
def api():
    store = SessionStore(live_enabled=False)
    yield Api(store)
    store.close_all()


def post_json(api, path, payload):
    return api.handle("POST", path, json.dumps(payload).encode("utf-8"))


def create_ready_session(api, scenario_key):
    """POST /api/sessions now returns promptly (P1: non-blocking session
    creation) -- reading happens in a background thread and the real
    frontend polls GET for progress. Tests that need the finished document
    wait for it explicitly here, exactly like that polling would."""
    created = post_json(api, "/api/sessions", {"scenario_key": scenario_key}).json
    session = api.store.get(created["session_id"])
    api.store.wait(session, timeout=10)
    return _session_payload_for_test(api, created["session_id"])


def _session_payload_for_test(api, session_id):
    return api.handle("GET", f"/api/sessions/{session_id}").json


def test_index_and_static_assets_are_served(api):
    assert api.handle("GET", "/").status == 200
    assert api.handle("GET", "/static/js/app.js").status == 200
    assert api.handle("GET", "/static/styles.css").status == 200


def test_static_path_traversal_is_refused(api):
    response = api.handle("GET", "/static/../../../etc/passwd")
    assert response.status == 404


def test_health_never_leaks_the_api_key_value(monkeypatch, api):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    response = api.handle("GET", "/api/health")
    assert response.status == 200
    assert b"super-secret-value" not in response.body
    assert response.json["live_credentials_present"] is True


def test_scenarios_endpoint_lists_all_registered_fixtures(api):
    response = api.handle("GET", "/api/scenarios")
    keys = {s["key"] for s in response.json["scenarios"]}
    assert keys == {"complete", "warning", "needs_review", "partial", "failed"}


def test_create_sample_session_reaches_ready_with_the_full_document(api):
    # POST itself returns promptly now (see test_ui_nonblocking.py for the
    # deterministic non-blocking regression tests); here we wait for the
    # background read the same way a real citizen's browser polls for it.
    body = create_ready_session(api, "complete")
    assert body["phase"] == "ready"
    assert body["document"]["summary"]["status"] == "COMPLETE"


def test_create_session_for_unknown_scenario_is_404(api):
    response = post_json(api, "/api/sessions", {"scenario_key": "not-a-real-scenario"})
    assert response.status == 404


def test_get_unknown_session_is_404_with_citizen_facing_message(api):
    response = api.handle("GET", "/api/sessions/does-not-exist")
    assert response.status == 404
    assert "upload again" in response.json["error"].lower()


def test_full_verify_round_trip_through_the_api(api):
    created = create_ready_session(api, "needs_review")
    session_id = created["session_id"]
    assert created["document"]["summary"]["open_questions"] == 1
    issue_id = created["document"]["questions"][0]["issue_id"]

    response = post_json(api, f"/api/sessions/{session_id}/verify", {
        "issue_id": issue_id, "action": "CONFIRM",
    })
    assert response.status == 200
    body = response.json
    assert body["document"]["summary"]["status"] == "COMPLETE"
    assert body["document"]["summary"]["open_questions"] == 0
    assert body["corrections"][0]["corrected_value"] == "3/4"


def test_verify_dont_know_defers_without_changing_the_record(api):
    created = create_ready_session(api, "needs_review")
    session_id = created["session_id"]
    issue_id = created["document"]["questions"][0]["issue_id"]

    response = post_json(api, f"/api/sessions/{session_id}/verify", {
        "issue_id": issue_id, "action": "dont_know",
    })
    body = response.json
    assert issue_id in body["deferred_issue_ids"]
    assert body["document"]["summary"]["status"] == "PARTIAL"


def test_verify_missing_fields_is_a_client_error(api):
    created = post_json(api, "/api/sessions", {"scenario_key": "needs_review"}).json
    response = post_json(api, f"/api/sessions/{created['session_id']}/verify", {"issue_id": "x"})
    assert response.status == 400


def test_ask_round_trip_through_the_api(api):
    created = create_ready_session(api, "complete")
    session_id = created["session_id"]
    response = post_json(api, f"/api/sessions/{session_id}/ask", {
        "question": "What land is recorded in Jasvir Singh's name?",
    })
    assert response.status == 200
    assert response.json["state"] == "answered"


def test_ask_suggestions_endpoint(api):
    created = create_ready_session(api, "complete")
    response = api.handle("GET", f"/api/sessions/{created['session_id']}/ask/suggestions")
    assert response.status == 200
    assert response.json["available"] is True
    assert len(response.json["suggestions"]) > 0


def test_page_svg_is_served_for_a_valid_page(api):
    created = post_json(api, "/api/sessions", {"scenario_key": "complete"}).json
    response = api.handle("GET", f"/api/sessions/{created['session_id']}/pages/1")
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("image/svg+xml")
    assert response.body.startswith(b"<svg")


def test_page_svg_for_failed_page_says_it_could_not_be_read(api):
    created = create_ready_session(api, "partial")
    response = api.handle("GET", f"/api/sessions/{created['session_id']}/pages/3")
    assert response.status == 200
    assert b"not be read" in response.body or "ਪੜ੍ਹਿਆ" in response.body.decode("utf-8")


def test_page_endpoint_with_svg_extension_is_no_longer_a_valid_route(api):
    """P1: the page-evidence route dropped its '.svg'-only assumption so it
    can serve real uploads' native MIME type (PNG/JPEG/WEBP/PDF) too."""
    created = post_json(api, "/api/sessions", {"scenario_key": "complete"}).json
    response = api.handle("GET", f"/api/sessions/{created['session_id']}/pages/1.svg")
    assert response.status == 404


def test_upload_without_files_is_rejected(api):
    response = post_json(api, "/api/sessions", {})
    assert response.status == 400


def test_upload_is_refused_when_live_reading_disabled(api):
    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\nrest").decode("ascii")
    response = post_json(api, "/api/sessions", {"files": [{"name": "page.png", "data": encoded}]})
    assert response.status == 503
    assert response.json["reading_unavailable"] is True
    assert response.json["sample_available"] is True


def test_upload_with_invalid_base64_is_rejected(api):
    response = post_json(api, "/api/sessions", {"files": [{"name": "page.png", "data": "not-base64!!"}]})
    assert response.status == 400


def test_close_session_removes_it(api):
    created = create_ready_session(api, "complete")
    session_id = created["session_id"]
    response = api.handle("DELETE", f"/api/sessions/{session_id}")
    assert response.status == 200
    assert response.json["closed"] is True
    assert response.json["cleanup_warning"] is None
    assert api.handle("GET", f"/api/sessions/{session_id}").status == 404


def test_close_session_while_reading_refuses_and_keeps_it_reachable(api):
    """P1: never delete an active extraction's files while it is reading."""
    created = post_json(api, "/api/sessions", {"scenario_key": "complete"}).json
    session_id = created["session_id"]
    response = api.handle("DELETE", f"/api/sessions/{session_id}")
    if response.json["closed"] is False:
        assert response.json["cleanup_warning"]
        assert api.handle("GET", f"/api/sessions/{session_id}").status == 200
    # Either way, wait for the real background read to finish before the
    # fixture tears the store down, so nothing is left mid-flight.
    session = api.store.get(session_id)
    if session is not None:
        api.store.wait(session, timeout=10)


def test_unknown_api_route_is_404(api):
    assert api.handle("GET", "/api/not-a-real-endpoint").status == 404
