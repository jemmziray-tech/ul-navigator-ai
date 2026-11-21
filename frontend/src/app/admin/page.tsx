"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity, AlertTriangle, CheckCircle2, Copy, Database, FileUp, Gauge, Loader2, LogOut, MessageCircleQuestion,
  RefreshCw, ScrollText, ThumbsDown, ThumbsUp, Trash2, Wrench,
} from "lucide-react";
import { SiteHeader } from "@/components/site";
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, Select, Skeleton } from "@/components/ui";
import { api, ApiError, CATEGORY_LABELS, fmtDate, label } from "@/lib/api";
import { cn } from "@/lib/utils";

type Overview = {
  documents: { by_status: Record<string, number>; indexed: number; chunks: number };
  coverage: { category: string; documents: number; chunks: number }[];
  jobs: Record<string, number>;
  last_sync: string | null;
  queries_30d: { total: number; answered: number; unanswered: number; modes: Record<string, number>; latency_ms: { p50: number | null; p95: number | null }; retrieval_ms: { p50: number | null; p95: number | null }; avg_citations: number | null };
  feedback: { up: number; down: number };
  conversations: number;
  busy: boolean;
};
type Job = { id: string; kind: string; status: string; started_at: string; finished_at: string | null; stats: Record<string, number>; failure_count: number };
type AdminDoc = { id: string; title: string; url: string; category: string; status: string; academic_year: string | null; content_type: string; chunk_count: number; collected_at: string; error: string | null; duplicate_of: string | null; is_manual: boolean; content_hash: string };

const SECTIONS = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "documents", label: "Sources", icon: Database },
  { id: "jobs", label: "Ingestion jobs", icon: Activity },
  { id: "upload", label: "Upload", icon: FileUp },
  { id: "maintenance", label: "Maintenance", icon: Wrench },
  { id: "questions", label: "Unanswered & feedback", icon: MessageCircleQuestion },
  { id: "logs", label: "Logs", icon: ScrollText },
] as const;
type SectionId = (typeof SECTIONS)[number]["id"];

function Login({ onToken }: { onToken: (t: string) => void }) {
  const [u, setU] = useState("admin");
  const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <Card className="mx-auto mt-16 max-w-sm p-6">
      <h1 className="font-display text-2xl font-semibold">Admin sign in</h1>
      <p className="mt-1 text-sm text-muted">Restricted to the project maintainer.</p>
      <form
        className="mt-6 space-y-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setErr(null);
          try {
            const r = await api<{ access_token: string }>("/api/admin/login", { method: "POST", body: JSON.stringify({ username: u, password: p }) });
            sessionStorage.setItem("uln_admin", r.access_token);
            onToken(r.access_token);
          } catch (e2) {
            setErr(e2 instanceof ApiError && e2.status === 503 ? "Admin access isn't configured on the server (set ADMIN_PASSWORD_HASH and JWT_SECRET)." : (e2 as Error).message);
          } finally { setBusy(false); }
        }}
      >
        <label className="block text-sm"><span className="mb-1 block text-muted">Username</span><Input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" /></label>
        <label className="block text-sm"><span className="mb-1 block text-muted">Password</span><Input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" /></label>
        {err ? <ErrorBanner message={err} /> : null}
        <Button type="submit" className="w-full" disabled={busy || !p}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Sign in</Button>
      </form>
    </Card>
  );
}

function Stat({ k, v, sub }: { k: string; v: React.ReactNode; sub?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-muted">{k}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{v}</p>
      {sub ? <p className="mt-0.5 text-xs text-muted">{sub}</p> : null}
    </Card>
  );
}

