"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, ArrowRight, ArrowUpRight, BookOpen, Bookmark, Check, Clock3, Download, GraduationCap, Layers3, Plus, Search, Share2, SlidersHorizontal, Sparkles, X } from "lucide-react";
import { SiteFooter, SiteHeader } from "@/components/site";
import { Badge, Button, Dialog, DialogContent, EmptyState, Input, Select } from "@/components/ui";
import { comparisonCsv, courseMatches, sourceDate, validCourseIds, type Course } from "@/lib/courses";
import { cn } from "@/lib/utils";

const SAVE_KEY = "ul-course-shortlist-v1";
const NOT_SPECIFIED = "Not specified in this source";

function Fact({ label, value }: { label: string; value: string | null }) {
  return <div><dt className="text-[11px] uppercase tracking-wider text-muted">{label}</dt><dd className={cn("mt-1 text-sm font-medium", !value && "font-normal text-muted")}>{value || NOT_SPECIFIED}</dd></div>;
}

function SourceLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-emerald underline decoration-emerald/30 underline-offset-4 hover:decoration-emerald">{children}<ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden /></a>;
}

export function CourseFinder({ courses, generatedAt }: { courses: Course[]; generatedAt: string }) {
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("");
  const [subject, setSubject] = useState("");
  const [attendance, setAttendance] = useState("");
  const [savedOnly, setSavedOnly] = useState(false);
  const [saved, setSaved] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [limit, setLimit] = useState(24);
  const [detail, setDetail] = useState<Course | null>(null);
  const [notice, setNotice] = useState("");
  const [onlyDifferences, setOnlyDifferences] = useState(false);
  const compareRef = useRef<HTMLElement>(null);
  const openedSharedComparison = useRef(false);

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(SAVE_KEY) || "null");
      if (stored?.version === 1) setSaved(validCourseIds(stored.ids, courses));
    } catch { /* A blocked or old browser store does not prevent browsing. */ }
    const ids = new URLSearchParams(window.location.search).get("compare")?.split(",") || [];
    setSelected(validCourseIds(ids, courses, 3));
    setHydrated(true);
  }, [courses]);

  useEffect(() => {
    if (!hydrated) return;
    try { localStorage.setItem(SAVE_KEY, JSON.stringify({ version: 1, ids: saved })); }
    catch { setNotice("Your browser could not save the shortlist. You can still share a comparison link."); }
  }, [saved, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    const url = new URL(window.location.href);
    if (selected.length) url.searchParams.set("compare", selected.join(","));
    else url.searchParams.delete("compare");
    window.history.replaceState(null, "", url);
  }, [selected, hydrated]);

  useEffect(() => {
    if (!hydrated || openedSharedComparison.current) return;
    openedSharedComparison.current = true;
    if (window.location.hash !== "#comparison" || selected.length === 0) return;
    const frame = requestAnimationFrame(() => compareRef.current?.scrollIntoView({ block: "start", behavior: "instant" }));
    return () => cancelAnimationFrame(frame);
  }, [hydrated, selected.length]);

  const subjects = useMemo(() => [...new Set(courses.flatMap(c => c.subjects))].sort(), [courses]);
  const selectedCourses = selected.map(id => courses.find(c => c.id === id)).filter((c): c is Course => !!c);
  const filtered = useMemo(() => courses.filter(c =>
    courseMatches(c, query) && (!level || c.level === level) && (!subject || c.subjects.includes(subject)) &&
    (!attendance || c.attendance?.toLowerCase().includes(attendance)) && (!savedOnly || saved.includes(c.id))),
    [courses, query, level, subject, attendance, savedOnly, saved]);

  function toggleCompare(id: string) {
    setNotice("");
    if (selected.includes(id)) setSelected(selected.filter(value => value !== id));
    else if (selected.length < 3) setSelected([...selected, id]);
    else setNotice("You can compare three programmes at a time. Remove one to add another.");
  }
  function toggleSaved(id: string) { setSaved(values => values.includes(id) ? values.filter(value => value !== id) : [...values, id]); }
  function reset() { setQuery(""); setLevel(""); setSubject(""); setAttendance(""); setSavedOnly(false); setLimit(24); }
  async function share() {
    const url = new URL(window.location.href);
    url.searchParams.set("compare", selected.join(","));
    url.hash = "comparison";
    try { await navigator.clipboard.writeText(url.toString()); setNotice("Comparison link copied. Anyone with the link can open these choices."); }
    catch { window.history.replaceState(null, "", url); setNotice("Copy the comparison link from your browser’s address bar."); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([comparisonCsv(selectedCourses)], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = "UL-course-comparison.csv"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const compareRows: { label: string; key?: keyof Course; value: (course: Course) => React.ReactNode }[] = [
    { label: "Study level", key: "level", value: c => c.level },
    { label: "Course code", key: "code", value: c => c.code || NOT_SPECIFIED },
    { label: "Duration", key: "duration", value: c => c.duration || NOT_SPECIFIED },
    { label: "Attendance", key: "attendance", value: c => c.attendance || NOT_SPECIFIED },
    { label: "Delivery", key: "delivery", value: c => c.delivery || NOT_SPECIFIED },
    { label: "NFQ level", key: "nfq", value: c => c.nfq || NOT_SPECIFIED },
    { label: "Start date", key: "start", value: c => c.start || NOT_SPECIFIED },
    { label: "Historical CAO points", key: "points", value: c => c.points ? <><strong>{c.points}</strong><span className="mt-1 block text-xs text-muted">Published for {c.pointsYear}. Future points may differ.</span></> : NOT_SPECIFIED },
    { label: "Entry guidance", key: "requirements", value: c => <><p className="text-sm leading-relaxed">{c.requirements || "Open the official page for the requirements for your applicant route."}</p><div className="mt-3"><SourceLink href={c.links["entry requirements"] || c.url}>Official entry page</SourceLink></div></> },
    { label: "Fees & funding", value: c => <>{(c.euFee || c.nonEuFee) && <div className="mb-3 space-y-2">{c.euFee && <p><span className="block text-xs text-muted">EU · published per year</span><strong>{c.euFee}</strong></p>}{c.nonEuFee && <p><span className="block text-xs text-muted">Non-EU · published per year</span><strong>{c.nonEuFee}</strong></p>}<p className="text-xs text-muted">Academic year not stated with these figures.</p></div>}<SourceLink href={c.links["fees and funding"] || "https://www.ul.ie/fees"}>Check official fee guidance</SourceLink></> },
    { label: "Source collected", value: c => <><span className="text-muted">{sourceDate(c.checkedAt)}</span><div className="mt-2"><SourceLink href={c.url}>View programme source</SourceLink></div></> },
  ];

  const visibleRows = onlyDifferences && selectedCourses.length > 1
    ? compareRows.filter(row => !row.key || new Set(selectedCourses.map(c => String(c[row.key!] ?? ""))).size > 1)
    : compareRows;

  return <>
    <SiteHeader />
    <main id="main" className="pb-28">
      <section className="course-hero overflow-hidden border-b border-border">
        <div className="mx-auto grid max-w-6xl gap-9 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[1.45fr_1fr] lg:items-center">
          <div>
            <p className="mb-5 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald"><span className="h-1.5 w-1.5 rounded-full bg-emerald" />The next chapter is yours</p>
            <h1 className="font-display text-5xl font-medium leading-[1.06] tracking-tight sm:text-6xl">Explore your options.<br /><span className="text-forest dark:text-emerald">Find your direction.</span></h1>
            <p className="mt-5 max-w-lg text-base leading-relaxed text-muted">A clearer way to explore UL programmes. Follow your interests, save the possibilities, and put the official facts side by side.</p>
            <div className="mt-7 flex flex-wrap gap-3"><Button asChild><a href="#find-courses">Find a programme<ArrowDown className="h-4 w-4" /></a></Button><Button asChild variant="outline"><Link href="/knowledge-health">Behind the information<ArrowUpRight className="h-4 w-4" /></Link></Button></div>
          </div>
          <div className="relative rounded-[24px] border border-border bg-surface/90 p-6 shadow-[8px_8px_0_var(--emerald-soft)] sm:p-7">
            <div className="mb-6 flex items-center justify-between"><span className="text-xs font-semibold uppercase tracking-widest text-muted">A little clarity goes a long way</span><Sparkles className="h-5 w-5 text-emerald" aria-hidden /></div>
            {[["01", "Follow your curiosity", "Search a subject, a course name or a CAO code."], ["02", "Keep your possibilities", "Your shortlist stays saved in this browser."], ["03", "See the difference", "Compare up to three programmes, with sources."]].map(([n, title, text]) => <div key={n} className="flex gap-4 border-t border-border py-4 last:pb-0"><span className="font-display text-2xl text-emerald/70">{n}</span><div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-1 text-xs leading-relaxed text-muted">{text}</p></div></div>)}
          </div>
        </div>
      </section>

      <section id="find-courses" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-9 sm:px-6">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs uppercase tracking-widest text-muted">Your possibilities</p><h2 className="mt-1 font-display text-3xl font-semibold">Find a programme</h2></div><div className="flex gap-2"><Badge><GraduationCap className="h-3.5 w-3.5" />{courses.length} programmes collected</Badge><Badge tone="green">Official UL sources</Badge></div></div>

        <div className="rounded-2xl border border-border bg-surface p-4 sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row"><div className="relative flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-muted" aria-hidden /><label htmlFor="course-search" className="sr-only">Search programmes</label><Input id="course-search" className="pl-10" placeholder="Try artificial intelligence, nursing, business or LM174…" value={query} onChange={e => { setQuery(e.target.value); setLimit(24); }} /></div><Button variant={savedOnly ? "primary" : "outline"} aria-pressed={savedOnly} onClick={() => { setSavedOnly(!savedOnly); setLimit(24); }}><Bookmark className="h-4 w-4" />My shortlist <span className="rounded-full bg-background/20 px-1.5 text-xs">{saved.length}</span></Button></div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3"><div><label htmlFor="course-level" className="mb-1 block text-xs text-muted">Study level</label><Select id="course-level" className="w-full" value={level} onChange={e => { setLevel(e.target.value); setLimit(24); }}><option value="">All study levels</option>{[...new Set(courses.map(c => c.level))].map(v => <option key={v}>{v}</option>)}</Select></div><div><label htmlFor="course-subject" className="mb-1 block text-xs text-muted">Area of interest</label><Select id="course-subject" className="w-full" value={subject} onChange={e => { setSubject(e.target.value); setLimit(24); }}><option value="">All subjects</option>{subjects.map(v => <option key={v}>{v}</option>)}</Select></div><div><label htmlFor="course-attendance" className="mb-1 block text-xs text-muted">Attendance</label><Select id="course-attendance" className="w-full" value={attendance} onChange={e => { setAttendance(e.target.value); setLimit(24); }}><option value="">Any attendance</option><option value="full-time">Full-time</option><option value="part-time">Part-time</option></Select></div></div>
          <div className="mt-4 flex flex-wrap items-center gap-2"><span className="mr-1 text-xs text-muted">Start with an interest</span>{["Computing & AI", "Business", "Health & sport", "Engineering"].map(value => <button key={value} onClick={() => { setSubject(subject === value ? "" : value); setLimit(24); }} aria-pressed={subject === value} className={cn("rounded-full border px-3 py-1.5 text-xs transition", subject === value ? "border-emerald bg-emerald-soft text-forest dark:text-emerald" : "border-border text-muted hover:border-emerald")}>{value}</button>)}</div>
        </div>

        <div className="my-5 flex items-center justify-between gap-3"><p className="text-sm text-muted" aria-live="polite"><strong className="font-semibold text-foreground">{filtered.length}</strong> {filtered.length === 1 ? "programme" : "programmes"}{savedOnly ? " in your shortlist" : " to explore"}</p><button onClick={reset} className="text-xs text-muted underline underline-offset-4">Reset filters</button></div>
        <div role="status" aria-live="polite" className={notice ? "fixed left-1/2 top-20 z-[60] flex w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 items-start gap-3 rounded-xl border border-emerald/40 bg-surface p-4 text-sm shadow-xl" : "sr-only"}><span className="flex-1">{notice}</span>{notice && <button aria-label="Dismiss notice" onClick={() => setNotice("")} className="rounded p-1 text-muted"><X className="h-4 w-4" /></button>}</div>

        {!filtered.length ? <EmptyState icon={<SlidersHorizontal className="h-7 w-7" />} title={savedOnly ? "Your next possibility is waiting" : "No programmes match these filters"}><p>{savedOnly ? "Tap the bookmark on a programme to keep it here." : "Try a broader subject or clear a filter."}</p><Button className="mt-4" variant="outline" onClick={reset}>Explore programmes</Button></EmptyState> : <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{filtered.slice(0, limit).map(course => <article key={course.id} className={cn("group flex flex-col rounded-2xl border bg-surface p-5 transition-shadow hover:shadow-md", selected.includes(course.id) ? "border-emerald ring-1 ring-emerald/20" : "border-border")}>
          <div className="flex items-center gap-2"><Badge tone="green">{course.code || course.award || (course.level === "Undergraduate" ? "Undergraduate" : "Postgraduate")}</Badge><button className="ml-auto rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-emerald" aria-label={`${saved.includes(course.id) ? "Unsave" : "Save"} ${course.title}`} aria-pressed={saved.includes(course.id)} onClick={() => toggleSaved(course.id)}><Bookmark className={cn("h-4 w-4", saved.includes(course.id) && "fill-emerald text-emerald")} /></button></div>
          <h3 className="mt-3 font-display text-xl font-semibold leading-snug">{course.title}</h3>
          <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-muted">{course.summary || `Explore this ${course.level.toLowerCase()} programme in UL’s official course information.`}</p>
          <dl className="mb-5 mt-5 grid grid-cols-2 gap-4"><Fact label="Duration" value={course.duration} /><Fact label="Attendance" value={course.attendance} /></dl>
          <div className="mt-auto border-t border-border pt-4"><div className="flex items-center justify-between gap-2"><button onClick={() => setDetail(course)} className="inline-flex items-center gap-1 text-sm font-medium text-emerald" aria-label={`View ${course.title}`}>View details<ArrowRight className="h-4 w-4" /></button><Button size="sm" variant={selected.includes(course.id) ? "subtle" : "outline"} onClick={() => toggleCompare(course.id)} aria-pressed={selected.includes(course.id)} aria-label={`Compare ${course.title}`}>{selected.includes(course.id) ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}Compare</Button></div><p className="mt-4 text-[10px] text-muted">Source collected {sourceDate(course.checkedAt)}</p></div>
        </article>)}</div>}
        {filtered.length > limit && <div className="mt-7 text-center"><Button variant="outline" onClick={() => setLimit(limit + 24)}>Show more programmes<Plus className="h-4 w-4" /></Button></div>}
        <p className="mt-7 text-xs leading-relaxed text-muted">This is a collected selection of UL programmes, updated {sourceDate(generatedAt)}. Programmes and requirements can change; check the linked official pages before applying. <Link className="underline underline-offset-4" href="/knowledge-health">See what’s covered</Link>.</p>
      </section>

      {selectedCourses.length > 0 && <section ref={compareRef} id="comparison" className="mx-auto max-w-6xl scroll-mt-20 px-4 pb-8 pt-3 sm:px-6">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs uppercase tracking-widest text-muted">The facts, side by side</p><h2 className="mt-1 font-display text-3xl font-semibold">Your comparison</h2></div><div className="flex flex-wrap gap-2"><Button variant={onlyDifferences ? "subtle" : "outline"} size="sm" aria-pressed={onlyDifferences} disabled={selectedCourses.length < 2} onClick={() => setOnlyDifferences(!onlyDifferences)}>Differences only</Button><Button variant="outline" size="sm" onClick={share}><Share2 className="h-4 w-4" />Share</Button><Button variant="outline" size="sm" onClick={download}><Download className="h-4 w-4" />Download CSV</Button></div></div>
        <div className="overflow-x-auto rounded-2xl border border-border bg-surface" tabIndex={0} role="region" aria-label="Programme comparison table"><table className="w-full min-w-[640px] table-fixed border-collapse text-left"><caption className="sr-only">Official programme facts. Empty fields are explicitly marked. Historical CAO points do not predict future entry.</caption><thead><tr><th className="w-36 border-b border-border p-4 align-top text-xs font-normal text-muted sm:w-44" scope="col">Your possibilities<br /><span className="mt-2 block">{selectedCourses.length} of 3 selected</span></th>{selectedCourses.map(c => <th key={c.id} className="border-b border-l border-border p-5 align-top" scope="col"><div className="flex items-start gap-2"><span className="font-display text-lg font-semibold">{c.title}</span><button onClick={() => toggleCompare(c.id)} className="ml-auto rounded p-1 text-muted hover:bg-surface-2" aria-label={`Remove ${c.title} from comparison`}><X className="h-4 w-4" /></button></div><span className="mt-2 block text-xs font-normal text-muted">{c.code || c.level}</span></th>)}</tr></thead><tbody>{visibleRows.map(row => <tr key={row.label} className="border-b border-border last:border-0"><th scope="row" className="bg-surface-2/50 p-4 align-top text-xs font-medium text-muted">{row.label}</th>{selectedCourses.map(course => <td key={course.id} className="border-l border-border p-5 align-top text-sm leading-relaxed">{row.value(course)}</td>)}</tr>)}</tbody></table></div>
        <p className="mt-3 text-xs leading-relaxed text-muted">{onlyDifferences && selectedCourses.length > 1 ? "Rows with the same recorded values are hidden. Source and fee guidance stays available. " : ""}CAO points refer to the stated past admissions year. Entry guidance is an extract; applicant routes and qualifications may differ. Fee eligibility and academic-year charges must be checked with UL.</p>
      </section>}

      {!!selected.length && <aside className="fixed inset-x-3 bottom-3 z-40 mx-auto max-w-4xl rounded-2xl border border-emerald/30 bg-surface/95 p-3 shadow-xl backdrop-blur-lg sm:inset-x-6 sm:p-4" aria-label="Comparison selection"><div className="flex items-center gap-3"><div className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-soft text-emerald sm:flex"><Layers3 className="h-5 w-5" /></div><div className="min-w-0 flex-1"><p className="text-sm font-semibold">{selected.length} of 3 selected</p><p className="truncate text-xs text-muted">{selectedCourses.map(c => c.code || c.title).join(" · ")}</p></div><button onClick={() => setSelected([])} className="px-2 text-xs text-muted underline underline-offset-4">Clear</button><Button size="sm" onClick={() => compareRef.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "start" })}>Compare<ArrowDown className="h-4 w-4" /></Button></div></aside>}

      <Dialog open={!!detail} onOpenChange={open => { if (!open) setDetail(null); }}><DialogContent title={detail?.title || "Programme details"} description="Published facts with links to the official University of Limerick sources.">{detail && <>
        <div className="mb-4 flex flex-wrap gap-2"><Badge tone="green">{detail.level}</Badge>{detail.code && <Badge>{detail.code}</Badge>}</div><p className="text-sm leading-relaxed text-muted">{detail.summary}</p>
        <dl className="my-6 grid grid-cols-2 gap-5 rounded-xl bg-surface-2 p-4"><Fact label="Duration" value={detail.duration} /><Fact label="Attendance" value={detail.attendance} /><Fact label="NFQ level" value={detail.nfq} /><Fact label="Delivery" value={detail.delivery} /><Fact label="Start date" value={detail.start} /><Fact label={detail.pointsYear ? `CAO points ${detail.pointsYear}` : "CAO points"} value={detail.points} /></dl>
        <div className="space-y-3"><h3 className="font-semibold">Entry guidance</h3><p className="text-sm leading-relaxed text-muted">{detail.requirements || "The entry details for this programme have not yet been collected. Use the official entry page to check your applicant route."}</p><SourceLink href={detail.links["entry requirements"] || detail.url}>Check the full entry requirements</SourceLink></div>
        {(detail.euFee || detail.nonEuFee) && <section className="mt-6 rounded-xl bg-surface-2 p-4"><h3 className="text-sm font-semibold">Published annual fees</h3><dl className="mt-3 grid grid-cols-2 gap-4"><Fact label="EU" value={detail.euFee || null} /><Fact label="Non-EU" value={detail.nonEuFee || null} /></dl><p className="mt-3 text-xs text-muted">Academic year not stated with these figures. Check fee eligibility and charges with UL.</p></section>}
        <div className="mt-6 flex flex-wrap gap-x-5 gap-y-3 border-t border-border pt-5"><SourceLink href={detail.links["fees and funding"] || "https://www.ul.ie/fees"}>Fees & funding</SourceLink>{detail.links["course content"] && <SourceLink href={detail.links["course content"]}>What you’ll study</SourceLink>}<SourceLink href={detail.url}>Programme source</SourceLink></div>
        <p className="mt-4 flex items-center gap-1 text-xs text-muted"><Clock3 className="h-3 w-3" />Programme source collected {sourceDate(detail.checkedAt)}{detail.requirementsCheckedAt ? ` · Entry page checked ${sourceDate(detail.requirementsCheckedAt)}` : ""}</p>
        <div className="mt-6 flex flex-wrap gap-2"><Button asChild variant="outline"><Link href={`/curricula?course=${detail.id}`}>Modules by semester<BookOpen className="h-4 w-4" /></Link></Button><Button onClick={() => toggleCompare(detail.id)} variant={selected.includes(detail.id) ? "subtle" : "primary"}>{selected.includes(detail.id) ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}{selected.includes(detail.id) ? "In comparison" : "Add to comparison"}</Button><Button asChild variant="outline"><Link href={`/chat?q=${encodeURIComponent(`Tell me about ${detail.title} at UL. Cite official sources and distinguish any missing information.`)}`}>Ask about this programme<ArrowRight className="h-4 w-4" /></Link></Button></div>
      </>}</DialogContent></Dialog>
    </main><SiteFooter />
  </>;
}
