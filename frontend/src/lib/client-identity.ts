/** Browser identity for anonymous conversation access; never share a storage-failure ID. */
export function createClientIdentity() {
  let sessionId: string | undefined;
  return function getIdentity(): string {
    if (typeof window === "undefined") return "server-render";
    if (sessionId) return sessionId;
    try {
      const saved = window.localStorage.getItem("uln_client_id");
      if (saved && /^[A-Za-z0-9_-]{16,128}$/.test(saved) && saved !== "anonymous-session") {
        sessionId = saved;
        return saved;
      }
    } catch { /* Storage may be blocked; retain a private identity in memory instead. */ }
    sessionId = typeof crypto.randomUUID === "function" ? crypto.randomUUID() :
      Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("");
    try { window.localStorage.setItem("uln_client_id", sessionId); } catch { /* Session-only identity. */ }
    return sessionId;
  };
}

export const getClientId = createClientIdentity();
