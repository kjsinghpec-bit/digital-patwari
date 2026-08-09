// Application shell: hash router + session state. No build step, no
// framework — each view module is a pure function of (session, callbacks)
// that returns a DOM node.

import { h, mount, clear, announce } from "./dom.js";
import { setLang, getLang, t } from "./i18n.js";
import { api, ApiError } from "./api.js";
import { leaveSession } from "./session-cleanup.js";
import { renderHome } from "./views/home.js";
import { renderProcessing } from "./views/processing.js";
import { renderSummary } from "./views/summary.js";
import { renderRecords } from "./views/records.js";
import { renderMutations, renderPossession, renderMortgages } from "./views/mutations.js";
import { renderCalculations } from "./views/calculations.js";
import { renderVerify } from "./views/verify.js";
import { renderAsk } from "./views/ask.js";

const main = document.getElementById("main");
const navEl = document.getElementById("nav");

const TABS = [
  { key: "summary", label: "nav.summary", render: renderSummary },
  { key: "records", label: "nav.records", render: renderRecords },
  { key: "mutations", label: "nav.mutations", render: renderMutations },
  { key: "possession", label: "nav.possession", render: renderPossession },
  { key: "mortgages", label: "nav.mortgages", render: renderMortgages },
  { key: "calculations", label: "nav.calculations", render: renderCalculations },
  { key: "verify", label: "nav.verify", render: null }, // wired specially: needs onSessionUpdated
  { key: "ask", label: "nav.ask", render: renderAsk },
];

// In-memory session cache so switching tabs doesn't refetch. Sessions are
// server-side and ephemeral (in-process, cleaned up on close) — this is
// purely a client-side mirror of the last-known state.
const sessions = new Map();
let pollTimer = null;

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function parseRoute() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "session" && parts[1]) {
    return { name: "session", sessionId: parts[1], tab: parts[2] || "summary" };
  }
  return { name: "home" };
}

function navigate(path) {
  window.location.hash = path;
}

function renderNav(session, activeTab) {
  if (!session) {
    navEl.hidden = true;
    clear(navEl);
    return;
  }
  navEl.hidden = false;
  const openQuestions = session.document ? session.document.summary.open_questions : 0;
  const inner = h("div", { class: "tabs-inner" }, TABS.map((tab) =>
    h("a", {
      class: "tab",
      href: `#/session/${session.session_id}/${tab.key}`,
      "aria-current": tab.key === activeTab ? "page" : null,
    }, [
      t(tab.label),
      tab.key === "verify" && openQuestions
        ? h("span", { class: "badge" }, String(openQuestions))
        : null,
    ].filter(Boolean))
  ));
  clear(navEl);
  navEl.appendChild(inner);
}

async function showHome() {
  stopPolling();
  renderNav(null);
  mount(main, h("p", { class: "empty" }, "Loading…"));
  const view = await renderHome({
    onSessionCreated: (session) => {
      sessions.set(session.session_id, session);
      navigate(`/session/${session.session_id}/summary`);
    },
    onError: (err) => showUploadError(err),
  });
  mount(main, view);
  main.focus();
  document.title = `${t("brand.name")} — ${t("home.tagline")}`;
}

function showUploadError(err) {
  const message = err instanceof ApiError ? err.message : (err && err.message) || "Something went wrong.";
  const sampleAvailable = err instanceof ApiError && err.payload && err.payload.sample_available;
  mount(main, h("div", { class: "stack" }, [
    h("div", { class: "banner danger", role: "alert" }, [
      h("span", { class: "glyph", "aria-hidden": "true" }, "!"),
      h("div", {}, [
        h("h3", {}, "This could not be uploaded"),
        h("p", {}, message),
        sampleAvailable ? h("p", {}, "You can still explore Digital Patwari with a sample record below.") : null,
      ].filter(Boolean)),
    ]),
    h("button", { class: "btn", type: "button", onclick: showHome }, t("action.back")),
  ]));
  announce(message);
}

async function refreshSession(sessionId) {
  const session = await api.getSession(sessionId);
  sessions.set(sessionId, session);
  return session;
}

function pollUntilReady(sessionId, onUpdate) {
  stopPolling();
  const tick = async () => {
    try {
      const session = await refreshSession(sessionId);
      onUpdate(session);
      if (session.phase !== "ready") {
        pollTimer = setTimeout(tick, 1500);
      }
    } catch (err) {
      // Session vanished (e.g. server restarted) — send the citizen home
      // rather than polling forever against a 404.
      showHome();
    }
  };
  pollTimer = setTimeout(tick, 1500);
}

async function showSession(sessionId, tab) {
  let session = sessions.get(sessionId);
  if (!session) {
    mount(main, h("p", { class: "empty" }, "Loading…"));
    try {
      session = await refreshSession(sessionId);
    } catch (err) {
      mount(main, h("div", { class: "stack" }, [
        h("div", { class: "banner danger", role: "alert" }, [
          h("span", { class: "glyph", "aria-hidden": "true" }, "!"),
          h("div", {}, [h("h3", {}, "This session is no longer available"), h("p", {}, "Please upload again, or try a sample record.")]),
        ]),
        h("button", { class: "btn", type: "button", onclick: showHome }, t("action.startOver")),
      ]));
      return;
    }
  }

  if (session.phase === "reading") {
    stopPolling();
    renderNav(null);
    mount(main, renderProcessing(session, {
      onContinue: () => rerender(),
      onRetry: async () => {
        await api.retrySession(sessionId);
        rerender();
      },
    }));
    document.title = `${t("processing.title")} — ${t("brand.name")}`;
    pollUntilReady(sessionId, (updated) => {
      if (window.location.hash.includes(sessionId)) {
        showSession(sessionId, tab);
      }
    });
    return;
  }

  stopPolling();

  const tabDef = TABS.find((candidate) => candidate.key === tab) || TABS[0];
  renderNav(session, tabDef.key);

  const onSessionUpdated = (updatedSession) => {
    sessions.set(sessionId, updatedSession);
    showSession(sessionId, tab);
  };

  let view;
  if (tabDef.key === "verify") {
    view = renderVerify(session, { onSessionUpdated });
  } else {
    view = tabDef.render(session);
  }

  const failedUpload = !session.document && session.phase === "ready";
  if (failedUpload) {
    view = h("div", { class: "stack" }, [
      h("div", { class: "banner danger", role: "alert" }, [
        h("span", { class: "glyph", "aria-hidden": "true" }, "!"),
        h("div", {}, [h("h3", {}, "Could not read this document"), h("p", {}, session.error || "Nothing could be read from this document.")]),
      ]),
    ]);
  }

  const actions = h("div", { class: "btn-row", style: "margin-top:22px;" }, [
    h("button", {
      class: "btn secondary",
      type: "button",
      onclick: async () => {
        // P1: the session and its temporary files are cleared server-side
        // before we navigate away, not left to the bounded expiry sweep.
        const warning = await leaveSession(sessionId);
        if (warning) announce(warning);
        showHome();
      },
    }, t("action.uploadAnother")),
  ]);

  mount(main, h("div", {}, [view, actions]));
  main.focus();
  document.title = `${t(tabDef.label)} — ${t("brand.name")}`;
}

function rerender() {
  const route = parseRoute();
  if (route.name === "session") showSession(route.sessionId, route.tab);
  else showHome();
}

function initLangSwitch() {
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLang(btn.dataset.lang));
  });
  setLang(getLang());
  window.addEventListener("dp-lang-changed", () => rerender());
}

window.addEventListener("hashchange", rerender);

initLangSwitch();
rerender();
