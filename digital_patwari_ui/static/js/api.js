// Thin fetch wrapper. Every method returns the parsed JSON body; on a
// non-2xx response it throws an ApiError carrying that body, so callers can
// show the server's own citizen-facing message instead of a generic one.

export class ApiError extends Error {
  constructor(status, payload) {
    super(payload && payload.error ? payload.error : `Request failed (${status})`);
    this.status = status;
    this.payload = payload || {};
  }
}

async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  return handleResponse(response);
}

async function handleResponse(response) {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new ApiError(response.status, payload);
  }
  return payload;
}

export const api = {
  health: () => request("GET", "/api/health"),
  scenarios: () => request("GET", "/api/scenarios"),
  createSampleSession: (scenarioKey) => request("POST", "/api/sessions", { scenario_key: scenarioKey }),
  createUploadSession: (files) => request("POST", "/api/sessions", { files }),
  getSession: (id) => request("GET", `/api/sessions/${id}`),
  deleteSession: (id) => request("DELETE", `/api/sessions/${id}`),
  retrySession: (id) => request("POST", `/api/sessions/${id}/retry`),
  verify: (id, payload) => request("POST", `/api/sessions/${id}/verify`, payload),
  ask: (id, question, intent, subject) =>
    request("POST", `/api/sessions/${id}/ask`, { question, intent: intent || null, subject: subject || null }),
  askSuggestions: (id) => request("GET", `/api/sessions/${id}/ask/suggestions`),
};

export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
