import { h, statusPill, absenceNotice } from "../dom.js";
import { t } from "../i18n.js";
import { evidenceButton } from "../evidence.js";

function mutationCard(sessionId, mutation) {
  return h("div", { class: "card" }, [
    h("div", { class: "card-head" }, [
      statusPill(mutation.moves_ownership ? "warn" : "info", mutation.status_plain),
      h("div", { class: "spacer" }),
      evidenceButton(sessionId, mutation.evidence, null, `Mutation ${mutation.mutation_id}`),
    ]),
    h("p", {}, [h("strong", {}, "Target: "), mutation.target]),
    mutation.mutation_type ? h("p", { class: "small muted" }, `Type: ${mutation.mutation_type}${mutation.date ? " · " + mutation.date : ""}`) : null,
    mutation.transferor || mutation.transferee
      ? h("p", { class: "small" }, `${mutation.transferor ? "From: " + mutation.transferor : ""}${mutation.transferor && mutation.transferee ? " → " : ""}${mutation.transferee ? "To: " + mutation.transferee : ""}`)
      : null,
    mutation.share_transferred ? h("p", { class: "small" }, `Share stated: ${mutation.share_transferred}`) : null,
    h("div", { class: "raw-text" }, mutation.raw_text),
    mutation.meaning ? h("p", { class: "muted small" }, mutation.meaning) : null,
  ].filter(Boolean));
}

export function renderMutations(session) {
  const doc = session.document;
  if (!doc.summary.is_readable) return h("p", { class: "empty" }, "This document could not be read.");
  if (!doc.mutations.length) {
    return h("div", { class: "stack" }, [
      h("h1", { "data-i18n": "nav.mutations" }, t("nav.mutations")),
      absenceNotice(doc.mutations_absence),
    ]);
  }
  return h("div", { class: "stack" }, [
    h("h1", { "data-i18n": "nav.mutations" }, t("nav.mutations")),
    h("p", { class: "muted" }, "Only a sanctioned mutation changes recorded ownership. Everything else is shown, but does not."),
    ...doc.mutations.map((m) => mutationCard(session.session_id, m)),
  ]);
}

function cultivationCard(sessionId, entry) {
  return h("div", { class: "card" }, [
    h("div", { class: "card-head" }, [
      h("h3", {}, entry.person_name),
      h("div", { class: "spacer" }),
      evidenceButton(sessionId, entry.evidence, null, entry.person_name),
    ]),
    h("p", { class: "muted small" }, [
      entry.khewat_number ? `Khewat ${entry.khewat_number}` : null,
      entry.khatauni_number ? ` · Khatauni ${entry.khatauni_number}` : null,
    ].filter(Boolean).join("")),
    h("p", {}, entry.relationship_plain),
    entry.raw_text ? h("div", { class: "raw-text" }, entry.raw_text) : null,
  ].filter(Boolean));
}

export function renderPossession(session) {
  const doc = session.document;
  if (!doc.summary.is_readable) return h("p", { class: "empty" }, "This document could not be read.");
  return h("div", { class: "stack" }, [
    h("h1", { "data-i18n": "nav.possession" }, t("nav.possession")),
    h("p", { class: "muted" }, "Who cultivates or possesses land is recorded separately from who owns it. One does not prove the other."),
    doc.cultivation.length
      ? h("div", { class: "stack" }, doc.cultivation.map((entry) => cultivationCard(session.session_id, entry)))
      : absenceNotice(doc.possession_absence),
  ]);
}

function mortgageCard(sessionId, mortgage) {
  const tone = mortgage.tone;
  return h("div", { class: "card" }, [
    h("div", { class: "card-head" }, [
      statusPill(tone, mortgage.status_plain),
      h("div", { class: "spacer" }),
    ]),
    h("p", {}, `Khewat ${mortgage.khewat_number || "(number not read)"}`),
    h("p", { class: "muted small" }, mortgage.note),
    mortgage.mutations.length ? h("div", { class: "stack" }, [
      h("h3", {}, "Mortgage entries"),
      ...mortgage.mutations.map((m) => h("div", { class: "raw-text" }, [m.raw_text, evidenceButton(sessionId, m.evidence)].filter(Boolean))),
    ]) : null,
    mortgage.releases.length ? h("div", { class: "stack" }, [
      h("h3", {}, "Release / discharge entries"),
      ...mortgage.releases.map((m) => h("div", { class: "raw-text" }, [m.raw_text, evidenceButton(sessionId, m.evidence)].filter(Boolean))),
    ]) : null,
  ].filter(Boolean));
}

export function renderMortgages(session) {
  const doc = session.document;
  if (!doc.summary.is_readable) return h("p", { class: "empty" }, "This document could not be read.");
  return h("div", { class: "stack" }, [
    h("h1", { "data-i18n": "nav.mortgages" }, t("nav.mortgages")),
    doc.mortgages.length
      ? h("div", { class: "stack" }, doc.mortgages.map((m) => mortgageCard(session.session_id, m)))
      : absenceNotice(doc.mortgages_absence),
    doc.remarks.length ? h("div", { class: "card" }, [
      h("h2", {}, "All Column 8 remarks"),
      h("div", { class: "stack", style: "margin-top:10px;" }, doc.remarks.map((remark) =>
        h("div", { class: `finding tone-${remark.tone}` }, [
          h("div", { class: "label" }, `${remark.category_plain} · ${remark.target}`),
          h("div", { class: "raw-text", style: "margin-top:6px;" }, remark.raw_text),
          remark.meaning ? h("p", { class: "detail" }, remark.meaning) : null,
          evidenceButton(session.session_id, remark.evidence),
        ].filter(Boolean))
      )),
    ]) : absenceNotice(doc.remarks_absence),
  ].filter(Boolean));
}
