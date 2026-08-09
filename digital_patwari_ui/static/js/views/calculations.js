import { h, statusPill } from "../dom.js";
import { t } from "../i18n.js";
import { evidenceButton } from "../evidence.js";

function calcCard(sessionId, calc) {
  return h("div", { class: "card" }, [
    h("div", { class: "card-head" }, [
      h("h3", {}, calc.title),
      h("div", { class: "spacer" }),
      evidenceButton(sessionId, calc.evidence, null, calc.title),
    ]),
    h("ol", { style: "margin:0 0 10px;padding-left:20px;" }, calc.steps.map((step) =>
      h("li", { class: "small" }, [
        h("strong", {}, step.label + ": "), step.value,
        step.note ? h("span", { class: "muted" }, ` (${step.note})`) : null,
      ].filter(Boolean))
    )),
    h("div", { style: "display:flex;align-items:center;gap:10px;flex-wrap:wrap;" }, [
      statusPill(calc.uncertain ? "unknown" : "ok", calc.uncertain ? "Cannot be completed" : "Result"),
      h("strong", { style: "font-size:1.1rem;" }, calc.result || t("common.unknown")),
    ]),
    calc.note ? h("p", { class: "muted small", style: "margin-top:8px;" }, calc.note) : null,
  ].filter(Boolean));
}

export function renderCalculations(session) {
  const doc = session.document;
  if (!doc.summary.is_readable) return h("p", { class: "empty" }, "This document could not be read.");
  return h("div", { class: "stack" }, [
    h("h1", { "data-i18n": "calc.title" }, t("calc.title")),
    h("p", { class: "muted", "data-i18n": "calc.lead" }, t("calc.lead")),
    doc.calculations.length
      ? h("div", { class: "stack" }, doc.calculations.map((c) => calcCard(session.session_id, c)))
      : h("p", { class: "empty" }, "No calculations could be produced from the pages that were read."),
  ]);
}
