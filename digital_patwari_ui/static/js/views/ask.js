import { h } from "../dom.js";
import { t } from "../i18n.js";
import { api } from "../api.js";
import { evidenceButton } from "../evidence.js";

// "Ask Digital Patwari" never generates prose here or on the server. Every
// bubble is built from a typed AskAnswerVM: record_says / calculated /
// interpretation are kept as separate labelled claims (never merged into
// one sentence), citations point back to real evidence, and an
// unrecognised question returns state:"unsupported" with real suggested
// questions rather than a guess.

function claimBlock(label, text, cssClass) {
  if (!text) return null;
  return h("div", { class: `claim ${cssClass}` }, [
    h("div", { class: "claim-label" }, label),
    h("div", { class: "claim-body" }, text),
  ]);
}

function answerBubble(sessionId, answer) {
  if (answer.state === "unavailable") {
    return h("div", { class: "bubble dp" }, [h("p", {}, answer.message || t("ask.unavailable"))]);
  }

  if (answer.state === "unsupported") {
    return h("div", { class: "bubble dp" }, [
      h("p", {}, answer.message),
      answer.suggestions && answer.suggestions.length
        ? h("div", { class: "chips", style: "margin-top:10px;" },
            answer.suggestions.map((s) => h("span", { class: "chip", style: "cursor:default;" }, s.text)))
        : null,
    ]);
  }

  const evidenceBtn = evidenceButton(sessionId, answer.citations, "View cited pages");

  // Every claim goes through claimBlock, which returns null for an empty
  // claim -- filtered out here rather than appendChild'd directly, since
  // appendChild(null) throws (unlike h()'s own child list, which tolerates
  // null/false/undefined by design).
  return h("div", { class: "bubble dp" }, [
    claimBlock("What the record says", answer.record_says, "record"),
    claimBlock("Calculated", answer.calculated, "calculated"),
    claimBlock("Mutation effect", answer.mutation_effect, "interpretation"),
    claimBlock("Derived position", answer.derived_position, "interpretation"),
    claimBlock("Possession", answer.possession_position, "interpretation"),
    claimBlock("What this means", answer.interpretation, "interpretation"),
    answer.uncertain
      ? h("p", { class: "note", style: "margin-top:10px;" },
          answer.uncertainty_reason || "This answer is uncertain and should be checked.")
      : null,
    evidenceBtn ? h("div", { style: "margin-top:10px;" }, evidenceBtn) : null,
    h("p", { class: "small muted", style: "margin-top:12px;" }, answer.disclaimer || t("ask.disclaimer")),
  ]);
}

export function renderAsk(session) {
  const doc = session.document;
  const chat = h("div", { class: "chat" });
  const log = h("div", { class: "card" }, [chat]);

  const input = h("input", { type: "text", placeholder: t("ask.placeholder"), "aria-label": t("ask.placeholder") });
  const sendBtn = h("button", { class: "btn", type: "button" }, t("ask.send"));
  const form = h("form", { class: "ask-form", onsubmit: (e) => { e.preventDefault(); send(); } }, [input, sendBtn]);
  const chipsWrap = h("div", { class: "chips", style: "margin-top:14px;" });

  const unavailable = !doc || !doc.summary.is_readable;

  function addUserBubble(text) {
    chat.appendChild(h("div", { class: "bubble you" }, text));
  }

  async function ask(question, intent, subject) {
    addUserBubble(question);
    const thinking = h("div", { class: "bubble dp" }, [h("span", { class: "spinner", "aria-hidden": "true" }), " …"]);
    chat.appendChild(thinking);
    thinking.scrollIntoView({ block: "nearest" });
    try {
      const answer = await api.ask(session.session_id, question, intent, subject);
      thinking.replaceWith(answerBubble(session.session_id, answer));
    } catch (err) {
      thinking.replaceWith(h("div", { class: "bubble dp" }, err.message || "Something went wrong."));
    }
  }

  function send() {
    const value = input.value.trim();
    if (!value) return;
    input.value = "";
    ask(value);
  }

  sendBtn.addEventListener("click", send);

  if (!unavailable) {
    api.askSuggestions(session.session_id).then((data) => {
      (data.suggestions || []).slice(0, 8).forEach((s) => {
        chipsWrap.appendChild(h("button", {
          class: "chip",
          type: "button",
          onclick: () => ask(s.text, s.intent, s.subject),
        }, s.text));
      });
    }).catch(() => {});
  }

  return h("div", { class: "stack" }, [
    h("h1", { "data-i18n": "ask.title" }, t("ask.title")),
    h("p", { class: "muted", "data-i18n": "ask.lead" }, t("ask.lead")),
    log,
    unavailable
      ? h("p", { class: "empty" }, t("ask.unavailable"))
      : h("div", {}, [form, chipsWrap]),
  ]);
}