export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [section, setSection] = useState<SectionId>("overview");
  const [ov, setOv] = useState<Overview | null>(null);
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [jobDetail, setJobDetail] = useState<{ id: string; failures: { url: string; stage: string; error: string }[] } | null>(null);
  const [docs, setDocs] = useState<{ total: number; items: AdminDoc[] } | null>(null);
  const [docStatus, setDocStatus] = useState("");
  const [docQ, setDocQ] = useState("");
  const [unanswered, setUnanswered] = useState<{ question: string; category: string; created_at: string; flags: string[] }[] | null>(null);
  const [feedback, setFeedback] = useState<{ rating: number; comment: string | null; created_at: string; answer_excerpt: string; category: string }[] | null>(null);
  const [dups, setDups] = useState<{ id: string; url: string; title: string; duplicate_of: string }[] | null>(null);
  const [logs, setLogs] = useState<string[] | null>(null);
  const [msg, setMsg] = useState<{ tone: "ok" | "err"; text: string } | null>(null);
  const [working, setWorking] = useState(false);

  useEffect(() => { setToken(sessionStorage.getItem("uln_admin")); }, []);

  const call = useCallback(async <T,>(path: string, init: RequestInit = {}) => {
    try {
      return await api<T>(path, { ...init, token });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { sessionStorage.removeItem("uln_admin"); setToken(null); }
      throw e;
    }
  }, [token]);

  const loadSection = useCallback(async (s: SectionId) => {
    if (!token) return;
    try {
      if (s === "overview") setOv(await call<Overview>("/api/admin/overview"));
      if (s === "jobs") setJobs(await call<Job[]>("/api/admin/jobs"));
      if (s === "documents") {
        const sp = new URLSearchParams();
        if (docStatus) sp.set("status", docStatus);
        if (docQ) sp.set("q", docQ);
        setDocs(await call(`/api/admin/documents?${sp}`));
      }
      if (s === "questions") {
        setUnanswered(await call("/api/admin/unanswered"));
        setFeedback(await call("/api/admin/feedback"));
      }
      if (s === "maintenance") setDups(await call("/api/admin/duplicates"));
      if (s === "logs") setLogs((await call<{ lines: string[] }>("/api/admin/logs?lines=300")).lines);
    } catch (e) {
      setMsg({ tone: "err", text: (e as Error).message });
    }
  }, [token, call, docStatus, docQ]);

  useEffect(() => { loadSection(section); }, [section, loadSection]);

  const action = async (path: string, okText: string, method = "POST") => {
    setWorking(true); setMsg(null);
    try {
      const r = await call<Record<string, unknown>>(path, { method, body: method === "POST" ? "{}" : undefined });
      setMsg({ tone: "ok", text: `${okText} ${JSON.stringify(r)}` });
      loadSection(section);
    } catch (e) { setMsg({ tone: "err", text: (e as Error).message }); }
    finally { setWorking(false); }
  };

  if (!token) return (<><SiteHeader /><main id="main" className="px-4"><Login onToken={setToken} /></main></>);

  return (
    <>
      <SiteHeader />
      <main id="main" className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight">Administration</h1>
            <p className="text-sm text-muted">Knowledge base health, ingestion and usage analytics.</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => { sessionStorage.removeItem("uln_admin"); setToken(null); }}><LogOut className="h-4 w-4" /> Sign out</Button>
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-[220px_1fr]">
          <nav className="flex gap-1 overflow-x-auto lg:flex-col" aria-label="Admin sections">
            {SECTIONS.map(({ id, label: l, icon: Icon }) => (
              <button key={id} onClick={() => setSection(id)} aria-current={section === id ? "page" : undefined}
                className={cn("inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-left text-sm", section === id ? "bg-forest text-white" : "hover:bg-surface-2")}>
                <Icon className="h-4 w-4" /> {l}
              </button>
            ))}
          </nav>
          <div className="min-w-0 space-y-4">
            {msg ? (
              <div className={cn("flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm", msg.tone === "ok" ? "border-emerald/40 bg-emerald-soft" : "border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200")}>
                <span className="break-all">{msg.text}</span>
                <button onClick={() => setMsg(null)} className="text-xs underline">Dismiss</button>
              </div>
            ) : null}

            {section === "overview" && (ov ? (
              <>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <Stat k="Indexed documents" v={ov.documents.indexed} sub={`${ov.documents.by_status.failed || 0} failed · ${ov.documents.by_status.duplicate || 0} duplicates`} />
                  <Stat k="Chunks" v={ov.documents.chunks.toLocaleString()} />
                  <Stat k="Jobs (success / partial / failed)" v={`${ov.jobs.success || 0} / ${ov.jobs.partial || 0} / ${ov.jobs.failed || 0}`} />
                  <Stat k="Last synchronisation" v={<span className="text-lg">{fmtDate(ov.last_sync)}</span>} sub={ov.busy ? "A job is running now" : undefined} />
                  <Stat k="Questions (30 days)" v={ov.queries_30d.total} sub={`${ov.queries_30d.unanswered} without reliable evidence`} />
                  <Stat k="Latency p50 / p95" v={<span className="text-lg">{ov.queries_30d.latency_ms.p50 ?? "—"} / {ov.queries_30d.latency_ms.p95 ?? "—"} ms</span>} sub={`retrieval p50 ${ov.queries_30d.retrieval_ms.p50 ?? "—"} ms`} />
                  <Stat k="Avg. citations per answer" v={ov.queries_30d.avg_citations ?? "—"} />
                  <Stat k="Feedback" v={<span className="inline-flex items-center gap-3 text-lg"><span className="inline-flex items-center gap-1"><ThumbsUp className="h-4 w-4 text-emerald" />{ov.feedback.up}</span><span className="inline-flex items-center gap-1"><ThumbsDown className="h-4 w-4 text-danger" />{ov.feedback.down}</span></span>} />
                </div>
                <Card className="p-5">
                  <h2 className="font-semibold">Source coverage by category</h2>
                  {ov.coverage.length === 0 ? <p className="mt-2 text-sm text-muted">Nothing indexed yet.</p> : (
                    <ul className="mt-4 space-y-2">
                      {ov.coverage.map((c) => {
                        const max = Math.max(...ov.coverage.map((x) => x.documents));
                        return (
                          <li key={c.category} className="grid grid-cols-[150px_1fr_110px] items-center gap-3 text-sm">
                            <span className="truncate">{label(c.category)}</span>
                            <div className="h-2 rounded-full bg-surface-2"><div className="h-2 rounded-full bg-emerald" style={{ width: `${(c.documents / max) * 100}%` }} /></div>
                            <span className="text-right text-xs tabular-nums text-muted">{c.documents} docs · {c.chunks} chunks</span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Card>
                {Object.keys(ov.queries_30d.modes).length ? (
                  <Card className="p-5 text-sm">
                    <h2 className="font-semibold">Answer modes (30 days)</h2>
                    <div className="mt-3 flex flex-wrap gap-2">{Object.entries(ov.queries_30d.modes).map(([k, v]) => <Badge key={k}>{k}: {v}</Badge>)}</div>
                  </Card>
                ) : null}
              </>
            ) : <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>)}

            {section === "documents" && (
              <Card className="p-4">
                <form className="mb-4 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); loadSection("documents"); }}>
                  <Input value={docQ} onChange={(e) => setDocQ(e.target.value)} placeholder="Search title or URL" className="max-w-xs" aria-label="Search sources" />
                  <Select value={docStatus} onChange={(e) => setDocStatus(e.target.value)} aria-label="Status">
                    <option value="">All statuses</option><option value="indexed">Indexed</option><option value="failed">Failed</option><option value="duplicate">Duplicate</option>
                  </Select>
                  <Button type="submit" variant="outline">Apply</Button>
                </form>
                {!docs ? <Skeleton className="h-40" /> : docs.items.length === 0 ? <EmptyState title="No documents" /> : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-left text-xs text-muted"><tr><th className="p-2">Title</th><th className="p-2">Status</th><th className="p-2">Category</th><th className="p-2">Year</th><th className="p-2">Chunks</th><th className="p-2">Collected</th><th className="p-2">Hash</th><th className="p-2" /></tr></thead>
                      <tbody>
                        {docs.items.map((d) => (
                          <tr key={d.id} className="border-t border-border align-top">
                            <td className="max-w-[320px] p-2">
                              <a href={d.url.startsWith("http") ? d.url : undefined} target="_blank" rel="noopener noreferrer" className="line-clamp-1 font-medium hover:underline">{d.title}</a>
                              <p className="line-clamp-1 text-xs text-muted">{d.url}</p>
                              {d.error ? <p className="mt-1 text-xs text-danger">{d.error}</p> : null}
                            </td>
                            <td className="p-2"><Badge tone={d.status === "indexed" ? "green" : d.status === "failed" ? "danger" : "warn"}>{d.status}</Badge></td>
                            <td className="p-2">{label(d.category)}</td>
                            <td className="p-2">{d.academic_year || "—"}</td>
                            <td className="p-2 tabular-nums">{d.chunk_count}</td>
                            <td className="p-2 whitespace-nowrap">{fmtDate(d.collected_at)}</td>
                            <td className="p-2 font-mono text-xs text-muted">{d.content_hash}</td>
                            <td className="p-2">
                              <Button variant="ghost" size="icon" aria-label={`Delete ${d.title}`} onClick={() => { if (confirm(`Delete "${d.title}" and its vectors from the index?`)) action(`/api/admin/documents/${d.id}`, "Deleted.", "DELETE"); }}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="mt-3 text-xs text-muted">{docs.total} total</p>
                  </div>
                )}
              </Card>
            )}

            {section === "jobs" && (
              <Card className="p-4">
                {!jobs ? <Skeleton className="h-40" /> : jobs.length === 0 ? <EmptyState title="No ingestion jobs yet">Run <code>python -m ul_ingest crawl</code> or start a crawl from Maintenance.</EmptyState> : (
                  <ul className="divide-y divide-border">
                    {jobs.map((j) => (
                      <li key={j.id} className="py-3 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          {j.status === "success" ? <CheckCircle2 className="h-4 w-4 text-emerald" /> : j.status === "running" ? <Loader2 className="h-4 w-4 animate-spin" /> : <AlertTriangle className="h-4 w-4 text-warning" />}
                          <span className="font-medium capitalize">{j.kind}</span>
                          <Badge tone={j.status === "success" ? "green" : j.status === "failed" ? "danger" : "warn"}>{j.status}</Badge>
                          <span className="text-xs text-muted">{new Date(j.started_at).toLocaleString("en-IE")}</span>
                          {j.failure_count ? (
                            <Button variant="ghost" size="sm" onClick={async () => setJobDetail(await call(`/api/admin/jobs/${j.id}`))}>{j.failure_count} failure(s)</Button>
                          ) : null}
                        </div>
                        <p className="mt-1 font-mono text-xs text-muted">{Object.entries(j.stats || {}).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join("  ")}</p>
                        {jobDetail?.id === j.id ? (
                          <ul className="mt-2 space-y-1 rounded-lg bg-surface-2 p-3 text-xs">
                            {jobDetail.failures.map((f, i) => <li key={i}><Badge>{f.stage}</Badge> <span className="break-all">{f.url}</span> — <span className="text-danger">{f.error}</span></li>)}
                          </ul>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            )}

            {section === "upload" && (
              <Card className="p-5">
                <h2 className="font-semibold">Upload an authorised document</h2>
                <p className="mt-1 text-sm text-muted">PDF, CSV (e.g. Book of Modules exports), RTF, TXT or MD. Files are validated, deduplicated and indexed incrementally.</p>
                <form
                  className="mt-5 grid gap-3 sm:grid-cols-2"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const fd = new FormData(e.currentTarget);
                    setWorking(true); setMsg(null);
                    try {
                      const r = await call<{ status: string; chunks_added: number }>("/api/admin/upload", { method: "POST", body: fd });
                      setMsg({ tone: "ok", text: `Upload ${r.status}: ${r.chunks_added} chunks added.` });
                      (e.target as HTMLFormElement).reset();
                    } catch (e2) { setMsg({ tone: "err", text: (e2 as Error).message }); }
                    finally { setWorking(false); }
                  }}
                >
                  <label className="text-sm sm:col-span-2"><span className="mb-1 block text-muted">File</span><input name="file" type="file" required accept=".pdf,.csv,.rtf,.txt,.md" className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-soft file:px-3 file:py-2 file:text-forest" /></label>
                  <label className="text-sm"><span className="mb-1 block text-muted">Title</span><Input name="title" placeholder="Document title" /></label>
                  <label className="text-sm"><span className="mb-1 block text-muted">Category</span>
                    <Select name="category" defaultValue="modules" className="w-full">{Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
                  </label>
                  <label className="text-sm"><span className="mb-1 block text-muted">Academic year</span><Input name="academic_year" placeholder="2026/27" pattern="20\d{2}/\d{2}" /></label>
                  <label className="text-sm"><span className="mb-1 block text-muted">Official source URL (optional)</span><Input name="source_url" type="url" placeholder="https://www.ul.ie/…" /></label>
                  <div className="sm:col-span-2"><Button type="submit" disabled={working}>{working ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />} Upload &amp; index</Button></div>
                </form>
              </Card>
            )}

            {section === "maintenance" && (
              <>
                <Card className="p-5">
                  <h2 className="font-semibold">Index operations</h2>
                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-border p-4 text-sm">
                      <p className="font-medium">Incremental crawl</p>
                      <p className="mt-1 text-muted">Re-fetch sources; only changed content (by hash) is re-embedded.</p>
                      <Button className="mt-3" size="sm" disabled={working} onClick={() => action("/api/admin/crawl", "Crawl started in the background.")}><RefreshCw className="h-4 w-4" /> Start crawl</Button>
                    </div>
                    <div className="rounded-xl border border-border p-4 text-sm">
                      <p className="font-medium">Reconcile index</p>
                      <p className="mt-1 text-muted">Remove orphan vectors and embed any chunks missing from FAISS.</p>
                      <Button className="mt-3" size="sm" variant="outline" disabled={working} onClick={() => action("/api/admin/reconcile", "Reconciled.")}>Reconcile</Button>
                    </div>
                    <div className="rounded-xl border border-border p-4 text-sm">
                      <p className="font-medium">Full re-index</p>
                      <p className="mt-1 text-muted">Re-embed every chunk — needed after changing the embedding model.</p>
                      <Button className="mt-3" size="sm" variant="outline" disabled={working} onClick={() => { if (confirm("Re-embed every chunk? This can take a while.")) action("/api/admin/reindex", "Re-index started."); }}>Re-index all</Button>
                    </div>
                  </div>
                </Card>
                <Card className="p-5">
                  <h2 className="flex items-center gap-2 font-semibold"><Copy className="h-4 w-4" /> Duplicate detection</h2>
                  {!dups ? <Skeleton className="mt-3 h-16" /> : dups.length === 0 ? <p className="mt-2 text-sm text-muted">No duplicate documents detected.</p> : (
                    <ul className="mt-3 space-y-1 text-sm">{dups.map((d) => <li key={d.id} className="break-all"><b>{d.title}</b> — {d.url} <span className="text-muted">(duplicate of {d.duplicate_of.slice(0, 10)}…)</span></li>)}</ul>
                  )}
                </Card>
              </>
            )}

            {section === "questions" && (
              <div className="grid gap-4 xl:grid-cols-2">
                <Card className="p-5">
                  <h2 className="font-semibold">Unanswered questions</h2>
                  <p className="text-xs text-muted">Questions where no reliable source was retrieved — candidates for new sources.</p>
                  {!unanswered ? <Skeleton className="mt-3 h-32" /> : unanswered.length === 0 ? <p className="mt-3 text-sm text-muted">None yet.</p> : (
                    <ul className="mt-3 divide-y divide-border text-sm">{unanswered.map((u, i) => <li key={i} className="py-2"><p>{u.question}</p><p className="text-xs text-muted">{label(u.category)} · {fmtDate(u.created_at)}</p></li>)}</ul>
                  )}
                </Card>
                <Card className="p-5">
                  <h2 className="font-semibold">Recent feedback</h2>
                  {!feedback ? <Skeleton className="mt-3 h-32" /> : feedback.length === 0 ? <p className="mt-3 text-sm text-muted">No feedback yet.</p> : (
                    <ul className="mt-3 divide-y divide-border text-sm">{feedback.map((f, i) => (
                      <li key={i} className="flex gap-2 py-2">{f.rating > 0 ? <ThumbsUp className="mt-0.5 h-4 w-4 shrink-0 text-emerald" /> : <ThumbsDown className="mt-0.5 h-4 w-4 shrink-0 text-danger" />}
                        <div><p className="line-clamp-2">{f.answer_excerpt}</p><p className="text-xs text-muted">{f.category ? label(f.category) + " · " : ""}{fmtDate(f.created_at)}</p></div></li>
                    ))}</ul>
                  )}
                </Card>
              </div>
            )}

            {section === "logs" && (
              <Card className="p-4">
                <div className="mb-2 flex justify-between"><h2 className="font-semibold">Ingestion log</h2><Button size="sm" variant="ghost" onClick={() => loadSection("logs")}><RefreshCw className="h-4 w-4" /></Button></div>
                {!logs ? <Skeleton className="h-64" /> : logs.length === 0 ? <p className="text-sm text-muted">No log entries yet.</p> : (
                  <pre className="max-h-[60vh] overflow-auto rounded-xl bg-[#0f1412] p-4 font-mono text-[11px] leading-relaxed text-[#cfe3d8] scrollbar-thin">{logs.join("\n")}</pre>
                )}
              </Card>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
