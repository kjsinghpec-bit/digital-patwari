import test from "node:test";
import assert from "node:assert/strict";
import { installFakeDom } from "./dom-shim.mjs";

installFakeDom();

function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
}

test("leaveSession calls DELETE on the session and resolves with no warning on a clean close", async () => {
  let called = null;
  globalThis.fetch = async (path, options) => {
    called = { path, method: options.method };
    return jsonResponse(200, { closed: true, cleanup_warning: null });
  };
  const { leaveSession } = await import("../js/session-cleanup.js");
  const warning = await leaveSession("abc123");
  assert.deepEqual(called, { path: "/api/sessions/abc123", method: "DELETE" });
  assert.equal(warning, null);
});

test("leaveSession surfaces a non-alarming cleanup_warning to the caller", async () => {
  globalThis.fetch = async () => jsonResponse(200, { closed: true, cleanup_warning: "a temp file lingered" });
  const { leaveSession } = await import("../js/session-cleanup.js");
  const warning = await leaveSession("abc123");
  assert.equal(warning, "a temp file lingered");
});

test("leaveSession never throws when the DELETE call itself fails -- the citizen still leaves", async () => {
  globalThis.fetch = async () => { throw new Error("network down"); };
  const { leaveSession } = await import("../js/session-cleanup.js");
  const warning = await leaveSession("abc123");
  assert.equal(warning, null);
});

test("leaveSession is a no-op for a missing session id", async () => {
  let calledFetch = false;
  globalThis.fetch = async () => { calledFetch = true; return jsonResponse(200, {}); };
  const { leaveSession } = await import("../js/session-cleanup.js");
  const warning = await leaveSession(null);
  assert.equal(warning, null);
  assert.equal(calledFetch, false);
});
