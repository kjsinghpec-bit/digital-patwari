import { h, statusPill, banner, fmt } from "../dom.js";
import { t } from "../i18n.js";
import { evidenceButton } from "../evidence.js";

export function renderSummary(session) {
  const doc = session.document;
  const summary = doc.summary;

  const statusBanner = banner(
    summary.status_tone,
    summary.status_title,
    h("p", {}, summary.status_explanation)
  );

  if (!summary.is_readable) {
    return h("div", { class: "stack" }, [
      statusBanner,
      summary.errors.length ? h("div", { class: "card" }, [
        h("h2", {}, "What went wrong"),
        h("ul", {}, summary.errors.map((e) => h("li", {}, e))),
      ]) : null,
    ].filter(Boolean));
  }

  const header = summary.header;
  const findingCards = summary.findings.map((f) =>
    h("div", { class: `finding tone-${f.tone}` }, [
      h("div", { class: "label" }, f.label),
      h("div", { class: `value ${f.value === null ? "unknown-value" : ""}` }, f.value === null ? t("common.unknown") : f.value),
      f.detail ? h("div", { class: "detail" }, f.detail) : null,
      evidenceButton(session.session_id, f.evidence, null, f.label),
    ].filter(Boolean))
  );

  const gateRows = summary.gates.map((gate) =>
    h("div", { class: "card", style: "padding:14px 16px;" }, [
      h("div", { style: "display:flex;align-items:center;gap:10px;flex-wrap:wrap;" }, [
        statusPill(gate.skipped ? "unknown" : (gate.passed ? "ok" : "warn"), gate.skipped ? "Not checked (no data)" : (gate.passed ? "Agrees" : "Disagrees")),
        h("strong", {}, gate.title),
      ]),
      h("p", { class: "muted small", style: "margin-top:6px;" }, gate.plain_language),
      gate.issues.length
        ? h("ul", { class: "small", style: "margin:8px 0 0;padding-left:18px;" },
            gate.issues.slice(0, 4).map((issue) => h("li", {}, `${issue.entity}: ${issue.message}`)))
        : null,
    ].filter(Boolean))
  );

  const pageRows = summary.pages.map((page) =>
    h("li", { class: `pagerow ${page.state}` }, [
      h("span", { class: "num", "aria-hidden": "true" }, String(page.page_number)),
      h("span", { class: "msg" }, page.message),
    ])
  );

  return h("div", { class: "stack" }, [
    statusBanner,

    header ? h("div", { class: "card" }, [
      h("div", { class: "card-head" }, [h("h2", {}, header.village), h("div", { class: "spacer" }), evidenceButton(session.session_id, header.evidence, null, "Document header")]),
      h("dl", { class: "kv" }, [
        h("dt", {}, "Hadbast"), h("dd", {}, header.hadbast_number),
        h("dt", {}, "Jamabandi year"), h("dd", {}, header.jamabandi_year),
        h("dt", {}, "LR number"), h("dd", {}, header.lr_number),
        header.district ? h("dt", {}, "District") : null,
        header.district ? h("dd", {}, header.district) : null,
        header.tehsil ? h("dt", {}, "Tehsil") : null,
        header.tehsil ? h("dd", {}, header.tehsil) : null,
        h("dt", {}, "Layout"), h("dd", {}, header.layout_plain),
      ].filter(Boolean)),
    ]) : null,

    h("div", { class: "grid cols-3" }, findingCards),

    h("div", { class: "card" }, [
      h("h2", { "data-i18n": "summary.gates.title" }, t("summary.gates.title")),
      h("p", { class: "muted small", "data-i18n": "summary.gates.lead" }, t("summary.gates.lead")),
      h("div", { class: "stack", style: "margin-top:12px;" }, gateRows),
    ]),

    h("div", { class: "card" }, [
      h("h2", { "data-i18n": "summary.pages.title" }, t("summary.pages.title")),
      h("ul", { class: "pagelist", style: "list-style:none;padding:0;margin-top:10px;" }, pageRows),
    ]),
  ].filter(Boolean));
}
