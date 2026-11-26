"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle, ArrowUp, Check, Copy, Loader2, MessageSquarePlus, PanelLeftClose, PanelLeftOpen,
  RefreshCw, SlidersHorizontal, Square, ThumbsDown, ThumbsUp, Trash2, X,
} from "lucide-react";
import { Logo, ThemeToggle, DISCLAIMER, UniversityResourceMark } from "@/components/site";
import { Badge, Button, ErrorBanner, Select, Tip } from "@/components/ui";
import { Markdown } from "@/components/chat/markdown";
import { CitationCard, SourcePreview } from "@/components/chat/citations";
import { api, CATEGORY_LABELS, getClientId, streamChat, type ChatResult, type Citation } from "@/lib/api";
import { ProgressiveReply } from "@/lib/progressive-reply";
import { cn } from "@/lib/utils";

type Msg = {
  key: string;
  role: "user" | "assistant";
  content: string;
  id?: string | null;
  citations?: Citation[];
  sources?: Citation[];
  followUps?: string[];
  mode?: ChatResult["mode"];
  flags?: string[];
  highStakes?: boolean;
  streaming?: boolean;
  stage?: string;
  error?: string;
  rating?: 1 | -1;
};
type ConvSummary = { id: string; title: string; updated_at: string };

const STAGES: Record<string, string> = {
  classifying: "Understanding your question…",
  retrieving: "Searching official UL sources…",
  generating: "Writing a grounded answer…",
};

const STARTERS = [
  "What QCA do I need for first class honours?",
  "When are the end-of-semester exams in 2026/27?",
  "How do I pay my accommodation fees?",
  "What should I do after arriving in Ireland as an international student?",
];

const uid = () => Math.random().toString(36).slice(2);

