"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  BookMarked, Calculator, CalendarDays, CheckCircle2, Circle, ExternalLink, ListChecks, Loader2,
  MessageCircle, Plus, Search, Sparkles, Trash2,
} from "lucide-react";
import { SiteFooter, SiteHeader } from "@/components/site";
import { Badge, Button, Card, EmptyState, ErrorBanner, Input, Select, Skeleton } from "@/components/ui";
import { Markdown } from "@/components/chat/markdown";
import { api, fmtDate } from "@/lib/api";
import { cn } from "@/lib/utils";

type Passage = { chunk_id: number; title: string; url: string; section: string; page: number | null; text: string; academic_year: string | null; collected_at: string };
type SourceRef = { title: string; url: string };

const TABS = [
  { id: "qca", label: "QCA calculator", icon: Calculator },
  { id: "calendar", label: "Academic calendar", icon: CalendarDays },
  { id: "modules", label: "Module search", icon: BookMarked },
  { id: "checklist", label: "International checklist", icon: ListChecks },
  { id: "explore", label: "Scholarships & accommodation", icon: Sparkles },
] as const;
type TabId = (typeof TABS)[number]["id"];

/* ------------------------------------------------------------------ QCA */
type Row = { key: string; code: string; credits: number; grade: string; include: boolean };
type QcaResult = {
  qca: number | null; credits: number; quality_points: number; classification: string | null;
  excluded_modules: string[]; disclaimer: string; sources: SourceRef[];
};

