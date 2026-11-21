"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowUpRight, BookOpen, ChevronRight, GraduationCap, Search } from "lucide-react";
import snapshot from "@/data/curricula.json";
import { SiteHeader, SiteFooter } from "@/components/site";
import { Badge, Button, Card, Dialog, DialogContent, Input, Select } from "@/components/ui";
import { Markdown } from "@/components/chat/markdown";
import { API_URL } from "@/lib/api";

type Module = { code: string; title: string; description: string; group: string; url: string };
type Section = { id: string; yearLabel: string; semester: string; modules: Module[]; notes: string[]; sourceUrl: string };
type Programme = { id: string; title: string; code: string | null; checkedAt: string; url: string; sections: Section[]; status: string };
type Descriptor = { title: string; text: string; url: string; collectedAt: string; note: string };
const programmes = snapshot.courses as Programme[];

export function CurriculumExplorer() {
  const params = useSearchParams();
  const initial = programmes.find(c => c.id === params.get("course") || c.code === params.get("course")) || programmes.find(c => c.code === "LM174") || programmes[0];
  const [selected, setSelected] = useState(initial?.id || "");
  const [search, setSearch] = useState("");
  const [year, setYear] = useState("");
  const [activeModule, setActiveModule] = useState<Module | null>(null);
  const [descriptor, setDescriptor] = useState<Descriptor | null>(null);
  const [loading, setLoading] = useState(false);
  const [descriptorError, setDescriptorError] = useState("");
  const course = programmes.find(c => c.id === selected) || initial;
  const matches = programmes.filter(c => `${c.code || ""} ${c.title}`.toLowerCase().includes(search.toLowerCase().trim()));
  const years = [...new Set(course?.sections.map(s => s.yearLabel) || [])];
  const sections = course?.sections.filter(s => !year || s.yearLabel === year) || [];

  useEffect(() => {
    if (!activeModule) return;
    const controller = new AbortController();
    let active = true;
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 45000);
    setDescriptor(null); setDescriptorError(""); setLoading(true);
    fetch(`${API_URL}/api/modules/${encodeURIComponent(activeModule.code)}`, { signal: controller.signal, cache: "no-store" })
      .then(async r => { if (!r.ok) throw new Error(r.status === 404 ? "The detailed descriptor has not yet been indexed. You can read it in UL’s official Book of Modules." : "The module service is temporarily unavailable. Please use the official source link or try again."); return r.json() as Promise<Descriptor>; })
      .then(d => { if (!controller.signal.aborted) setDescriptor(d); })
      .catch(e => { if (active) setDescriptorError(timedOut ? "The module service took too long to respond. Please use the official source link or try again." : (e as Error).message); })
      .finally(() => { if (active) setLoading(false); clearTimeout(timer); });
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [activeModule]);

  return <><SiteHeader /><main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
    <Badge tone="green"><BookOpen className="h-3 w-3" /> Your programme, semester by semester</Badge>
    <h1 className="mt-4 font-display text-4xl sm:text-5xl">See what you’ll study.</h1>
    <p className="mt-4 max-w-2xl text-muted">Explore module lists from official UL course-content pages. Keep years, pathways, options and placement semesters in view, then open a module to read its published content.</p>
    <div className="mt-7 grid gap-3 rounded-2xl border border-border bg-surface p-4 md:grid-cols-[1fr_2fr]">
      <label className="text-xs text-muted"><span className="mb-2 flex items-center gap-1"><Search className="h-3 w-3" /> Find a programme</span><Input value={search} onChange={e => setSearch(e.target.value)} placeholder="e.g. LM174, nursing, engineering" /></label>
      <label className="text-xs text-muted"><span className="mb-2 block">Choose programme ({matches.length} matches)</span><Select className="w-full" aria-label="Choose programme" value={matches.some(c => c.id === selected) ? selected : ""} onChange={e => { setSelected(e.target.value); setYear(""); }}><option value="" disabled>Select a programme</option>{matches.map(c => <option key={c.id} value={c.id}>{c.code ? c.code + " · " : ""}{c.title}</option>)}</Select></label>
    </div>
    {course && <>
      <div className="mt-8 flex flex-wrap items-start justify-between gap-4"><div><h2 className="font-display text-2xl sm:text-3xl">{course.title}</h2><div className="mt-3 flex flex-wrap gap-2">{course.code && <Badge tone="green">{course.code}</Badge>}<Badge>{course.sections.length} captured sections</Badge><Badge>Academic-year applicability not confirmed</Badge></div></div><Button asChild variant="outline"><a href={course.url} target="_blank" rel="noreferrer">Official course content <ArrowUpRight className="h-4 w-4" /></a></Button></div>
      <p className="mt-4 max-w-3xl text-xs leading-relaxed text-muted">These are published module listings, not a personalised registration plan. Options may require a choice, and modules or pathways can change by cohort. The collection date is not confirmation that the structure applies to a particular academic year. Source collected {new Date(course.checkedAt).toLocaleDateString("en-IE", { day:"numeric", month:"short", year:"numeric", timeZone:"UTC" })}.</p>
      {years.length > 0 && <div className="my-6 flex flex-wrap gap-2" aria-label="Year or pathway"><Button size="sm" variant={!year ? "subtle" : "outline"} aria-pressed={!year} onClick={() => setYear("")}>All sections</Button>{years.map(y => <Button key={y} size="sm" variant={year === y ? "subtle" : "outline"} aria-pressed={year === y} onClick={() => setYear(y)}>{y}</Button>)}</div>}
      {!sections.length ? <Card className="mt-6 p-8 text-center"><GraduationCap className="mx-auto h-8 w-8 text-muted" /><h3 className="mt-3 font-semibold">A semester map is not available in this snapshot</h3><p className="mt-2 text-sm text-muted">The page may describe subjects without codes, use another layout or not publish semester-level detail. Please check the official programme page. We haven’t filled those gaps by guessing.</p></Card> : <div className="grid items-start gap-5 lg:grid-cols-2">{sections.map(s => <Card key={s.id} className="min-w-0 overflow-hidden"><div className="border-b border-border bg-surface-2/50 p-5"><p className="text-xs font-medium text-muted">{s.yearLabel}</p><div className="mt-2 flex items-center justify-between gap-3"><h3 className="text-xl font-semibold">{s.semester}</h3><Badge>{s.modules.length} module listings</Badge></div></div><div className="p-5"><ul className="space-y-2">{s.modules.map((m,i) => <li key={`${m.code}-${i}`}><button onClick={() => { setDescriptor(null); setDescriptorError(""); setLoading(true); setActiveModule(m); }} className="flex w-full items-start gap-3 rounded-xl border border-border px-3 py-3 text-left transition hover:border-emerald hover:bg-emerald-soft"><span className="shrink-0 rounded-md bg-surface-2 px-2 py-1 font-mono text-xs text-emerald">{m.code}</span><span className="min-w-0 flex-1"><span className="block text-sm font-medium">{m.title}</span>{m.group !== "Listed modules" && <span className="mt-1 block text-xs text-muted">{m.group}</span>}</span><ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted" /></button></li>)}</ul>{!!s.notes.length && <div className="mt-4 space-y-2 rounded-xl bg-surface-2 p-3 text-xs leading-relaxed text-muted">{s.notes.map((n,i) => <p key={i}>{n}</p>)}</div>}<div className="mt-4 flex flex-wrap gap-4 text-xs"><a href={s.sourceUrl} target="_blank" rel="noreferrer" className="text-emerald underline underline-offset-4">Check this source section</a><Link href={`/chat?q=${encodeURIComponent(`Which modules are listed for ${course.code || course.title}, ${s.yearLabel}, ${s.semester}? Keep pathways and elective choices separate and cite the curriculum source.`)}`} className="text-emerald underline underline-offset-4">Ask about this semester</Link></div></div></Card>)}</div>}
    </>}
    <p className="mt-8 border-t border-border pt-5 text-xs text-muted">Coverage: {snapshot.coverage.structuredCourses} of {snapshot.coverage.catalogueCourses} collected course records have captured module sections. This is an ongoing collection, not confirmation of complete coverage of every UL programme or elective.</p>
    <Dialog open={!!activeModule} onOpenChange={open => { if (!open) setActiveModule(null); }}><DialogContent title={activeModule ? `${activeModule.code} · ${activeModule.title}` : "Module content"} description="Published module content with links to the official UL sources.">
      {activeModule && <><div className="mb-4 flex flex-wrap gap-2"><Badge tone="green">{activeModule.code}</Badge><Badge>{activeModule.group}</Badge></div>{activeModule.description && <p className="mb-5 text-sm leading-relaxed text-muted">Course-page summary: {activeModule.description}</p>}{loading ? <p role="status" className="text-sm text-muted">Loading the indexed module descriptor…</p> : descriptor ? <><p className="mb-4 text-xs leading-relaxed text-muted">{descriptor.note}</p><Markdown content={descriptor.text} citations={[]} onCite={() => {}} /><p className="mt-4 text-xs text-muted">Descriptor collected {new Date(descriptor.collectedAt).toLocaleDateString("en-IE", {timeZone:"UTC"})}.</p></> : <p className="rounded-xl bg-surface-2 p-4 text-sm text-muted">{descriptorError}</p>}<a href={activeModule.url} target="_blank" rel="noreferrer" className="mt-5 inline-flex items-center gap-1 text-sm text-emerald underline underline-offset-4">Open official Book of Modules <ArrowUpRight className="h-4 w-4" /></a></>}
    </DialogContent></Dialog>
  </main><SiteFooter /></>;
}
