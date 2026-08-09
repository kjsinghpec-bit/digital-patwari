import { h } from "../dom.js";
import { t } from "../i18n.js";
import { api, fileToBase64 } from "../api.js";

const SCENARIO_TONE = {
  complete: "ok",
  warning: "warn",
  needs_review: "warn",
  partial: "warn",
  failed: "danger",
};

export async function renderHome({ onSessionCreated, onError }) {
  const scenarios = await api.scenarios();

  const fileInput = h("input", {
    type: "file",
    accept: ".pdf,.png,.jpg,.jpeg,.webp",
    multiple: true,
    class: "visually-hidden",
    id: "file-input",
    onchange: (event) => handleFiles(event.target.files),
  });

  const cameraInput = h("input", {
    type: "file",
    accept: "image/*",
    capture: "environment",
    class: "visually-hidden",
    id: "camera-input",
    onchange: (event) => handleFiles(event.target.files),
  });

  const dropzone = h("div", { class: "dropzone", id: "dropzone" }, [
    h("p", { style: "font-size:1.2rem;font-weight:700;margin-bottom:6px;" }, "📄"),
    h("p", { "data-i18n": "home.drop" }, t("home.drop")),
    h("div", { class: "btn-row", style: "justify-content:center;margin-top:14px;" }, [
      h("button", {
        class: "btn big",
        type: "button",
        onclick: () => fileInput.click(),
      }, t("home.upload")),
      h("button", {
        class: "btn secondary",
        type: "button",
        onclick: () => cameraInput.click(),
      }, [h("span", { "aria-hidden": "true" }, "📷 "), t("home.camera")]),
    ]),
    h("p", { class: "muted small", style: "margin-top:12px;", "data-i18n": "home.formats" }, t("home.formats")),
    fileInput,
    cameraInput,
  ]);

  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragging"));
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragging");
    if (event.dataTransfer.files.length) handleFiles(event.dataTransfer.files);
  });

  async function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    try {
      const encoded = await Promise.all(
        files.map(async (file) => ({ name: file.name, data: await fileToBase64(file) }))
      );
      const session = await api.createUploadSession(encoded);
      onSessionCreated(session);
    } catch (err) {
      onError(err);
    }
  }

  const sampleButtons = scenarios.scenarios.map((scenario) =>
    h("button", {
      class: "sample-btn",
      type: "button",
      onclick: async () => {
        try {
          const session = await api.createSampleSession(scenario.key);
          onSessionCreated(session);
        } catch (err) {
          onError(err);
        }
      },
    }, [
      h("div", { style: "display:flex;align-items:center;gap:10px;justify-content:space-between;flex-wrap:wrap;" }, [
        h("strong", {}, scenario.label),
        statusChip(scenario.expected_status, SCENARIO_TONE[scenario.key] || "info"),
      ]),
      h("span", {}, scenario.description),
    ])
  );

  return h("div", { class: "stack" }, [
    h("div", { class: "hero" }, [
      h("h1", {}, [t("brand.name") || "Digital Patwari"]),
      h("p", { class: "tagline", "data-i18n": "home.tagline" }, t("home.tagline")),
    ]),
    h("div", { class: "card" }, [
      h("p", { "data-i18n": "home.lead" }, t("home.lead")),
      dropzone,
    ]),
    h("div", { class: "card" }, [
      h("p", { class: "muted small", "data-i18n": "home.privacy" }, t("home.privacy")),
      h("p", { class: "muted small", "data-i18n": "home.legal" }, t("home.legal")),
    ]),
    h("div", { class: "card" }, [
      h("h2", { "data-i18n": "home.samples.title" }, t("home.samples.title")),
      h("p", { class: "muted", "data-i18n": "home.samples.lead" }, t("home.samples.lead")),
      h("div", { class: "samples", style: "margin-top:12px;" }, sampleButtons),
    ]),
    h("details", { class: "how" }, [
      h("summary", { "data-i18n": "home.how.title" }, t("home.how.title")),
      h("p", { "data-i18n": "home.how.body" }, t("home.how.body")),
    ]),
  ]);
}

function statusChip(status, tone) {
  const labels = {
    COMPLETE: "Complete",
    COMPLETE_WITH_WARNINGS: "Warnings",
    PARTIAL: "Needs attention",
    FAILED: "Failed",
  };
  return h("span", { class: `status ${tone}` }, labels[status] || status);
}
