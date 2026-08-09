import { h, statusPill } from "../dom.js";
import { t } from "../i18n.js";
import { evidenceButton } from "../evidence.js";

function ownerCard(sessionId, owner) {
  return h("div", { class: "person" }, [
    h("div", { class: "card-head" }, [
      h("h3", {}, owner.name),
      h("div", { class: "spacer" }),
      evidenceButton(sessionId, owner.evidence, null, owner.name),
    ]),
    owner.name !== owner.raw_name ? h("p", { class: "raw" }, `Printed as: ${owner.raw_name}`) : null,
    h("div", { class: "figures" }, [
      h("div", { class: "figure" }, [
        h("div", { class: "label" }, "Recorded share"),
        h("div", { class: `val ${owner.share_known ? "" : "unknown-value"}` }, owner.share_known ? owner.share : "Could not be read"),
      ]),
      h("div", { class: "figure" }, [
        h("div", { class: "label" }, "Land (recorded)"),
        h("div", { class: `val ${owner.area_known ? "" : "unknown-value"}` }, owner.area_known ? owner.area : t("common.unknown")),
      ]),
    ]),
    owner.area_note ? h("p", { class: "note" }, owner.area_note) : null,
    h("p", { class: "muted small" }, owner.scope_note),
    owner.reconciliation_note ? h("p", { class: "note" }, owner.reconciliation_note) : null,
  ].filter(Boolean));
}

function khasraTable(sessionId, khasras) {
  if (!khasras.length) return h("p", { class: "muted small" }, "No parcels recorded under this Khatauni.");
  return h("div", { class: "table-scroll" }, [
    h("table", { class: "parcels" }, [
      h("thead", {}, h("tr", {}, [
        h("th", {}, "Murabba / Khasra"),
        h("th", {}, "Area"),
        h("th", {}, "Irrigation"),
        h("th", {}, "Evidence"),
      ])),
      h("tbody", {}, khasras.map((khasra) => h("tr", {}, [
        h("td", {}, `${khasra.murabba_number ? khasra.murabba_number + " // " : ""}${khasra.khasra_number}`),
        h("td", {}, khasra.area_known ? khasra.area : h("em", {}, "unknown")),
        h("td", {}, khasra.irrigation || "—"),
        h("td", {}, evidenceButton(sessionId, khasra.evidence, "View") || "—"),
      ]))),
    ]),
  ]);
}

function khatauniBlock(sessionId, khatauni) {
  return h("div", { class: "khatauni" }, [
    h("div", { class: "card-head" }, [
      h("h3", {}, `Khatauni ${khatauni.khatauni_number}`),
      h("div", { class: "spacer" }),
      evidenceButton(sessionId, khatauni.evidence, null, `Khatauni ${khatauni.khatauni_number}`),
    ]),
    khatauni.continuation_note ? h("p", { class: "note" }, khatauni.continuation_note) : null,
    h("p", { class: "muted small" }, khatauni.governance_note),
    h("dl", { class: "kv" }, [
      khatauni.cultivator ? h("dt", {}, "Cultivator") : null,
      khatauni.cultivator ? h("dd", {}, khatauni.cultivator) : null,
      khatauni.possession_type ? h("dt", {}, "Possession") : null,
      khatauni.possession_type ? h("dd", {}, khatauni.possession_type) : null,
      h("dt", {}, "Printed total"),
      h("dd", {}, khatauni.recorded_area || h("em", {}, "not readable")),
      khatauni.parcels_area ? h("dt", {}, "Sum of its own parcels") : null,
      khatauni.parcels_area ? h("dd", {}, khatauni.parcels_area) : null,
    ].filter(Boolean)),
    khatauni.area_agrees === false
      ? h("p", { class: "note" }, [statusPill("warn", "Does not match"), " ", khatauni.area_note])
      : (khatauni.area_agrees === true ? h("p", { class: "small" }, [statusPill("ok", "Matches"), " these two figures agree."]) : (khatauni.area_note ? h("p", { class: "note" }, khatauni.area_note) : null)),
    khasraTable(sessionId, khatauni.khasras),
  ].filter(Boolean));
}

function khewatBlock(sessionId, khewat) {
  return h("div", { class: "khewat" }, [
    h("header", {}, [
      h("h2", {}, khewat.number_known ? `Khewat ${khewat.khewat_number}` : "Khewat (number not read on this page)"),
      h("p", { class: "muted small", style: "margin:4px 0 0;" }, [
        `Total share ${khewat.total_share || "—"} · `,
        khewat.total_area_complete ? `Total land ${khewat.total_area}` : "Total land: some Khataunis have no readable area",
      ]),
    ]),
    h("div", { class: "khewat-body stack" }, [
      h("div", {}, [
        h("h3", { "data-i18n": "owner.title" }, t("owner.title")),
        h("div", { class: "stack", style: "margin-top:10px;" }, khewat.owners.map((owner) => ownerCard(sessionId, owner))),
      ]),
      h("div", {}, [
        h("h3", {}, "Khataunis"),
        h("div", { class: "stack", style: "margin-top:10px;" }, khewat.khataunis.map((k) => khatauniBlock(sessionId, k))),
      ]),
    ]),
  ]);
}

export function renderRecords(session) {
  const doc = session.document;
  if (!doc.summary.is_readable) {
    return h("p", { class: "empty" }, "This document could not be read, so no records can be shown.");
  }
  if (!doc.khewats.length) {
    return h("p", { class: "empty", "data-i18n": "records.empty" }, t("records.empty"));
  }
  return h("div", { class: "stack" }, [
    h("h1", { "data-i18n": "records.title" }, t("records.title")),
    ...doc.khewats.map((khewat) => khewatBlock(session.session_id, khewat)),
  ]);
}
