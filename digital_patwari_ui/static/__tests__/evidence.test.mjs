import test from "node:test";
import assert from "node:assert/strict";
import { installFakeDom } from "./dom-shim.mjs";

installFakeDom();
const { evidenceButton, openEvidence, closeEvidence } = await import("../js/evidence.js");

test("evidenceButton returns null when there is no evidence to show", () => {
  assert.equal(evidenceButton("session-1", [], "label"), null);
  assert.equal(evidenceButton("session-1", null, "label"), null);
});

test("evidenceButton returns a clickable button when evidence exists", () => {
  const btn = evidenceButton("session-1", [{ page_number: 1, raw_text: "45/40" }], "View evidence");
  assert.equal(btn.tagName, "BUTTON");
  assert.ok(btn.textContent.includes("View evidence"));
});

test("clicking the evidence button opens an overlay attached to document.body", () => {
  const evidence = [{ page_number: 3, column_ref: "3", raw_text: "3/4 hissa", region: "0.1,0.1,0.2,0.05" }];
  const btn = evidenceButton("session-1", evidence, "View evidence");
  btn.dispatch("click");
  assert.equal(globalThis.document.body.children.length, 1);
  const overlay = globalThis.document.body.children[0];
  assert.equal(overlay.style.display, "flex");
  assert.ok(overlay.textContent.includes("3/4 hissa"));
  closeEvidence();
  assert.equal(overlay.style.display, "none");
});

test("openEvidence with no page-bearing evidence says so instead of showing a blank panel", () => {
  openEvidence("session-1", [{ raw_text: "no page attached" }], "some title");
  const overlay = globalThis.document.body.children[0];
  assert.ok(overlay.textContent.includes("No page evidence is attached"));
  closeEvidence();
});

test("a reading with no highlight region still shows page/column/raw text", () => {
  openEvidence("session-1", [{ page_number: 2, column_ref: "8", raw_text: "no region here" }], null);
  const overlay = globalThis.document.body.children[0];
  assert.ok(overlay.textContent.includes("no region here"));
  assert.ok(overlay.textContent.toLowerCase().includes("no exact highlight"));
  closeEvidence();
});

// P1: evidence viewing for real uploads. The page URL no longer assumes
// '.svg' -- the server decides the real MIME type -- and an image that
// fails to decode (e.g. a PDF page) must fall back to an "open" link
// rather than leaving raw text/metadata unreachable.

function findByTag(node, tag) {
  if (node.tagName === tag) return node;
  for (const child of node.children || []) {
    const found = findByTag(child, tag);
    if (found) return found;
  }
  return null;
}

test("the page image request carries no file extension", () => {
  openEvidence("session-1", [{ page_number: 4, raw_text: "text" }], null);
  const overlay = globalThis.document.body.children[0];
  const img = findByTag(overlay, "IMG");
  assert.equal(img.getAttribute("src"), "/api/sessions/session-1/pages/4");
  closeEvidence();
});

test("an image that fails to load (e.g. a PDF page) falls back to an open link, evidence text stays visible", () => {
  openEvidence("session-1", [{ page_number: 5, raw_text: "pdf page text", column_ref: "3" }], null);
  const overlay = globalThis.document.body.children[0];
  const img = findByTag(overlay, "IMG");
  assert.ok(img, "expected an <img> to exist before the error fires");
  img.dispatch("error");
  assert.equal(findByTag(overlay, "IMG"), null, "the broken <img> should have been replaced");
  assert.ok(overlay.textContent.includes("Open page 5"));
  // The raw text/metadata must remain visible regardless of the image.
  assert.ok(overlay.textContent.includes("pdf page text"));
  closeEvidence();
});
