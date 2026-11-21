"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, ExternalLink, FileText, Globe, Search, Upload } from "lucide-react";
import { SiteFooter, SiteHeader } from "@/components/site";
import { Badge, Button, Card, Dialog, DialogContent, EmptyState, ErrorBanner, Input, Select, Skeleton } from "@/components/ui";
import { api, CATEGORY_LABELS, fmtDate, label } from "@/lib/api";

type Doc = {
  id: string; title: string; url: string; category: string; academic_year: string | null;
  content_type: string; chunk_count: number; page_count: number | null; collected_at: string;
  preview: string; is_manual: boolean;
};
type DocDetail = Doc & { sections: { chunk_id: number; section: string; page: number | null; text: string }[] };

function Explorer() {
  const params = useSearchParams();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState(params.get("category") || "");
  const [year, setYear] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: Doc[]; years: string[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<DocDetail | null>(null);
  const size = 18;

  const load = useCallback(async () => {
    setErr(null);
    const sp = new URLSearchParams({ page: String(page), size: String(size) });
    if (query) sp.set("q", query);
    if (category) sp.set("category", category);
    if (year) sp.set("year", year);
    if (type) sp.set("content_type", type);
    try {
      setData(await api(`/api/sources?${sp}`));
    } catch {
      setErr("Couldn't load sources. Is the backend running?");
    }
  }, [page, query, category, year, type]);

  useEffect(() => { load(); }, [load]);

  const openDoc = async (id: string) => {
    try { setOpen(await api<DocDetail>(`/api/sources/${id}`)); } catch { setErr("Couldn't load that source."); }
  };

  const pages = data ? Math.max(1, Math.ceil(data.total / size)) : 1;

  return (
    <>
      <SiteHeader />
      <main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <h1 className="font-display text-4xl font-semibold tracking-tight">Knowledge explorer</h1>
        <p className="mt-2 max-w-2xl text-muted">Every official source the assistant can use. Search, filter by category or academic year, and preview what was indexed and when.</p>

        <Card className="mt-8 p-3">
          <form className="flex flex-col gap-2 md:flex-row" onSubmit={(e) => { e.preventDefault(); setPage(1); setQuery(q.trim()); }} role="search">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <label htmlFor="ex-q" className="sr-only">Search sources</label>
              <Input id="ex-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles, URLs and content…" className="pl-9" />
            </div>
            <label htmlFor="ex-cat" className="sr-only">Category</label>
            <Select id="ex-cat" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
              <option value="">All categories</option>
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
            <label htmlFor="ex-year" className="sr-only">Academic year</label>
            <Select id="ex-year" value={year} onChange={(e) => { setYear(e.target.value); setPage(1); }}>
              <option value="">All years</option>
              {(data?.years || []).map((y) => <option key={y} value={y}>{y}</option>)}
            </Select>
            <label htmlFor="ex-type" className="sr-only">Type</label>
            <Select id="ex-type" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
              <option value="">All types</option><option value="html">Web pages</option><option value="pdf">PDFs</option><option value="csv">CSV</option><option value="txt">Text</option>
            </Select>
            <Button type="submit">Search</Button>
          </form>
        </Card>

        {err ? <div className="mt-6"><ErrorBanner message={err} onRetry={load} /></div> : null}

        <p className="mt-6 text-sm text-muted" aria-live="polite">{data ? `${data.total.toLocaleString()} source${data.total === 1 ? "" : "s"}` : "Loading…"}</p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {!data && !err
            ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-44" />)
            : data?.items.map((d, i) => (
                <motion.button key={d.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.02 }}
                  onClick={() => openDoc(d.id)}
                  className="flex flex-col rounded-2xl border border-border bg-surface p-5 text-left transition hover:-translate-y-0.5 hover:border-emerald/60 hover:shadow-md">
                  <div className="flex items-center gap-2 text-xs text-muted">
                    {d.content_type === "pdf" ? <FileText className="h-3.5 w-3.5" /> : d.is_manual ? <Upload className="h-3.5 w-3.5" /> : <Globe className="h-3.5 w-3.5" />}
                    <span className="uppercase">{d.content_type}</span>
                    {d.page_count ? <span>· {d.page_count} pages</span> : null}
                    <span className="ml-auto">{fmtDate(d.collected_at)}</span>
                  </div>
                  <h2 className="mt-2 line-clamp-2 font-semibold leading-snug">{d.title}</h2>
                  <p className="mt-2 line-clamp-3 text-sm text-muted">{d.preview}</p>
                  <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
                    <Badge>{label(d.category)}</Badge>
                    {d.academic_year ? <Badge tone="green">{d.academic_year}</Badge> : null}
                    <Badge>{d.chunk_count} passages</Badge>
                  </div>
                </motion.button>
              ))}
        </div>
        {data && data.items.length === 0 ? (
          <div className="mt-4"><EmptyState icon={<Search className="h-6 w-6" />} title="No sources match">Try a different search or clear the filters. If nothing is indexed yet, run the ingestion pipeline.</EmptyState></div>
        ) : null}
        {data && pages > 1 ? (
          <div className="mt-8 flex items-center justify-center gap-3">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
            <span className="text-sm text-muted">Page {page} of {pages}</span>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
          </div>
        ) : null}
      </main>
      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        {open ? (
          <DialogContent title={open.title} description={`${label(open.category)}${open.academic_year ? " · " + open.academic_year : ""} · retrieved ${fmtDate(open.collected_at)}`} className="max-w-3xl">
            {open.url.startsWith("http") ? (
              <Button asChild size="sm" variant="outline" className="mb-4">
                <a href={open.url} target="_blank" rel="noopener noreferrer">Open original <ExternalLink className="h-3.5 w-3.5" /></a>
              </Button>
            ) : null}
            <div className="space-y-3">
              {open.sections.map((s) => (
                <div key={s.chunk_id} className="rounded-xl border border-border p-4">
                  <p className="mb-1 text-xs font-medium text-muted">{s.section || "Introduction"}{s.page ? ` · page ${s.page}` : ""}</p>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{s.text}</p>
                </div>
              ))}
              {open.chunk_count > open.sections.length ? <p className="text-xs text-muted">Showing the first {open.sections.length} of {open.chunk_count} passages.</p> : null}
            </div>
          </DialogContent>
        ) : null}
      </Dialog>
      <SiteFooter />
    </>
  );
}

export default function ExplorerPage() {
  return <Suspense><Explorer /></Suspense>;
}
