// Tiny DOM helpers. No framework, no build step.

export function h(tag, attrs = {}, children = []) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "html") el.innerHTML = value;
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "dataset") {
      Object.assign(el.dataset, value);
    } else if (value === true) {
      el.setAttribute(key, "");
    } else {
      el.setAttribute(key, value);
    }
  }
  const kids = Array.isArray(children) ? children : [children];
  for (const kid of kids) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.appendChild(typeof kid === "string" || typeof kid === "number" ? document.createTextNode(String(kid)) : kid);
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
}

export function mount(container, node) {
  clear(container);
  container.appendChild(node);
}

export function announce(message) {
  const region = document.getElementById("live-region");
  if (region) region.textContent = message;
}

const TONE_GLYPH = { ok: "✓", warn: "!", unknown: "?", info: "•", danger: "✕" };

export function statusPill(tone, text) {
  return h("span", { class: `status ${tone}` }, [
    h("span", { class: "glyph", "aria-hidden": "true" }, TONE_GLYPH[tone] || "•"),
    text,
  ]);
}

export function banner(tone, titleText, bodyNode) {
  return h("div", { class: `banner ${tone}`, role: tone === "warn" || tone === "danger" ? "alert" : "status" }, [
    h("span", { class: "glyph", "aria-hidden": "true" }, TONE_GLYPH[tone] || "•"),
    h("div", {}, [titleText ? h("h3", {}, titleText) : null, bodyNode].filter(Boolean)),
  ]);
}

// Renders a server-composed "nothing found" claim (see
// digital_patwari_ui/absence.py). The text and tone always come from the
// document view model -- this is presentation only, so the wording can
// never drift between Ask, the view models and this screen. Used by every
// screen that can show an empty list (Mutations, Possession, Mortgages).
export function absenceNotice(claim) {
  return banner(claim.tone === "unknown" ? "unknown" : "ok", null, h("p", {}, claim.text));
}

export function fmt(value, fallbackKey, tFn) {
  if (value === null || value === undefined || value === "") {
    return h("span", { class: "unknown-value" }, tFn ? tFn(fallbackKey || "common.unknown") : "Unknown");
  }
  return h("span", {}, String(value));
}
