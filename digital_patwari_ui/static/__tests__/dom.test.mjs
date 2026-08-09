import test from "node:test";
import assert from "node:assert/strict";
import { installFakeDom } from "./dom-shim.mjs";

installFakeDom();
const { h, clear, mount, statusPill, banner, fmt, absenceNotice } = await import("../js/dom.js");

test("h() builds an element with text children", () => {
  const el = h("p", {}, "hello");
  assert.equal(el.tagName, "P");
  assert.equal(el.textContent, "hello");
});

test("h() applies class, dataset and boolean attributes", () => {
  const el = h("button", { class: "btn primary", dataset: { key: "abc" }, disabled: true });
  assert.equal(el.className, "btn primary");
  assert.equal(el.dataset.key, "abc");
  assert.equal(el.getAttribute("disabled"), "");
});

test("h() wires onClick-style handlers via addEventListener", () => {
  let clicked = false;
  const el = h("button", { onclick: () => (clicked = true) });
  el.dispatch("click");
  assert.equal(clicked, true);
});

test("h() skips null/undefined/false children and attrs", () => {
  const el = h("div", { title: null, hidden: false }, [null, "text", undefined, false]);
  assert.equal(el.hasAttribute("title"), false);
  assert.equal(el.hasAttribute("hidden"), false);
  assert.equal(el.children.length, 1);
  assert.equal(el.textContent, "text");
});

test("h() nests elements, not just text", () => {
  const inner = h("span", {}, "inner");
  const outer = h("div", {}, [inner]);
  assert.equal(outer.children[0], inner);
  assert.equal(outer.textContent, "inner");
});

test("clear() removes all children", () => {
  const el = h("div", {}, ["a", "b", "c"]);
  assert.equal(el.children.length, 3);
  clear(el);
  assert.equal(el.children.length, 0);
});

test("mount() clears the container first, then appends the new node", () => {
  const container = h("div", {}, ["stale"]);
  mount(container, h("p", {}, "fresh"));
  assert.equal(container.children.length, 1);
  assert.equal(container.textContent, "fresh");
});

test("statusPill renders a tone class and the given text", () => {
  const pill = statusPill("warn", "Needs review");
  assert.equal(pill.className, "status warn");
  assert.equal(pill.textContent, "!Needs review");
});

test("statusPill falls back to a bullet glyph for an unknown tone", () => {
  const pill = statusPill("nonsense-tone", "text");
  assert.ok(pill.textContent.startsWith("•"));
});

test("banner renders tone, title and body", () => {
  const node = banner("ok", "All good", h("p", {}, "details"));
  assert.equal(node.className, "banner ok");
  assert.equal(node.getAttribute("role"), "status");
  assert.ok(node.textContent.includes("All good"));
  assert.ok(node.textContent.includes("details"));
});

test("banner uses an alert role for warn/danger tones", () => {
  const node = banner("warn", "Careful", h("p", {}, "why"));
  assert.equal(node.getAttribute("role"), "alert");
});

test("fmt() shows a value verbatim when present", () => {
  const node = fmt("3/4");
  assert.equal(node.textContent, "3/4");
  assert.equal(node.className, "");
});

test("fmt() shows the unknown fallback for null/undefined/empty", () => {
  for (const value of [null, undefined, ""]) {
    const node = fmt(value, "common.unknown", (key) => `[${key}]`);
    assert.equal(node.className, "unknown-value");
    assert.equal(node.textContent, "[common.unknown]");
  }
});

// P1 regression: absenceNotice must render exactly the server-composed
// text/tone from digital_patwari_ui.absence -- it must never compose its
// own "No X found" wording, so a screen can't drift from Ask's wording.
test("absenceNotice renders the server-composed text verbatim, in an 'ok' banner when complete", () => {
  const node = absenceNotice({ text: "No mutation entries were found.", tone: "ok", uncertain: false });
  assert.equal(node.className, "banner ok");
  assert.ok(node.textContent.includes("No mutation entries were found."));
});

test("absenceNotice uses the 'unknown' banner tone when the document is partial", () => {
  const node = absenceNotice({
    text: "No mutation entries were found in the pages successfully read. Unread pages may contain additional information.",
    tone: "unknown",
    uncertain: true,
  });
  assert.equal(node.className, "banner unknown");
  assert.ok(node.textContent.includes("Unread pages may contain additional information."));
});
