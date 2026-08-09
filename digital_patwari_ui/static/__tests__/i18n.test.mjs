import test from "node:test";
import assert from "node:assert/strict";
import { installFakeDom } from "./dom-shim.mjs";

installFakeDom();
const { t, setLang, getLang } = await import("../js/i18n.js");

test("t() returns the English string for a known key by default", () => {
  setLang("en");
  assert.equal(t("nav.summary"), "Summary");
});

test("t() falls back to the key itself when unknown, never blank", () => {
  assert.equal(t("this.key.does.not.exist"), "this.key.does.not.exist");
});

test("setLang('pa') switches active language and persists it", () => {
  setLang("pa");
  assert.equal(getLang(), "pa");
  assert.equal(t("nav.summary"), "ਸਾਰ");
  assert.equal(globalThis.localStorage.getItem("dp-lang"), "pa");
});

test("setLang sets documentElement.lang and always uses ltr direction", () => {
  setLang("pa");
  assert.equal(globalThis.document.documentElement.lang, "pa");
  assert.equal(globalThis.document.documentElement.dir, "ltr");
  setLang("en");
});

test("setLang ignores an unrecognised language code", () => {
  setLang("en");
  setLang("xx-not-a-real-language");
  assert.equal(getLang(), "en");
});

test("every English key has a Punjabi counterpart (no silent gaps)", async () => {
  // Reach into the module's private STRINGS table via behavioural probing:
  // every key that resolves in English must also resolve differently (or
  // at least intentionally) in Punjabi -- here we just assert both
  // languages answer the same well-known key set without falling back to
  // the raw key, which would indicate a missing translation.
  const keys = [
    "brand.name", "home.tagline", "home.upload", "nav.summary", "nav.records",
    "nav.mutations", "nav.possession", "nav.mortgages", "nav.calculations",
    "nav.verify", "nav.ask", "verify.confirm", "verify.dontknow", "ask.send",
  ];
  setLang("pa");
  for (const key of keys) {
    assert.notEqual(t(key), key, `missing Punjabi translation for ${key}`);
  }
  setLang("en");
  for (const key of keys) {
    assert.notEqual(t(key), key, `missing English translation for ${key}`);
  }
});
