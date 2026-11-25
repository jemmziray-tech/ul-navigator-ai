"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight, BookOpenCheck, Check, CircleAlert, Clock3, FileSearch, RefreshCw, ShieldCheck } from "lucide-react";
import { SiteFooter, SiteHeader } from "@/components/site";
import { Badge, Button, Card, Skeleton } from "@/components/ui";
import { api, label, type Stats } from "@/lib/api";
import { sourceDate } from "@/lib/courses";

type Props = {
  generatedAt: string;
  coverage: { courses: number; requirements: number; courseCodes: number };
  collection: { at: string; collected: number; discovered: number };
  modules: { catalogueCourses: number; structuredCourses: number; semesterSections: number; moduleListings: number; generatedAt: string };
};
const CORE_TOPICS = ["undergraduate", "postgraduate", "fees", "regulations", "accommodation", "international", "library", "student_support", "scholarships", "careers", "modules", "calendar"];

export function KnowledgeHealth({ generatedAt, coverage, collection, modules }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [checked, setChecked] = useState<string | null>(null);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true); setError(false);
    try {
      const timeout = AbortSignal.timeout(45_000);
      const value = await api<Stats>("/api/stats", { signal: signal ? AbortSignal.any([signal, timeout]) : timeout });
      setStats(value); setChecked(new Date().toISOString());
    } catch { if (!signal?.aborted) setError(true); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => { const controller = new AbortController(); load(controller.signal); return () => controller.abort(); }, [load]);

  const gaps = stats ? CORE_TOPICS.filter(topic => (stats.categories[topic] || 0) < 5) : [];
  const proportion = collection.discovered ? Math.min(100, collection.collected / collection.discovered * 100) : 0;

  return <><SiteHeader /><main id="main" className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
    <div className="flex flex-wrap items-start justify-between gap-5"><div className="max-w-2xl"><p className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald"><ShieldCheck className="h-4 w-4" />Open about our knowledge</p><h1 className="font-display text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">Good answers start<br />with information you can inspect.</h1><p className="mt-4 leading-relaxed text-muted">See the official sources behind UL Navigator, where coverage is growing, and which details still need checking.</p></div><Button variant="outline" onClick={() => load()} disabled={loading}><RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />{loading ? "Checking…" : "Refresh live counts"}</Button></div>

    <section className="mt-9" aria-labelledby="live-heading"><div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 id="live-heading" className="text-sm font-semibold">Searchable on the live site</h2><Badge tone={error ? "warn" : stats ? "green" : "neutral"}>{error ? "Live check unavailable" : stats ? "Live counts retrieved" : "Checking the live collection"}</Badge></div>
      {error && <p role="alert" className="mb-4 rounded-xl border border-warning/30 bg-surface p-4 text-sm text-muted">The live collection could not be reached. {stats ? "The counts below are from the last successful check." : "The course snapshot and source links remain available."} Try refreshing in a moment.</p>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[{ label: "Official sources indexed", value: stats?.documents }, { label: "Searchable passages", value: stats?.chunks }, { label: "PDF documents", value: stats?.pdf_documents }, { label: "PDF pages processed", value: stats?.pdf_pages }].map(item => <Card className="p-5" key={item.label}><p className="text-xs text-muted">{item.label}</p>{loading && !stats ? <Skeleton className="mt-3 h-10 w-20" /> : <p className="mt-2 font-display text-4xl font-semibold tabular-nums">{item.value?.toLocaleString() ?? "—"}</p>}</Card>)}</div>
      {checked && <p className="mt-3 text-xs text-muted">Checked {sourceDate(checked)} · Most recent source import {sourceDate(stats?.last_synced)}. These counts describe indexed information, not the completeness or accuracy of every answer.</p>}
    </section>

    <div className="mt-9 grid gap-5 lg:grid-cols-[1.45fr_1fr]"><section aria-labelledby="coverage-heading"><Card className="h-full p-6"><div className="mb-5 flex items-center justify-between"><div><p className="text-xs uppercase tracking-wider text-muted">A closer look</p><h2 id="coverage-heading" className="mt-1 font-display text-2xl font-semibold">Topic coverage</h2></div><FileSearch className="h-6 w-6 text-emerald" /></div><p className="mb-5 text-sm leading-relaxed text-muted">Explore the sources in a topic before relying on an answer. Topics with fewer than five indexed sources are flagged for closer review.</p>
      <div className="grid gap-2 sm:grid-cols-2">{CORE_TOPICS.map(topic => { const count = stats?.categories[topic]; return <Link href={`/explorer?category=${topic}`} key={topic} className="flex items-center justify-between gap-2 rounded-xl border border-border p-3 transition hover:border-emerald"><div><p className="text-sm font-medium">{label(topic)}</p><p className="mt-1 text-[11px] text-muted">{count === undefined ? "Count not checked" : count < 5 ? "Limited indexed coverage" : "Browse collected sources"}</p></div><span className="flex items-center gap-2 text-sm font-semibold tabular-nums">{count?.toLocaleString() ?? "—"}<ArrowUpRight className="h-3.5 w-3.5 text-muted" /></span></Link>; })}</div>
      {stats && <p className="mt-4 text-xs text-muted">{gaps.length} {gaps.length === 1 ? "topic" : "topics"} flagged for review. A larger source count does not guarantee complete coverage.</p>}</Card></section>

      <section aria-labelledby="collection-heading"><Card className="h-full p-6"><Badge>Collection snapshot</Badge><h2 id="collection-heading" className="mt-4 font-display text-2xl font-semibold">A growing library,<br />with clear boundaries.</h2><p className="mt-3 text-sm leading-relaxed text-muted">The public-site collection is separate from what has been added to chat. Pages are checked, extracted and imported in batches.</p><dl className="mt-6 space-y-4"><div className="flex items-center justify-between border-b border-border pb-4"><dt className="text-sm text-muted">Discovered URLs</dt><dd className="text-2xl font-semibold tabular-nums">{collection.discovered.toLocaleString()}</dd></div><div className="flex items-center justify-between"><dt className="text-sm text-muted">Pages with saved text</dt><dd className="text-2xl font-semibold tabular-nums">{collection.collected.toLocaleString()}</dd></div></dl><div className="mt-5 h-2 overflow-hidden rounded-full bg-surface-2" role="progressbar" aria-label="Saved text among discovered URLs at snapshot time" aria-valuenow={Math.round(proportion)} aria-valuemin={0} aria-valuemax={100}><div className="h-full rounded-full bg-emerald" style={{ width: `${proportion}%` }} /></div><p className="mt-2 text-xs text-muted">{proportion.toFixed(1)}% of this discovered queue had saved text at snapshot time.</p><p className="mt-5 flex items-start gap-2 rounded-xl bg-surface-2 p-3 text-xs leading-relaxed text-muted"><Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0" />Recorded {sourceDate(collection.at)}. This snapshot is not a live crawler status or a claim that all UL information has been collected.</p><p className="mt-4 text-xs leading-relaxed text-muted">Collection covers supported public pages and documents. Inaccessible pages, private services, unsupported files and text requiring OCR can leave gaps.</p></Card></section></div>

    <section className="mt-9" aria-labelledby="modules-heading">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-xs uppercase tracking-wider text-muted">Programme and semester coverage</p><h2 id="modules-heading" className="mt-1 font-display text-3xl font-semibold">See what is mapped.</h2></div>
        <Button asChild variant="outline"><Link href="/curricula">Browse semester maps<ArrowRight className="h-4 w-4" /></Link></Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { title: "Programmes with maps", count: modules.structuredCourses, detail: `Of ${modules.catalogueCourses} checked catalogue records` },
          { title: "Year and semester sections", count: modules.semesterSections, detail: "Includes separate published pathways" },
          { title: "Coded module listings", count: modules.moduleListings, detail: "Listings may repeat across programmes" },
          { title: "Maps still missing", count: Math.max(0, modules.catalogueCourses - modules.structuredCourses), detail: "No structured semester map captured" },
        ].map(item => <Card key={item.title} className="p-5"><h3 className="text-sm font-semibold">{item.title}</h3><p className="mt-3 font-display text-4xl font-semibold tabular-nums">{item.count.toLocaleString()}</p><p className="mt-3 text-xs leading-relaxed text-muted">{item.detail}</p></Card>)}
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted">Snapshot updated {sourceDate(modules.generatedAt)}. These are published curriculum listings, not a count of fully indexed module descriptions or a personalised registration plan. Electives, pathways and academic-year applicability must be checked against the linked official source.</p>
    </section>

    <section className="mt-9" aria-labelledby="quality-heading"><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs uppercase tracking-wider text-muted">Behind the course finder</p><h2 id="quality-heading" className="mt-1 font-display text-3xl font-semibold">Useful facts. Visible gaps.</h2></div><Button asChild variant="outline"><Link href="/courses">Explore programmes<ArrowRight className="h-4 w-4" /></Link></Button></div><div className="grid gap-4 md:grid-cols-3">{[
      { icon: BookOpenCheck, title: "Programme snapshots", count: coverage.courses, total: coverage.courses, body: "Programmes with structured official course information. This is a collected selection, not UL’s full directory." },
      { icon: Check, title: "Entry guidance collected", count: coverage.requirements, total: coverage.courses, body: "Programmes with an entry-page extract. The course finder links to the official page when an extract is missing." },
      { icon: CircleAlert, title: "Entry guidance still to collect", count: coverage.courses - coverage.requirements, total: coverage.courses, body: "Missing details are shown explicitly. Fees are linked to official guidance; historical CAO points retain their published year." },
    ].map(item => <Card className="p-6" key={item.title}><item.icon className="h-5 w-5 text-emerald" /><h3 className="mt-4 text-sm font-semibold">{item.title}</h3><p className="mt-2 font-display text-4xl font-semibold">{item.count}<span className="ml-2 font-sans text-sm font-normal text-muted">of {item.total}</span></p><p className="mt-3 text-sm leading-relaxed text-muted">{item.body}</p></Card>)}</div><p className="mt-3 text-xs text-muted">Course snapshot updated {sourceDate(generatedAt)}. Every programme shows its source date and links.</p></section>

    <section className="mt-9 rounded-2xl border border-emerald/20 bg-emerald-soft p-6 sm:flex sm:items-center sm:justify-between sm:gap-6"><div><h2 className="font-display text-2xl font-semibold">Check the evidence. Keep your options open.</h2><p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">Source links let you check the detail, academic year and applicant route that matter to you. Important application decisions should be confirmed with UL.</p></div><Button asChild className="mt-4 shrink-0 sm:mt-0"><Link href="/explorer">Browse official sources<ArrowRight className="h-4 w-4" /></Link></Button></section>
    </main><SiteFooter /></>;
}
