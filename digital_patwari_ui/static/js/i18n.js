// Minimal, dependency-free localisation. Not a translation of every server
// string (those come from the pipeline in the citizen's own reading of the
// record and are shown as-is) — this covers the UI's OWN chrome: labels,
// buttons, section titles. `t()` falls back to the key itself so a missing
// translation is visible, never blank.

const STRINGS = {
  en: {
    "brand.name": "Digital Patwari",
    "brand.powered": "Powered by FardAI",
    "footer.notice": "Digital Patwari explains what a land record says. It does not decide legal ownership and does not replace verification by the Revenue Department.",
    "home.tagline": "Understand your land record — with evidence.",
    "home.lead": "Upload your Fard. We will read every page, connect records carried across pages, calculate recorded shares and show evidence for every important answer.",
    "home.upload": "Upload Fard",
    "home.drop": "Drop a PDF or page images here, or choose a file",
    "home.formats": "Accepted: PDF, JPG, PNG, WEBP. Up to 25 MB.",
    "home.camera": "Take a photo",
    "home.privacy": "Your file is only used to read this record. It is not used to train any model.",
    "home.legal": "This is not legal advice and does not replace verification by the Punjab Revenue Department.",
    "home.samples.title": "Try a sample record",
    "home.samples.lead": "No file of your own? See how Digital Patwari behaves with these synthetic, non-real sample Fards.",
    "home.how.title": "How it works",
    "home.how.body": "Each page is read on its own. Khewats and Khataunis that continue across pages are joined by their printed numbers, not guessed. Shares and areas are calculated with exact fractions. Anything unclear is held back for your confirmation instead of being guessed.",
    "nav.summary": "Summary",
    "nav.records": "Records",
    "nav.mutations": "Mutations",
    "nav.possession": "Possession",
    "nav.mortgages": "Mortgages",
    "nav.calculations": "Calculations",
    "nav.evidence": "Evidence",
    "nav.verify": "Needs your help",
    "nav.ask": "Ask Digital Patwari",
    "processing.title": "Reading your document",
    "processing.subtitle": "This can take a moment. You can leave this page open.",
    "processing.retry": "Retry the pages that could not be read",
    "processing.done": "See the result",
    "summary.title": "Summary",
    "summary.viewEvidence": "View evidence",
    "summary.gates.title": "Consistency checks",
    "summary.gates.lead": "Digital Patwari checks the record against itself. A check that fails means two parts of the record disagree — it does not mean the record is fraudulent.",
    "summary.pages.title": "Pages",
    "records.title": "Khewats, Khataunis and Khasras",
    "records.empty": "No Khewat could be read from this document.",
    "owner.title": "Owners",
    "verify.title": "Needs your help",
    "verify.lead": "These entries could not be read with confidence. Your answer is recorded separately from the original document — the original reading is always kept.",
    "verify.none": "There is nothing that needs your confirmation right now.",
    "verify.confirm": "Yes, that's correct",
    "verify.pick": "Choose",
    "verify.correct": "Enter the correct value",
    "verify.dontknow": "I don't know",
    "verify.submit": "Save my answer",
    "evidence.title": "Evidence viewer",
    "evidence.raw": "Printed text",
    "evidence.column": "Column",
    "evidence.page": "Page",
    "evidence.noHighlight": "No exact highlight is available for this reading, but this is the page and column it came from.",
    "ask.title": "Ask Digital Patwari",
    "ask.lead": "Ask a question about this document. Answers use only what was read here, cite the page, and say plainly when something is uncertain or unsupported.",
    "ask.placeholder": "Type a question…",
    "ask.send": "Ask",
    "ask.unavailable": "Ask Digital Patwari is not available for this document yet.",
    "ask.disclaimer": "Not legal advice — verify with the Revenue Department.",
    "calc.title": "Calculations",
    "calc.lead": "Every figure below is shown with its working, so it can be checked by hand.",
    "action.back": "Back",
    "action.uploadAnother": "Upload another document",
    "action.startOver": "Start over",
    "common.unknown": "Unknown",
    "common.notRecorded": "Not recorded",
  },
  pa: {
    "brand.name": "ਡਿਜੀਟਲ ਪਟਵਾਰੀ",
    "brand.powered": "FardAI ਦੁਆਰਾ",
    "footer.notice": "ਡਿਜੀਟਲ ਪਟਵਾਰੀ ਸਿਰਫ਼ ਦੱਸਦਾ ਹੈ ਕਿ ਜ਼ਮੀਨ ਦੇ ਰਿਕਾਰਡ ਵਿੱਚ ਕੀ ਲਿਖਿਆ ਹੈ। ਇਹ ਕਾਨੂੰਨੀ ਮਾਲਕੀ ਦਾ ਫ਼ੈਸਲਾ ਨਹੀਂ ਕਰਦਾ ਅਤੇ ਮਾਲ ਵਿਭਾਗ ਦੀ ਤਸਦੀਕ ਦੀ ਥਾਂ ਨਹੀਂ ਲੈਂਦਾ।",
    "home.tagline": "ਆਪਣੇ ਜ਼ਮੀਨ ਦੇ ਰਿਕਾਰਡ ਨੂੰ ਸਬੂਤ ਨਾਲ ਸਮਝੋ।",
    "home.lead": "ਆਪਣਾ ਫਰਦ ਅਪਲੋਡ ਕਰੋ। ਅਸੀਂ ਹਰ ਸਫ਼ਾ ਪੜ੍ਹਾਂਗੇ, ਸਫ਼ਿਆਂ ਵਿਚਲੇ ਰਿਕਾਰਡ ਜੋੜਾਂਗੇ, ਹਿੱਸੇ ਗਿਣਾਂਗੇ ਅਤੇ ਹਰ ਜਵਾਬ ਦਾ ਸਬੂਤ ਦਿਖਾਵਾਂਗੇ।",
    "home.upload": "ਫਰਦ ਅਪਲੋਡ ਕਰੋ",
    "home.drop": "ਇੱਥੇ PDF ਜਾਂ ਸਫ਼ਿਆਂ ਦੀਆਂ ਤਸਵੀਰਾਂ ਸੁੱਟੋ, ਜਾਂ ਫ਼ਾਈਲ ਚੁਣੋ",
    "home.formats": "ਮਨਜ਼ੂਰ: PDF, JPG, PNG, WEBP। 25 MB ਤੱਕ।",
    "home.camera": "ਫੋਟੋ ਖਿੱਚੋ",
    "home.privacy": "ਤੁਹਾਡੀ ਫ਼ਾਈਲ ਸਿਰਫ਼ ਇਹ ਰਿਕਾਰਡ ਪੜ੍ਹਨ ਲਈ ਵਰਤੀ ਜਾਂਦੀ ਹੈ। ਇਹ ਕਿਸੇ ਮਾਡਲ ਨੂੰ ਸਿਖਲਾਈ ਦੇਣ ਲਈ ਨਹੀਂ ਵਰਤੀ ਜਾਂਦੀ।",
    "home.legal": "ਇਹ ਕਾਨੂੰਨੀ ਸਲਾਹ ਨਹੀਂ ਹੈ ਅਤੇ ਪੰਜਾਬ ਮਾਲ ਵਿਭਾਗ ਦੀ ਤਸਦੀਕ ਦੀ ਥਾਂ ਨਹੀਂ ਲੈਂਦੀ।",
    "home.samples.title": "ਇੱਕ ਨਮੂਨਾ ਰਿਕਾਰਡ ਅਜ਼ਮਾਓ",
    "home.samples.lead": "ਆਪਣੀ ਫ਼ਾਈਲ ਨਹੀਂ ਹੈ? ਵੇਖੋ ਇਹ ਬਣਾਵਟੀ, ਅਸਲੀ ਨਾ ਹੋਣ ਵਾਲੇ ਨਮੂਨਾ ਫਰਦਾਂ ਨਾਲ ਡਿਜੀਟਲ ਪਟਵਾਰੀ ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ।",
    "home.how.title": "ਇਹ ਕਿਵੇਂ ਕੰਮ ਕਰਦਾ ਹੈ",
    "home.how.body": "ਹਰ ਸਫ਼ਾ ਵੱਖਰੇ ਤੌਰ 'ਤੇ ਪੜ੍ਹਿਆ ਜਾਂਦਾ ਹੈ। ਸਫ਼ਿਆਂ ਵਿੱਚ ਜਾਰੀ ਰਹਿਣ ਵਾਲੇ ਖੇਵਟ ਤੇ ਖਤੌਨੀ ਉਹਨਾਂ ਦੇ ਛਪੇ ਨੰਬਰਾਂ ਨਾਲ ਜੋੜੇ ਜਾਂਦੇ ਹਨ, ਅੰਦਾਜ਼ੇ ਨਾਲ ਨਹੀਂ। ਹਿੱਸੇ ਤੇ ਰਕਬਾ ਸਹੀ ਭਿੰਨਾਂ ਨਾਲ ਗਿਣੇ ਜਾਂਦੇ ਹਨ। ਜੋ ਸਪੱਸ਼ਟ ਨਹੀਂ, ਉਹ ਅੰਦਾਜ਼ੇ ਦੀ ਥਾਂ ਤੁਹਾਡੀ ਤਸਦੀਕ ਲਈ ਰੱਖਿਆ ਜਾਂਦਾ ਹੈ।",
    "nav.summary": "ਸਾਰ",
    "nav.records": "ਰਿਕਾਰਡ",
    "nav.mutations": "ਇੰਤਕਾਲ",
    "nav.possession": "ਕਬਜ਼ਾ",
    "nav.mortgages": "ਰਹਿਨ",
    "nav.calculations": "ਗਿਣਤੀ",
    "nav.evidence": "ਸਬੂਤ",
    "nav.verify": "ਤੁਹਾਡੀ ਮਦਦ ਚਾਹੀਦੀ ਹੈ",
    "nav.ask": "ਡਿਜੀਟਲ ਪਟਵਾਰੀ ਨੂੰ ਪੁੱਛੋ",
    "processing.title": "ਤੁਹਾਡਾ ਦਸਤਾਵੇਜ਼ ਪੜ੍ਹਿਆ ਜਾ ਰਿਹਾ ਹੈ",
    "processing.subtitle": "ਇਸ ਵਿੱਚ ਕੁਝ ਸਮਾਂ ਲੱਗ ਸਕਦਾ ਹੈ। ਤੁਸੀਂ ਇਹ ਸਫ਼ਾ ਖੁੱਲ੍ਹਾ ਰੱਖ ਸਕਦੇ ਹੋ।",
    "processing.retry": "ਨਾ ਪੜ੍ਹੇ ਗਏ ਸਫ਼ਿਆਂ ਨੂੰ ਦੁਬਾਰਾ ਅਜ਼ਮਾਓ",
    "processing.done": "ਨਤੀਜਾ ਵੇਖੋ",
    "summary.title": "ਸਾਰ",
    "summary.viewEvidence": "ਸਬੂਤ ਵੇਖੋ",
    "summary.gates.title": "ਮਿਲਾਨ ਜਾਂਚਾਂ",
    "summary.gates.lead": "ਡਿਜੀਟਲ ਪਟਵਾਰੀ ਰਿਕਾਰਡ ਨੂੰ ਆਪਣੇ ਆਪ ਨਾਲ ਜਾਂਚਦਾ ਹੈ। ਇੱਕ ਜਾਂਚ ਦਾ ਫੇਲ੍ਹ ਹੋਣਾ ਦਾ ਮਤਲਬ ਹੈ ਕਿ ਰਿਕਾਰਡ ਦੇ ਦੋ ਹਿੱਸੇ ਆਪਸ ਵਿੱਚ ਮੇਲ ਨਹੀਂ ਖਾਂਦੇ — ਇਸਦਾ ਮਤਲਬ ਧੋਖਾਧੜੀ ਨਹੀਂ।",
    "summary.pages.title": "ਸਫ਼ੇ",
    "records.title": "ਖੇਵਟ, ਖਤੌਨੀ ਅਤੇ ਖਸਰੇ",
    "records.empty": "ਇਸ ਦਸਤਾਵੇਜ਼ ਵਿੱਚੋਂ ਕੋਈ ਖੇਵਟ ਨਹੀਂ ਪੜ੍ਹਿਆ ਜਾ ਸਕਿਆ।",
    "owner.title": "ਮਾਲਕ",
    "verify.title": "ਤੁਹਾਡੀ ਮਦਦ ਚਾਹੀਦੀ ਹੈ",
    "verify.lead": "ਇਹ ਇੰਦਰਾਜ਼ ਭਰੋਸੇ ਨਾਲ ਨਹੀਂ ਪੜ੍ਹੇ ਜਾ ਸਕੇ। ਤੁਹਾਡਾ ਜਵਾਬ ਅਸਲੀ ਦਸਤਾਵੇਜ਼ ਤੋਂ ਵੱਖਰਾ ਦਰਜ ਕੀਤਾ ਜਾਂਦਾ ਹੈ — ਅਸਲ ਪੜ੍ਹਤ ਹਮੇਸ਼ਾ ਰੱਖੀ ਜਾਂਦੀ ਹੈ।",
    "verify.none": "ਹੁਣ ਤੁਹਾਡੀ ਤਸਦੀਕ ਦੀ ਲੋੜ ਵਾਲਾ ਕੁਝ ਨਹੀਂ ਹੈ।",
    "verify.confirm": "ਹਾਂ, ਇਹ ਸਹੀ ਹੈ",
    "verify.pick": "ਚੁਣੋ",
    "verify.correct": "ਸਹੀ ਮੁੱਲ ਦਰਜ ਕਰੋ",
    "verify.dontknow": "ਮੈਨੂੰ ਨਹੀਂ ਪਤਾ",
    "verify.submit": "ਮੇਰਾ ਜਵਾਬ ਸੰਭਾਲੋ",
    "evidence.title": "ਸਬੂਤ ਦੇਖਣ ਵਾਲਾ",
    "evidence.raw": "ਛਪਿਆ ਪਾਠ",
    "evidence.column": "ਕਾਲਮ",
    "evidence.page": "ਸਫ਼ਾ",
    "evidence.noHighlight": "ਇਸ ਪੜ੍ਹਤ ਲਈ ਸਹੀ ਨਿਸ਼ਾਨ ਉਪਲਬਧ ਨਹੀਂ, ਪਰ ਇਹ ਉਹ ਸਫ਼ਾ ਤੇ ਕਾਲਮ ਹੈ ਜਿੱਥੋਂ ਇਹ ਆਇਆ।",
    "ask.title": "ਡਿਜੀਟਲ ਪਟਵਾਰੀ ਨੂੰ ਪੁੱਛੋ",
    "ask.lead": "ਇਸ ਦਸਤਾਵੇਜ਼ ਬਾਰੇ ਸਵਾਲ ਪੁੱਛੋ। ਜਵਾਬ ਸਿਰਫ਼ ਇੱਥੇ ਪੜ੍ਹੇ ਗਏ ਤੋਂ ਹੀ ਆਉਂਦੇ ਹਨ, ਸਫ਼ੇ ਦਾ ਹਵਾਲਾ ਦਿੰਦੇ ਹਨ, ਅਤੇ ਸਾਫ਼ ਦੱਸਦੇ ਹਨ ਜਦੋਂ ਕੁਝ ਅਸਪੱਸ਼ਟ ਹੋਵੇ।",
    "ask.placeholder": "ਸਵਾਲ ਲਿਖੋ…",
    "ask.send": "ਪੁੱਛੋ",
    "ask.unavailable": "ਇਸ ਦਸਤਾਵੇਜ਼ ਲਈ ਹਾਲੇ ਪੁੱਛਣਾ ਉਪਲਬਧ ਨਹੀਂ।",
    "ask.disclaimer": "ਕਾਨੂੰਨੀ ਸਲਾਹ ਨਹੀਂ — ਮਾਲ ਵਿਭਾਗ ਨਾਲ ਤਸਦੀਕ ਕਰੋ।",
    "calc.title": "ਗਿਣਤੀ",
    "calc.lead": "ਹੇਠਾਂ ਹਰ ਅੰਕੜਾ ਆਪਣੀ ਕੰਮ-ਕਾਜ ਨਾਲ ਦਿਖਾਇਆ ਗਿਆ ਹੈ, ਤਾਂ ਜੋ ਹੱਥੀਂ ਜਾਂਚਿਆ ਜਾ ਸਕੇ।",
    "action.back": "ਪਿੱਛੇ",
    "action.uploadAnother": "ਹੋਰ ਦਸਤਾਵੇਜ਼ ਅਪਲੋਡ ਕਰੋ",
    "action.startOver": "ਮੁੜ ਸ਼ੁਰੂ ਕਰੋ",
    "common.unknown": "ਪਤਾ ਨਹੀਂ",
    "common.notRecorded": "ਦਰਜ ਨਹੀਂ",
  },
};

let current = localStorage.getItem("dp-lang") || "en";

export function setLang(lang) {
  if (!STRINGS[lang]) return;
  current = lang;
  localStorage.setItem("dp-lang", lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = "ltr";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.setAttribute("aria-pressed", String(btn.dataset.lang === current));
  });
  window.dispatchEvent(new CustomEvent("dp-lang-changed", { detail: { lang: current } }));
}

export function getLang() {
  return current;
}

export function t(key) {
  return (STRINGS[current] && STRINGS[current][key]) || STRINGS.en[key] || key;
}
