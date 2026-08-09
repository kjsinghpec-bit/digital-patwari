import test from "node:test";
import assert from "node:assert/strict";
import { installFakeDom } from "./dom-shim.mjs";

installFakeDom();
const { api, ApiError } = await import("../js/api.js");

function stubFetch(handler) {
  globalThis.fetch = async (path, options) => handler(path, options);
}

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  };
}

test("api.deleteSession sends a DELETE request to the session's own URL", async () => {
  let seen = null;
  stubFetch((path, options) => {
    seen = { path, method: options.method };
    return jsonResponse(200, { closed: true, cleanup_warning: null });
  });
  const result = await api.deleteSession("abc123");
  assert.deepEqual(seen, { path: "/api/sessions/abc123", method: "DELETE" });
  assert.equal(result.closed, true);
  assert.equal(result.cleanup_warning, null);
});

test("api.deleteSession surfaces a cleanup_warning without throwing", async () => {
  stubFetch(() => jsonResponse(200, { closed: true, cleanup_warning: "a temp file lingered" }));
  const result = await api.deleteSession("abc123");
  assert.equal(result.cleanup_warning, "a temp file lingered");
});

test("api.deleteSession throws ApiError on a non-2xx response", async () => {
  stubFetch(() => jsonResponse(404, { error: "This session is no longer available." }));
  await assert.rejects(() => api.deleteSession("gone"), ApiError);
});
