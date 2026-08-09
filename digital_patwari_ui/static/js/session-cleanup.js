// Best-effort server-side cleanup before a citizen leaves a session
// (Upload another document / start over). Always calls the DELETE session
// API first, per P1: the server removes the session and its temporary
// uploaded files. It never blocks or fails the navigation home -- a
// network hiccup, or a session that's already gone, still lets the
// citizen leave cleanly. Any non-alarming cleanup_warning the server
// returns is passed back to the caller to show, never as an error state.

import { api } from "./api.js";

export async function leaveSession(sessionId) {
  if (!sessionId) return null;
  try {
    const result = await api.deleteSession(sessionId);
    return (result && result.cleanup_warning) || null;
  } catch (err) {
    // Best-effort: the citizen is leaving regardless. The server's own
    // bounded expiry sweep will clear an orphaned session later.
    return null;
  }
}
