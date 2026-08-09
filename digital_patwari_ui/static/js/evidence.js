// Evidence viewer: shows the synthetic page image with the highlighted
// region for one piece of evidence, plus its raw text/column/page facts.
// Every "View evidence" button across the app opens the same component so
// behaviour never drifts between screens.

import { h, clear } from "./dom.js";
import { t } from "./i18n.js";

let overlayEl = null;

function ensureOverlay() {
  if (overlayEl) return overlayEl;
  overlayEl = h("div", {
    class: "evidence-overlay",
    style:
      "position:fixed;inset:0;background:rgba(20,37,30,.55);z-index:200;display:none;" +
      "align-items:flex-start;justify-content:center;padding:24px 14px;overflow:auto;",
    onclick: (event) => {
      if (event.target === overlayEl) closeEvidence();
    },
  });
  document.body.appendChild(overlayEl);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && overlayEl.style.display !== "none") closeEvidence();
  });
  return overlayEl;
}

export function closeEvidence() {
  if (overlayEl) overlayEl.style.display = "none";
}

function regionStyle(region) {
  if (!region) return null;
  const parts = region.split(",").map(Number);
  if (parts.length !== 4 || parts.some(Number.isNaN)) return null;
  const [x, y, w, hgt] = parts;
  return `left:${x * 100}%;top:${y * 100}%;width:${w * 100}%;height:${hgt * 100}%;`;
}

export function openEvidence(sessionId, evidenceList, relatedTitle) {
  const overlay = ensureOverlay();
  const list = (evidenceList || []).filter((item) => item && item.page_number);
  const panel = h("div", {
    class: "card",
    style: "max-width:1000px;width:100%;margin:0 auto;",
    role: "dialog",
    "aria-modal": "true",
    "aria-label": t("evidence.title"),
  });

  const closeBtn = h("button", {
    class: "btn secondary",
    type: "button",
    style: "float:right;",
    onclick: closeEvidence,
  }, "✕");

  panel.appendChild(h("div", { class: "card-head" }, [
    h("h2", {}, t("evidence.title")),
    h("div", { class: "spacer" }),
    closeBtn,
  ]));

  if (relatedTitle) panel.appendChild(h("p", { class: "muted" }, relatedTitle));

  if (!list.length) {
    panel.appendChild(h("p", {}, "No page evidence is attached to this item."));
  }

  list.forEach((item) => {
    // No file extension: the server decides the real MIME type (SVG for
    // sample records, or the original PNG/JPEG/WEBP/PDF for a real
    // upload) -- the client never has to guess it from a URL.
    const pageUrl = `/api/sessions/${sessionId}/pages/${item.page_number}`;
    const style = regionStyle(item.region);
    const img = h("img", { src: pageUrl, alt: `Page ${item.page_number}` });
    // <img> cannot render a PDF page. If the browser fails to decode it as
    // an image, fall back to a same-origin link that opens it in the
    // browser's own PDF viewer, rather than showing a broken-image icon.
    img.addEventListener("error", () => {
      img.replaceWith(h("a", {
        href: pageUrl, target: "_blank", rel: "noopener",
        class: "btn secondary",
      }, `Open page ${item.page_number}`));
    });
    const stage = h("div", { class: "page-stage" }, [
      h("div", { class: "page-stage-inner" }, [
        img,
        item.is_blank_cell
          ? h("div", { class: "highlight", style: `${style || "left:0;top:0;width:100%;height:6%;"} border-color:#8a6320;` })
          : (style ? h("div", { class: "highlight", style }) : null),
      ].filter(Boolean)),
    ]);

    const meta = h("dl", { class: "kv", style: "margin-top:12px;" }, [
      h("dt", {}, t("evidence.page")), h("dd", {}, String(item.page_number)),
      item.column_label ? h("dt", {}, t("evidence.column")) : null,
      item.column_label ? h("dd", {}, item.column_label) : null,
      h("dt", {}, "Status"), h("dd", {}, `${item.status}${item.confidence ? ` · ${item.confidence} confidence` : ""}`),
    ].filter(Boolean));

    const block = h("div", { class: "stack", style: "margin-bottom:22px;" }, [
      stage,
      !style ? h("p", { class: "note" }, t("evidence.noHighlight")) : null,
      h("h3", { style: "margin-top:14px;" }, t("evidence.raw")),
      h("div", { class: "raw-text" }, item.is_blank_cell ? "(blank ruled cell)" : (item.raw_text || "—")),
      meta,
    ].filter(Boolean));
    panel.appendChild(block);
  });

  clear(overlay);
  overlay.appendChild(panel);
  overlay.style.display = "flex";
  closeBtn.focus();
}

export function evidenceButton(sessionId, evidenceList, label, relatedTitle) {
  if (!evidenceList || !evidenceList.length) return null;
  return h("button", {
    class: "evidence-btn",
    type: "button",
    onclick: () => openEvidence(sessionId, evidenceList, relatedTitle),
  }, [h("span", { "aria-hidden": "true" }, "🔍"), label || t("summary.viewEvidence")]);
}