function ChatWorkspace() {
  const params = useSearchParams();
  const router = useRouter();
  const [clientId, setClientId] = useState("");
  const [convs, setConvs] = useState<ConvSummary[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sidebar, setSidebar] = useState(true);
  const [mobileSidebar, setMobileSidebar] = useState(false);
  const [preview, setPreview] = useState<Citation | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [category, setCategory] = useState("");
  const [year, setYear] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const followBottom = useRef(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const autoSent = useRef(false);

  const [years, setYears] = useState<string[]>([]);
  useEffect(() => setClientId(getClientId()), []);
  useEffect(() => {
    api<{ years: string[] }>("/api/sources?size=1").then((r) => setYears(r.years)).catch(() => {});
  }, []);

  const refreshConvs = useCallback(async () => {
    if (!clientId) return;
    try {
      setConvs(await api<ConvSummary[]>(`/api/conversations?client_id=${clientId}`));
      setLoadErr(null);
    } catch {
      setLoadErr("Couldn't load your chat history. Please check your connection and try again.");
    }
  }, [clientId]);

  useEffect(() => { refreshConvs(); }, [refreshConvs]);

  useEffect(() => {
    if (followBottom.current) bottomRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
  }, [messages]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const loadConversation = useCallback(async (id: string) => {
    if (!clientId) return;
    abortRef.current?.abort();
    try {
      const c = await api<{ id: string; messages: { id: string; role: "user" | "assistant"; content: string; citations: Citation[]; meta: Record<string, unknown> }[] }>(
        `/api/conversations/${id}?client_id=${clientId}`,
      );
      setConvId(c.id);
      setMessages(
        c.messages.map((m) => ({
          key: m.id, id: m.id, role: m.role, content: m.content, citations: m.citations || [],
          followUps: (m.meta?.follow_ups as string[]) || [], mode: m.meta?.mode as ChatResult["mode"],
          flags: (m.meta?.flags as string[]) || [],
        })),
      );
      setMobileSidebar(false);
    } catch {
      setLoadErr("That conversation could not be loaded.");
    }
  }, [clientId]);

  const newChat = () => {
    abortRef.current?.abort();
    setConvId(null);
    setMessages([]);
    setMobileSidebar(false);
    router.replace("/chat");
    taRef.current?.focus();
  };

  const send = useCallback(
    async (text: string, opts: { regenerate?: boolean } = {}) => {
      const question = text.trim();
      if (!question || busy || !clientId) return;
      followBottom.current = true;
      setBusy(true);
      setInput("");
      const aKey = uid();
      setMessages((prev) => {
        let base = prev;
        if (opts.regenerate) {
          base = prev[prev.length - 1]?.role === "assistant" ? prev.slice(0, -1) : prev;
        } else {
          base = [...prev, { key: uid(), role: "user", content: question }];
        }
        return [...base, { key: aKey, role: "assistant", content: "", streaming: true, stage: "classifying" }];
      });
      const patch = (p: Partial<Msg> | ((m: Msg) => Partial<Msg>)) =>
        setMessages((prev) => prev.map((m) => (m.key === aKey ? { ...m, ...(typeof p === "function" ? p(m) : p) } : m)));
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      let receivedDone = false;
      let receivedError = false;
      let drain = Promise.resolve();
      const reveal = new ProgressiveReply(content => patch({ content, stage: "generating" }), 32,
        window.matchMedia("(prefers-reduced-motion: reduce)").matches);
      const cancelReveal = () => reveal.cancel();
      ctrl.signal.addEventListener("abort", cancelReveal, { once: true });
      try {
        await streamChat(
          {
            question, client_id: clientId, conversation_id: convId, regenerate: opts.regenerate,
            filters: { categories: category ? [category] : null, academic_year: year || null },
          },
          {
            onMeta: (d) => { if (d.conversation_id) setConvId(d.conversation_id); },
            onStatus: (d) => patch({ stage: d.stage }),
            onSources: (s) => patch({ sources: s, citations: s }),
            onToken: (t) => reveal.append(t),
            onReset: () => reveal.reset(),
            onDone: (r) => {
              receivedDone = true;
              drain = reveal.finish(r.answer);
              patch({ citations: r.citations, sources: r.sources, followUps: r.follow_ups,
                mode: r.mode, flags: r.flags, highStakes: r.high_stakes, id: r.message_id, streaming: true,
              });
              if (r.conversation_id) setConvId(r.conversation_id);
            },
            onError: (msg) => { receivedError = true; reveal.cancel(); patch({ error: msg, streaming: false }); },
          },
          ctrl.signal,
        );
        await drain;
        if (ctrl.signal.aborted) throw new DOMException("Stopped", "AbortError");
        if (!receivedDone && !receivedError) throw new Error("The answer stream ended before verification");
      } catch (e) {
        if ((e as Error).name === "AbortError") patch((m) => ({ streaming: false, content: m.content ? `${m.content}\n\n_Stopped._` : "_Stopped._" }));
        else patch({ streaming: false, error: "Couldn't reach the UL Navigator API. Please check your connection and try again." });
      } finally {
        reveal.cancel();
        ctrl.signal.removeEventListener("abort", cancelReveal);
        patch((m) => (m.streaming ? { streaming: false } : {}));
        setBusy(false);
        abortRef.current = null;
        refreshConvs();
      }
    },
    [busy, clientId, convId, category, year, refreshConvs],
  );

  // landing page hand-off (?q=...) and deep links (?c=...)
  useEffect(() => {
    if (!clientId || autoSent.current) return;
    const q = params.get("q");
    const c = params.get("c");
    if (c) { autoSent.current = true; loadConversation(c); }
    else if (q) { autoSent.current = true; send(q); }
  }, [clientId, params, send, loadConversation]);

  const stop = () => abortRef.current?.abort();

  const rate = async (m: Msg, rating: 1 | -1) => {
    if (!m.id || m.rating) return;
    setMessages((prev) => prev.map((x) => (x.key === m.key ? { ...x, rating } : x)));
    try { await api("/api/feedback", { method: "POST", body: JSON.stringify({ message_id: m.id, rating }) }); } catch { /* non-critical */ }
  };

  const copy = async (m: Msg) => {
    const plain = m.content.replace(/\[S\d+\]/g, "");
    const refs = (m.citations || []).map((c) => `[${c.id}] ${c.title} — ${c.url}`).join("\n");
    await navigator.clipboard.writeText(refs ? `${plain}\n\nSources:\n${refs}` : plain);
    setCopied(m.key);
    setTimeout(() => setCopied(null), 1500);
  };

  const removeConv = async (id: string) => {
    try {
      await api(`/api/conversations/${id}?client_id=${clientId}`, { method: "DELETE" });
      if (id === convId) newChat();
      refreshConvs();
    } catch { setLoadErr("Couldn't delete that conversation."); }
  };

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const lastUser = [...messages].reverse().find((m) => m.role === "user");

  const Sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between px-3">
        <Link href="/" aria-label="Home"><Logo /></Link>
        <Button variant="ghost" size="icon" className="hidden md:inline-flex" aria-label="Collapse sidebar" onClick={() => setSidebar(false)}>
          <PanelLeftClose className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Close sidebar" onClick={() => setMobileSidebar(false)}>
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="px-3">
        <Button className="w-full" onClick={newChat}><MessageSquarePlus className="h-4 w-4" /> New conversation</Button>
      </div>
      <nav className="mt-4 flex-1 overflow-y-auto px-2 scrollbar-thin" aria-label="Conversation history">
        <p className="px-2 pb-2 text-[11px] font-medium uppercase tracking-wider text-muted">History</p>
        {convs.length === 0 ? (
          <p className="px-2 text-sm text-muted">Your conversations will appear here.</p>
        ) : (
          <ul className="space-y-0.5">
            {convs.map((c) => (
              <li key={c.id} className="group relative">
                <button
                  onClick={() => loadConversation(c.id)}
                  className={cn("w-full truncate rounded-lg px-2.5 py-2 pr-8 text-left text-sm hover:bg-surface-2", c.id === convId && "bg-surface-2 font-medium")}
                  aria-current={c.id === convId ? "page" : undefined}
                >
                  {c.title}
                </button>
                <button
                  onClick={() => removeConv(c.id)}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted opacity-0 hover:text-danger focus:opacity-100 group-hover:opacity-100"
                  aria-label={`Delete conversation ${c.title}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>
      <div className="space-y-3 border-t border-border p-3 text-[11px] leading-snug text-muted"><UniversityResourceMark compact /><p>{DISCLAIMER}</p><Link href="/privacy" className="inline-block underline underline-offset-2">Privacy &amp; your conversations</Link></div>
    </div>
  );

  return (
    <div className="flex h-dvh overflow-hidden">
      {/* desktop sidebar */}
      <AnimatePresence initial={false}>
        {sidebar && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="hidden shrink-0 overflow-hidden border-r border-border bg-surface md:block"
          >
            <div className="h-full w-[280px]">{Sidebar}</div>
          </motion.aside>
        )}
      </AnimatePresence>
      {/* mobile drawer */}
      <AnimatePresence>
        {mobileSidebar && (
          <>
            <motion.div className="fixed inset-0 z-40 bg-black/40 md:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobileSidebar(false)} />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-[85vw] max-w-[300px] border-r border-border bg-surface md:hidden"
              initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }} transition={{ type: "spring", damping: 30, stiffness: 300 }}
            >
              {Sidebar}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-border px-3">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            {!sidebar && (
              <Button variant="ghost" size="icon" className="hidden md:inline-flex" aria-label="Expand sidebar" onClick={() => setSidebar(true)}>
                <PanelLeftOpen className="h-4 w-4" />
              </Button>
            )}
            <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open conversation history" onClick={() => setMobileSidebar(true)}>
              <PanelLeftOpen className="h-4 w-4" />
            </Button>
            <UniversityResourceMark header />
            <span className="min-w-0 truncate text-sm font-medium">{convs.find((c) => c.id === convId)?.title || "New conversation"}</span>
          </div>
          <div className="flex items-center gap-1">
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex"><Link href="/exams">Exams</Link></Button>
            <Button asChild variant="ghost" size="sm"><Link href="/courses">Courses</Link></Button>
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex"><Link href="/explorer">Sources</Link></Button>
            <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex"><Link href="/tools">Tools</Link></Button>
            <ThemeToggle />
          </div>
        </header>

        <p className="sr-only" role="status">{busy ? "Writing your answer. Use Stop to pause." : "Ready for your question."}</p>
        <main id="main" className="flex-1 overflow-y-auto scrollbar-thin" onScroll={e => { const el = e.currentTarget; followBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; }}>
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
            {loadErr ? <div className="mb-4"><ErrorBanner message={loadErr} onRetry={refreshConvs} /></div> : null}
            {messages.length === 0 ? (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="pt-[10vh] text-center">
                <h1 className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">How can I help you at UL?</h1>
                <p className="mx-auto mt-3 max-w-lg text-muted">I answer from official University of Limerick pages and documents, and I'll show you the source for every fact.</p>
                <div className="mx-auto mt-8 grid max-w-2xl gap-2 sm:grid-cols-2">
                  {STARTERS.map((s) => (
                    <button key={s} onClick={() => send(s)} className="rounded-xl border border-border bg-surface p-3 text-left text-sm transition hover:border-emerald/60 hover:shadow-sm">
                      {s}
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <ol className="space-y-8">
                {messages.map((m) => (
                  <motion.li key={m.key} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
                    {m.role === "user" ? (
                      <div className="flex justify-end">
                        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-forest px-4 py-2.5 text-[0.95rem] text-white">{m.content}</div>
                      </div>
                    ) : (
                      <div className="flex gap-3">
                        <div className="mt-0.5 hidden h-8 w-8 shrink-0 place-items-center rounded-full border border-border bg-surface sm:grid" aria-hidden>
                          <svg viewBox="0 0 32 32" className="h-5 w-5"><path d="M16 5l3.4 11L16 27l-3.4-11L16 5Z" fill="var(--emerald)" /></svg>
                        </div>
                        <div className="min-w-0 flex-1">
                          {(m.mode || m.highStakes || (m.flags?.length ?? 0) > 0) && !m.streaming ? (
                            <div className="mb-2 flex flex-wrap gap-1.5">
                              {m.mode === "clarification" && <Badge tone="green">Just one detail</Badge>}
                              {m.mode === "extractive" && <Badge tone="warn">Extractive mode — quoting sources directly</Badge>}
                              {m.mode === "insufficient" && <Badge tone="warn"><AlertTriangle className="h-3 w-3" /> Not enough evidence</Badge>}
                              {m.highStakes && <Badge tone="danger">High-stakes topic — verify with UL</Badge>}
                              {m.flags?.includes("year_mismatch") && <Badge tone="warn">Different academic year</Badge>}
                              {m.flags?.includes("unverified_figures") && <Badge tone="warn">Some figures unverified</Badge>}
                            </div>
                          ) : null}
                          {m.error ? (
                            <ErrorBanner message={m.error} onRetry={lastUser ? () => send(lastUser.content, { regenerate: true }) : undefined} />
                          ) : m.content ? (
                            <div className={cn(m.streaming && "typing-caret")} aria-busy={m.streaming}>
                              <Markdown content={m.content} citations={m.citations || []} onCite={setPreview} />
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 text-sm text-muted" role="status">
                              <Loader2 className="h-4 w-4 animate-spin text-emerald" /> {STAGES[m.stage || "classifying"] || "Working…"}
                            </div>
                          )}

                          {!m.streaming && m.citations && m.citations.length > 0 ? (
                            <section className="mt-4" aria-label="Sources">
                              <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted">Sources</p>
                              <div className="grid gap-2 sm:grid-cols-2">
                                {m.citations.map((c, i) => <CitationCard key={c.id} c={c} index={i} onOpen={setPreview} />)}
                              </div>
                            </section>
                          ) : null}

                          {!m.streaming && !m.error && m.content ? (
                            <div className="mt-3 flex flex-wrap items-center gap-1 text-muted">
                              <Tip label={copied === m.key ? "Copied" : "Copy answer"}>
                                <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Copy answer" onClick={() => copy(m)}>
                                  {copied === m.key ? <Check className="h-4 w-4 text-emerald" /> : <Copy className="h-4 w-4" />}
                                </Button>
                              </Tip>
                              {m.key === lastAssistant?.key && lastUser ? (
                                <Tip label="Regenerate">
                                  <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Regenerate answer" disabled={busy} onClick={() => send(lastUser.content, { regenerate: true })}>
                                    <RefreshCw className="h-4 w-4" />
                                  </Button>
                                </Tip>
                              ) : null}
                              {m.id ? (
                                <>
                                  <Tip label="Helpful">
                                    <Button variant="ghost" size="icon" className={cn("h-8 w-8", m.rating === 1 && "text-emerald")} aria-label="Helpful" aria-pressed={m.rating === 1} onClick={() => rate(m, 1)}>
                                      <ThumbsUp className="h-4 w-4" />
                                    </Button>
                                  </Tip>
                                  <Tip label="Not helpful">
                                    <Button variant="ghost" size="icon" className={cn("h-8 w-8", m.rating === -1 && "text-danger")} aria-label="Not helpful" aria-pressed={m.rating === -1} onClick={() => rate(m, -1)}>
                                      <ThumbsDown className="h-4 w-4" />
                                    </Button>
                                  </Tip>
                                </>
                              ) : null}
                            </div>
                          ) : null}

                          {!m.streaming && m.key === lastAssistant?.key && m.followUps && m.followUps.length > 0 ? (
                            <div className="mt-4 flex flex-wrap gap-2" aria-label="Suggested follow-up questions">
                              {m.followUps.map((f) => (
                                <button key={f} onClick={() => send(f)} disabled={busy} className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs transition hover:border-emerald hover:text-forest disabled:opacity-50 dark:hover:text-emerald">
                                  {f}
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </motion.li>
                ))}
              </ol>
            )}
            <div ref={bottomRef} className="h-4" />
          </div>
        </main>

        <div className="shrink-0 border-t border-border bg-background/90 px-4 pb-4 pt-3 backdrop-blur sm:px-6">
          <div className="mx-auto max-w-3xl">
            <AnimatePresence>
              {showFilters && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                  <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
                    <label className="sr-only" htmlFor="f-cat">Category</label>
                    <Select id="f-cat" value={category} onChange={(e) => setCategory(e.target.value)} className="h-9">
                      <option value="">All categories</option>
                      {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                    </Select>
                    <label className="sr-only" htmlFor="f-year">Academic year</label>
                    <Select id="f-year" value={year} onChange={(e) => setYear(e.target.value)} className="h-9">
                      <option value="">Current academic year</option>
                      {years.map((y) => <option key={y} value={y}>{y}</option>)}
                    </Select>
                    {(category || year) && <Button variant="ghost" size="sm" onClick={() => { setCategory(""); setYear(""); }}>Clear</Button>}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <form
              onSubmit={(e) => { e.preventDefault(); send(input); }}
              className="flex items-end gap-2 rounded-2xl border border-border bg-surface p-2 shadow-sm focus-within:border-emerald"
            >
              <Tip label="Filters">
                <Button type="button" variant="ghost" size="icon" aria-label="Search filters" aria-expanded={showFilters} onClick={() => setShowFilters((s) => !s)} className={cn((category || year) && "text-emerald")}>
                  <SlidersHorizontal className="h-4 w-4" />
                </Button>
              </Tip>
              <label htmlFor="composer" className="sr-only">Your question</label>
              <textarea
                id="composer"
                ref={taRef}
                rows={1}
                value={input}
                maxLength={2000}
                onChange={(e) => {
                  setInput(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 180) + "px";
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                placeholder="Ask a question about UL…"
                className="max-h-[180px] min-h-[40px] flex-1 resize-none bg-transparent px-1 py-2 text-[0.95rem] outline-none placeholder:text-muted/70"
              />
              {busy ? (
                <Button type="button" size="icon" variant="outline" aria-label="Stop generating" onClick={stop}><Square className="h-4 w-4" /></Button>
              ) : (
                <Button type="submit" size="icon" aria-label="Send" disabled={!input.trim()}><ArrowUp className="h-4 w-4" /></Button>
              )}
            </form>
            <p className="mt-2 text-center text-[11px] text-muted">
              Answers can be incomplete. Check the cited sources and confirm important decisions with the relevant UL office.
            </p>
          </div>
        </div>
      </div>
      <SourcePreview c={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="grid h-dvh place-items-center text-muted"><Loader2 className="h-5 w-5 animate-spin" /></div>}>
      <ChatWorkspace />
    </Suspense>
  );
}
