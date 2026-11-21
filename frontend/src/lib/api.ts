// In production the site calls its own origin (/backend/...), which Next.js rewrites to the
// FastAPI service set in BACKEND_URL - so the backend can move without rebuilding the client.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "/backend").replace(/\/$/, "");

export type Citation = {
  id: string;
  chunk_id: number;
  document_id: string;
  title: string;
  url: string;
  section: string | null;
  page: number | null;
  excerpt: string;
  academic_year: string | null;
  category: string;
  retrieved_at: string;
  content_type: string;
  score: number;
};

export type ChatResult = {
  message_id: string | null;
  conversation_id: string | null;
  answer: string;
  citations: Citation[];
  sources: Citation[];
  follow_ups: string[];
  mode: "generative" | "extractive" | "insufficient" | "system" | "refusal" | "clarification";
  answered: boolean;
  flags: string[];
  category: string;
  high_stakes: boolean;
  academic_year: string | null;
  timings: { retrieval_ms: number; total_ms: number };
};

export type Stats = {
  documents: number;
  chunks: number;
  pdf_documents: number;
  pdf_pages: number;
  categories: Record<string, number>;
  last_synced: string | null;
  generation: "gemini" | "extractive";
  embedding_model: string;
  current_academic_year: string;
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = undefined;
    let msg = `Request failed (${res.status})`;
    try {
      body = await res.json();
      const d = (body as { detail?: unknown })?.detail;
      if (typeof d === "string") msg = d;
      else if (d && typeof d === "object" && "message" in d) msg = String((d as { message: string }).message);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg, body);
  }
  return res.json() as Promise<T>;
}

export async function api<T>(path: string, init: RequestInit & { token?: string | null } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (init.token) headers.set("Authorization", `Bearer ${init.token}`);
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  return parse<T>(res);
}

export type StreamHandlers = {
  onMeta?: (d: { conversation_id: string | null }) => void;
  onStatus?: (d: { stage: string }) => void;
  onSources?: (sources: Citation[]) => void;
  onToken?: (text: string) => void;
  onReset?: () => void;
  onDone?: (r: ChatResult) => void;
  onError?: (message: string) => void;
};

/** POST + Server-Sent Events reader (EventSource only supports GET). */
export async function streamChat(
  body: {
    question: string;
    client_id: string;
    conversation_id?: string | null;
    filters?: { categories?: string[] | null; academic_year?: string | null };
    regenerate?: boolean;
  },
  h: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const err = await parse<never>(res).catch((e: ApiError) => e);
    h.onError?.(err instanceof Error ? err.message : "Request failed");
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
      }
      if (!data.length) continue;
      let payload: unknown;
      try {
        payload = JSON.parse(data.join("\n"));
      } catch {
        continue;
      }
      const p = payload as Record<string, unknown>;
      switch (event) {
        case "meta": h.onMeta?.(p as { conversation_id: string | null }); break;
        case "status": h.onStatus?.(p as { stage: string }); break;
        case "sources": h.onSources?.((p.sources as Citation[]) || []); break;
        case "token": h.onToken?.(String(p.text ?? "")); break;
        case "reset": h.onReset?.(); break;
        case "done": h.onDone?.(p as unknown as ChatResult); break;
        case "error": h.onError?.(String(p.message ?? "Something went wrong")); break;
      }
    }
  }
}

export function getClientId(): string {
  if (typeof window === "undefined") return "server-render";
  const KEY = "uln_client_id";
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = (crypto.randomUUID?.() || Math.random().toString(36).slice(2) + Date.now().toString(36)).replace(/[^A-Za-z0-9_-]/g, "");
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return "anonymous-session";
  }
}

export const CATEGORY_LABELS: Record<string, string> = {
  qca_grading: "QCA & grading",
  regulations: "Regulations",
  registration: "Registration",
  accommodation: "Accommodation",
  international: "International",
  fees: "Fees",
  scholarships: "Scholarships",
  calendar: "Calendar",
  modules: "Modules",
  library: "Library",
  student_support: "Student support",
  careers: "Careers (CECD)",
  campus: "Campus",
  undergraduate: "Undergraduate study",
  postgraduate: "Postgraduate study",
  general: "General",
};

export const label = (c: string) => CATEGORY_LABELS[c] || c.replace(/_/g, " ");

export function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : d.toLocaleDateString("en-IE", { day: "numeric", month: "short", year: "numeric" });
}