function QcaTool() {
  const [grades, setGrades] = useState<{ grade: string; qpv: number }[]>([]);
  const [formula, setFormula] = useState("");
  const [rows, setRows] = useState<Row[]>(() =>
    Array.from({ length: 5 }, (_, i) => ({ key: String(i), code: "", credits: 6, grade: "B1", include: true })),
  );
  const [res, setRes] = useState<QcaResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<{ grades: { grade: string; qpv: number }[]; formula: string }>("/api/tools/qca/rules")
      .then((r) => { setGrades(r.grades); setFormula(r.formula); })
      .catch(() => setErr("Couldn't load UL grading rules from the API."));
  }, []);

  useEffect(() => {
    const t = setTimeout(async () => {
      try {
        setRes(await api<QcaResult>("/api/tools/qca", {
          method: "POST",
          body: JSON.stringify({ modules: rows.map(({ code, credits, grade, include }) => ({ code, credits, grade, include })) }),
        }));
        setErr(null);
      } catch (e) {
        setErr((e as Error).message);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [rows]);

  const upd = (key: string, p: Partial<Row>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...p } : r)));

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <Card className="p-5 lg:col-span-2"><h2 className="font-semibold">Working towards a target?</h2><p className="mt-1 text-sm text-muted">Explore the grades you need in your remaining modules.</p><Button asChild className="mt-3" variant="subtle"><Link href="/grade-planner">Open Grade Target Planner</Link></Button><Button asChild className="ml-2 mt-3" variant="outline"><Link href="/curricula">Browse programme modules</Link></Button></Card>
      <Card className="p-5">
        <div className="mb-3 grid grid-cols-[1fr_90px_100px_70px_36px] gap-2 text-xs font-medium text-muted">
          <span>Module (optional)</span><span>Credits</span><span>Grade</span><span>Counts</span><span />
        </div>
        <ul className="space-y-2">
          {rows.map((r, i) => (
            <li key={r.key} className="grid grid-cols-[1fr_90px_100px_70px_36px] items-center gap-2">
              <Input aria-label={`Module ${i + 1} code`} value={r.code} onChange={(e) => upd(r.key, { code: e.target.value })} placeholder={`e.g. CS4012`} maxLength={20} />
              <Input aria-label={`Module ${i + 1} credits`} type="number" min={1} max={60} step={0.5} value={r.credits} onChange={(e) => upd(r.key, { credits: Math.max(0.5, Number(e.target.value) || 0) })} />
              <Select aria-label={`Module ${i + 1} grade`} value={r.grade} onChange={(e) => upd(r.key, { grade: e.target.value })}>
                {(grades.length ? grades : [{ grade: r.grade, qpv: 0 }]).map((g) => <option key={g.grade} value={g.grade}>{g.grade}{grades.length ? ` (${g.qpv.toFixed(2)})` : ""}</option>)}
              </Select>
              <label className="flex items-center justify-center">
                <input type="checkbox" className="h-4 w-4 accent-[var(--emerald)]" checked={r.include} onChange={(e) => upd(r.key, { include: e.target.checked })} aria-label={`Include module ${i + 1} in QCA`} />
              </label>
              <Button variant="ghost" size="icon" aria-label={`Remove module ${i + 1}`} disabled={rows.length <= 1} onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => setRows((rs) => [...rs, { key: Math.random().toString(36), code: "", credits: 6, grade: "B1", include: true }])}>
          <Plus className="h-4 w-4" /> Add module
        </Button>
        {formula ? <p className="mt-5 rounded-xl bg-surface-2 p-3 font-mono text-xs">{formula}</p> : null}
      </Card>
      <div className="space-y-4">
        <Card className="overflow-hidden">
          <div className="bg-gradient-to-br from-forest to-forest-2 p-6 text-white">
            <p className="text-sm opacity-80">Your QCA</p>
            <p className="mt-1 text-5xl font-semibold tabular-nums" aria-live="polite">{res?.qca != null ? res.qca.toFixed(2) : "—"}</p>
            <p className="mt-2 text-sm opacity-90">{res?.classification ?? (res?.qca != null ? "Below third class honours threshold" : "")}</p>
            <p className="mt-2 text-xs opacity-80">Indicative band uses the unrounded calculation. QCA above is rounded to two decimals.</p>
          </div>
          <dl className="grid grid-cols-2 gap-3 p-5 text-sm">
            <div><dt className="text-muted">Credits counted</dt><dd className="font-semibold">{res?.credits ?? "—"}</dd></div>
            <div><dt className="text-muted">Quality points</dt><dd className="font-semibold">{res?.quality_points ?? "—"}</dd></div>
          </dl>
        </Card>
        {err ? <ErrorBanner message={err} /> : null}
        {res ? (
          <Card className="p-5 text-xs leading-relaxed text-muted">
            <p>{res.disclaimer}</p>
            <p className="mt-3 font-medium text-foreground">Sources</p>
            <ul className="mt-1 space-y-1">
              {res.sources.map((s) => (
                <li key={s.url}><a className="inline-flex items-center gap-1 underline underline-offset-2 hover:text-foreground" href={s.url} target="_blank" rel="noopener noreferrer">{s.title}<ExternalLink className="h-3 w-3" /></a></li>
              ))}
            </ul>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

/* --------------------------------------------------------- passage list */
function PassageList({ items, loading, emptyTitle, emptyBody }: { items: Passage[] | null; loading: boolean; emptyTitle: string; emptyBody: string }) {
  const grouped = useMemo(() => {
    const m = new Map<string, Passage[]>();
    (items || []).forEach((p) => m.set(p.url, [...(m.get(p.url) || []), p]));
    return [...m.values()];
  }, [items]);
  if (loading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32" />)}</div>;
  if (!items || items.length === 0) return <EmptyState icon={<Search className="h-6 w-6" />} title={emptyTitle}>{emptyBody}</EmptyState>;
  return (
    <div className="space-y-5">
      {grouped.map((group) => (
        <Card key={group[0].url} className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 className="font-semibold">{group[0].title}</h3>
              <p className="mt-0.5 text-xs text-muted">Retrieved {fmtDate(group[0].collected_at)}{group[0].academic_year ? ` · ${group[0].academic_year}` : ""}</p>
            </div>
            {group[0].url.startsWith("http") ? (
              <Button asChild variant="outline" size="sm"><a href={group[0].url} target="_blank" rel="noopener noreferrer">Official page <ExternalLink className="h-3.5 w-3.5" /></a></Button>
            ) : null}
          </div>
          <div className="mt-4 space-y-4">
            {group.map((p) => (
              <div key={p.chunk_id} className="border-l-2 border-emerald/50 pl-4">
                {p.section ? <p className="mb-1 text-xs font-medium text-muted">{p.section}{p.page ? ` · p.${p.page}` : ""}</p> : null}
                <Markdown content={p.text} citations={[]} onCite={() => {}} />
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

function usePassages(path: string | null) {
  const [items, setItems] = useState<Passage[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true); setErr(null);
    try { setItems((await api<{ items: Passage[] }>(path)).items); }
    catch { setErr("Couldn't load information from the API."); }
    finally { setLoading(false); }
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return { items, loading, err, reload: load };
}

function CalendarTool() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { items, loading, err, reload } = usePassages(`/api/tools/calendar${query ? `?q=${encodeURIComponent(query)}` : ""}`);
  return (
    <div className="space-y-4">
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
        <label htmlFor="cal-q" className="sr-only">Search the calendar</label>
        <Input id="cal-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter, e.g. exams, reading week, semester start…" />
        <Button type="submit">Filter</Button>
      </form>
      <p className="text-sm text-muted">Dates below are shown exactly as published in the indexed official calendar pages — nothing is generated.</p>
      {err ? <ErrorBanner message={err} onRetry={reload} /> : null}
      <PassageList items={items} loading={loading} emptyTitle="No calendar information indexed yet" emptyBody="Run the ingestion pipeline (the 2026/27 academic calendar is a seed source) and the official dates will appear here." />
    </div>
  );
}

type ModuleHit = { chunk_id: number; title: string; url: string; section: string; page: number | null; matched_line: string; module_codes: string[]; excerpt: string; academic_year: string | null };
function ModuleTool() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<ModuleHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const search = async (e: React.FormEvent) => {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setLoading(true); setErr(null);
    try { setRes((await api<{ results: ModuleHit[] }>(`/api/tools/modules?q=${encodeURIComponent(q.trim())}`)).results); }
    catch (e2) { setErr((e2 as Error).message); }
    finally { setLoading(false); }
  };
  return (
    <div className="space-y-4">
      <form className="flex gap-2" onSubmit={search}>
        <label htmlFor="mod-q" className="sr-only">Module code or name</label>
        <Input id="mod-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Module code (e.g. CS4012) or name (e.g. machine learning)" />
        <Button type="submit" disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Search</Button>
      </form>
      <p className="text-sm text-muted">Searches the indexed module booklets and any Book of Modules exports uploaded by an administrator.</p>
      {err ? <ErrorBanner message={err} /> : null}
      {res === null ? null : res.length === 0 ? (
        <EmptyState icon={<BookMarked className="h-6 w-6" />} title="No matching module found">Check the code, or search the official Book of Modules at bookofmodules.ul.ie.</EmptyState>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {res.map((r) => (
            <Card key={r.chunk_id} className="p-4">
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium leading-snug">{r.title}</p>
                {r.page ? <Badge>p.{r.page}</Badge> : null}
              </div>
              {r.section ? <p className="mt-0.5 text-xs text-muted">{r.section}</p> : null}
              {r.matched_line ? <p className="mt-3 rounded-lg bg-emerald-soft px-3 py-2 font-mono text-xs">{r.matched_line}</p> : <p className="mt-3 line-clamp-4 text-sm text-muted">{r.excerpt}</p>}
              <div className="mt-3 flex flex-wrap items-center gap-1">
                {r.module_codes.slice(0, 6).map((c) => <Badge key={c}>{c}</Badge>)}
                {r.url.startsWith("http") ? <a href={r.url} target="_blank" rel="noopener noreferrer" className="ml-auto inline-flex items-center gap-1 text-xs text-emerald underline underline-offset-2">Source <ExternalLink className="h-3 w-3" /></a> : null}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

type Step = { id: string; stage: string; title: string; detail: string; url: string; ask: string };
function ChecklistTool() {
  const [items, setItems] = useState<Step[] | null>(null);
  const [note, setNote] = useState("");
  const [done, setDone] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState(false);
  useEffect(() => {
    api<{ items: Step[]; note: string }>("/api/tools/checklist").then((r) => { setItems(r.items); setNote(r.note); }).catch(() => setErr(true));
    try { setDone(JSON.parse(localStorage.getItem("uln_checklist") || "{}")); } catch { /* ignore */ }
  }, []);
  const toggle = (id: string) => setDone((d) => {
    const n = { ...d, [id]: !d[id] };
    try { localStorage.setItem("uln_checklist", JSON.stringify(n)); } catch { /* ignore */ }
    return n;
  });
  if (err) return <ErrorBanner message="Couldn't load the checklist from the API." />;
  if (!items) return <Skeleton className="h-64" />;
  const stages = [...new Set(items.map((i) => i.stage))];
  const pct = Math.round((items.filter((i) => done[i.id]).length / items.length) * 100);
  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="flex items-center justify-between text-sm"><span className="font-medium">Your progress</span><span className="tabular-nums text-muted">{pct}%</span></div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <motion.div className="h-full rounded-full bg-emerald" animate={{ width: `${pct}%` }} />
        </div>
        <p className="mt-3 text-xs text-muted">{note} Progress is saved only in this browser.</p>
      </Card>
      {stages.map((s) => (
        <section key={s}>
          <h3 className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">{s}</h3>
          <ul className="space-y-2">
            {items.filter((i) => i.stage === s).map((i) => (
              <li key={i.id} className={cn("flex items-start gap-3 rounded-xl border border-border bg-surface p-4", done[i.id] && "opacity-70")}>
                <button onClick={() => toggle(i.id)} aria-pressed={!!done[i.id]} aria-label={`Mark "${i.title}" as ${done[i.id] ? "not done" : "done"}`} className="mt-0.5 text-emerald">
                  {done[i.id] ? <CheckCircle2 className="h-5 w-5" /> : <Circle className="h-5 w-5 text-muted" />}
                </button>
                <div className="flex-1">
                  <p className={cn("font-medium", done[i.id] && "line-through")}>{i.title}</p>
                  <p className="text-sm text-muted">{i.detail}</p>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs">
                    <a href={i.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-emerald underline underline-offset-2">Official guidance <ExternalLink className="h-3 w-3" /></a>
                    <Link href={`/chat?q=${encodeURIComponent(i.ask)}`} className="inline-flex items-center gap-1 text-muted hover:text-foreground"><MessageCircle className="h-3 w-3" /> Ask Navigator</Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

const EXPLORE = [
  { id: "scholarships", label: "Scholarships" },
  { id: "accommodation", label: "Accommodation" },
  { id: "fees", label: "Fees" },
  { id: "international", label: "International" },
];
function ExploreTool() {
  const [cat, setCat] = useState("scholarships");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const { items, loading, err, reload } = usePassages(`/api/tools/explore?category=${cat}${query ? `&q=${encodeURIComponent(query)}` : ""}`);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Information area">
        {EXPLORE.map((e) => (
          <button key={e.id} role="tab" aria-selected={cat === e.id} onClick={() => setCat(e.id)}
            className={cn("rounded-full border px-4 py-1.5 text-sm transition", cat === e.id ? "border-forest bg-forest text-white" : "border-border bg-surface hover:border-emerald")}>
            {e.label}
          </button>
        ))}
      </div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setQuery(q.trim()); }}>
        <label htmlFor="exp-q" className="sr-only">Filter</label>
        <Input id="exp-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter, e.g. sports, deposit, instalment…" />
        <Button type="submit">Filter</Button>
      </form>
      {err ? <ErrorBanner message={err} onRetry={reload} /> : null}
      <PassageList items={items} loading={loading} emptyTitle="Nothing indexed for this area yet" emptyBody="Run the ingestion pipeline to collect the official pages for this area." />
    </div>
  );
}

export default function ToolsPage() {
  const [tab, setTab] = useState<TabId>("qca");
  useEffect(() => {
    const h = window.location.hash.slice(1) as TabId;
    if (TABS.some((t) => t.id === h)) setTab(h);
  }, []);
  const select = (t: TabId) => { setTab(t); history.replaceState(null, "", `#${t}`); };
  return (
    <>
      <SiteHeader />
      <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <h1 className="font-display text-4xl font-semibold tracking-tight">Student tools</h1>
        <p className="mt-2 max-w-2xl text-muted">Practical tools built on UL&apos;s published rules and the indexed official sources.</p>
        <div className="mt-8 flex gap-2 overflow-x-auto pb-2 scrollbar-thin" role="tablist" aria-label="Tools">
          {TABS.map(({ id, label: l, icon: Icon }) => (
            <button key={id} role="tab" aria-selected={tab === id} aria-controls={`panel-${id}`} id={`tab-${id}`} onClick={() => select(id)}
              className={cn("inline-flex shrink-0 items-center gap-2 rounded-xl border px-4 py-2 text-sm transition", tab === id ? "border-forest bg-forest text-white" : "border-border bg-surface hover:border-emerald")}>
              <Icon className="h-4 w-4" /> {l}
            </button>
          ))}
        </div>
        <motion.section key={tab} id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-6">
          {tab === "qca" && <QcaTool />}
          {tab === "calendar" && <CalendarTool />}
          {tab === "modules" && <ModuleTool />}
          {tab === "checklist" && <ChecklistTool />}
          {tab === "explore" && <ExploreTool />}
        </motion.section>
      </main>
      <SiteFooter />
    </>
  );
}
