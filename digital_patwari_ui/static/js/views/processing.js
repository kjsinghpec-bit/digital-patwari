import { h } from "../dom.js";
import { t } from "../i18n.js";

const STATE_LABEL = {
  read: "Read",
  reused_from_cache: "Reused from earlier",
  failed: "Could not be read",
  not_uploaded: "Not uploaded",
};

export function renderProcessing(session, { onContinue, onRetry }) {
  const doc = session.document;
  const pages = (doc && doc.summary.pages) || [];
  const total = pages.length || 1;
  const readCount = pages.filter((p) => p.state === "read" || p.state === "reused_from_cache").length;
  const failedCount = pages.filter((p) => p.state === "failed").length;
  const pct = Math.round((readCount / total) * 100);

  const rows = pages.map((page) =>
    h("li", { class: `pagerow ${page.state}` }, [
      h("span", { class: "num", "aria-hidden": "true" }, String(page.page_number)),
      h("span", { class: "msg" }, page.message),
    ])
  );

  const eventItems = session.events.slice(-8).map((event) =>
    h("li", {}, [h("span", { class: "k" }, event.kind), h("span", {}, event.message)])
  );

  const body = [
    h("div", { class: "card" }, [
      h("h1", { "data-i18n": "processing.title" }, t("processing.title")),
      h("p", { class: "muted", "data-i18n": "processing.subtitle" }, t("processing.subtitle")),
      h("div", { style: "margin:16px 0 6px;" }, [
        h("div", { class: "progress-track" }, [h("div", { class: "progress-fill", style: `width:${pct}%;` })]),
      ]),
      h("p", { class: "small muted" }, `${readCount} / ${total} pages read${failedCount ? ` · ${failedCount} could not be read` : ""}`),
      session.phase === "reading"
        ? h("p", {}, [h("span", { class: "spinner", "aria-hidden": "true" }), " Reading…"])
        : null,
    ].filter(Boolean)),

    h("div", { class: "card" }, [
      h("h2", {}, "Pages"),
      h("ul", { class: "pagelist", style: "list-style:none;padding:0;" }, rows.length ? rows : [h("p", { class: "muted" }, "Preparing your document…")]),
    ]),

    session.error
      ? h("div", { class: "card" }, [
          h("p", { class: "banner danger" }, session.error),
        ])
      : null,

    session.events.length
      ? h("div", { class: "card" }, [h("h2", {}, "Activity"), h("ul", { class: "eventlog" }, eventItems)])
      : null,
  ].filter(Boolean);

  if (session.phase === "ready") {
    const actions = [
      h("button", { class: "btn big", type: "button", onclick: onContinue }, t("processing.done")),
    ];
    if (failedCount) {
      actions.unshift(
        h("button", { class: "btn secondary", type: "button", onclick: onRetry }, t("processing.retry"))
      );
    }
    body.push(h("div", { class: "btn-row" }, actions));
  }

  return h("div", { class: "stack" }, body);
}
