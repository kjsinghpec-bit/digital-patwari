import { h, statusPill } from "../dom.js";
import { t } from "../i18n.js";
import { api } from "../api.js";
import { evidenceButton } from "../evidence.js";

// Every question shown here maps 1:1 to a VerificationIssue produced by the
// real assembly/validation pipeline (digital_patwari.assembly). Submitting
// an answer calls POST /verify, which runs digital_patwari.assembly's
// apply_verification_response against the ORIGINAL page observations and
// re-runs the axiom gates — nothing here recalculates a share or an area
// itself. The original machine reading is never overwritten; it stays
// visible on the question and is preserved in the audit record the server
// returns.

function evidenceListFor(question) {
  if (!question.page_number) return [];
  return [{
    page_number: question.page_number,
    column_ref: question.column_ref,
    column_label: question.column_label,
    raw_text: question.ai_raw_text,
    status: "uncertain",
    confidence: null,
    region: question.region,
    is_blank_cell: false,
  }];
}

function questionCard(session, question, { onAnswered }) {
  const container = h("div", { class: "question" });

  function rebuild() {
    container.replaceChildren();

    const head = h("div", { class: "card-head" }, [
      statusPill("warn", question.reason_plain),
      h("div", { class: "spacer" }),
      evidenceButton(session.session_id, evidenceListFor(question), null, question.question),
    ]);
    container.appendChild(head);
    container.appendChild(h("h3", {}, question.question));
    container.appendChild(h("p", { class: "why" }, question.why_it_matters));

    if (question.ai_raw_text) {
      container.appendChild(h("p", { class: "small muted", style: "margin-top:10px;" }, "What we read:"));
      container.appendChild(h("div", { class: "raw-text" }, question.ai_raw_text));
    }

    const statusLine = h("p", { class: "small" }, [
      question.critical ? statusPill("warn", "Affects other figures until answered") : statusPill("info", "Optional"),
    ]);
    container.appendChild(statusLine);

    const feedback = h("p", { class: "small", style: "min-height:1.2em;" });
    const options = h("div", { class: "answer-options" });

    async function submit(action, extra) {
      feedback.textContent = "Saving…";
      try {
        const updated = await api.verify(session.session_id, {
          issue_id: question.issue_id,
          action,
          ...extra,
        });
        onAnswered(updated);
      } catch (err) {
        feedback.textContent = err.message || "That could not be saved. Please try again.";
      }
    }

    if (question.proposed_value !== null && question.proposed_value !== undefined) {
      options.appendChild(h("button", {
        class: "btn",
        type: "button",
        onclick: () => submit("CONFIRM"),
      }, `${t("verify.confirm")} (${question.proposed_value})`));
    }

    (question.alternatives || []).forEach((alt) => {
      options.appendChild(h("button", {
        class: "btn secondary",
        type: "button",
        onclick: () => submit("SELECT_ALTERNATIVE", { selected_alternative: alt }),
      }, `${t("verify.pick")}: ${alt}`));
    });

    const correctionInput = h("input", { type: "text", placeholder: t("verify.correct"), "aria-label": t("verify.correct") });
    options.appendChild(h("div", { class: "correction-row" }, [
      correctionInput,
      h("button", {
        class: "btn secondary",
        type: "button",
        onclick: () => {
          const value = correctionInput.value.trim();
          if (!value) { feedback.textContent = "Please type a value first."; return; }
          submit("ENTER_CORRECTION", { correction: value });
        },
      }, t("verify.submit")),
    ]));

    options.appendChild(h("button", {
      class: "btn quiet",
      type: "button",
      onclick: () => submit("dont_know"),
    }, t("verify.dontknow")));

    container.appendChild(options);
    container.appendChild(feedback);
  }

  rebuild();
  return container;
}

export function renderVerify(session, { onSessionUpdated }) {
  const doc = session.document;
  if (!doc || !doc.summary.is_readable) {
    return h("p", { class: "empty" }, "This document could not be read, so there is nothing to verify yet.");
  }
  const open = doc.questions.filter((q) => !q.resolved && !session.deferred_issue_ids.includes(q.issue_id));
  const deferred = doc.questions.filter((q) => session.deferred_issue_ids.includes(q.issue_id));
  const resolved = doc.questions.filter((q) => q.resolved);

  const wrap = h("div", { class: "stack" }, [
    h("h1", { "data-i18n": "verify.title" }, t("verify.title")),
    h("p", { class: "muted", "data-i18n": "verify.lead" }, t("verify.lead")),
  ]);

  if (!open.length && !deferred.length) {
    wrap.appendChild(h("p", { class: "empty", "data-i18n": "verify.none" }, t("verify.none")));
  } else {
    open.forEach((question) => {
      wrap.appendChild(questionCard(session, question, { onSessionUpdated, onAnswered: onSessionUpdated }));
    });
  }

  if (deferred.length) {
    wrap.appendChild(h("div", { class: "card" }, [
      h("h2", {}, "Left for later"),
      h("ul", {}, deferred.map((q) => h("li", {}, q.question))),
    ]));
  }

  if (resolved.length) {
    wrap.appendChild(h("div", { class: "card" }, [
      h("h2", {}, "Already answered"),
      h("ul", {}, resolved.map((q) => h("li", {}, [statusPill("ok", "Answered"), " ", q.question]))),
    ]));
  }

  return wrap;
}
