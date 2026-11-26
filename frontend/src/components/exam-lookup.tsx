"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CalendarDays, Clock3, ExternalLink, Loader2, MapPin, Search } from "lucide-react";
import { SiteFooter, SiteHeader } from "./site";
import { Badge, Button, Card, Input } from "./ui";
import { api } from "@/lib/api";

type Exam = { module: string; name: string; date_iso: string; time: string; day: string; building: string; location: string; information: string };
type Result = { module: string; status: "found" | "stale" | "not_listed" | "unavailable" | "session_mismatch"; session: string | null; academic_year: string | null; checked_at: string | null; source_url: string; note: string; rows: Exam[] };
const OFFICIAL = "https://www.timetable.ul.ie/UA/ExamModuleTimetable.aspx";
const valid = (code: string) => /^[A-Z]{2,4}\d{4}[A-Z]?$/.test(code);

export function ExamLookup() {
  const params = useSearchParams();
  const initial = (params.get("module") || "").trim().toUpperCase();
  const [code, setCode] = useState(initial);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef<AbortController | null>(null);
  const lookup = useCallback(async (raw: string) => {
    const module = raw.trim().toUpperCase();
    if (!valid(module)) { setError("Enter a module code such as CS4141."); return; }
    pending.current?.abort();
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setError(""); setResult(null);
    try {
      const value = await api<Result>(`/api/exams/${encodeURIComponent(module)}`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(45_000)]) });
      if (!controller.signal.aborted) setResult(value);
    } catch { if (!controller.signal.aborted) setError("The lookup could not complete. Try again shortly or open UL’s official timetable below."); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }, []);
  useEffect(() => { if (valid(initial)) { setCode(initial); void lookup(initial); } return () => pending.current?.abort(); }, [initial, lookup]);

  return <><SiteHeader /><main id="main" className="mx-auto max-w-4xl px-4 py-12 sm:px-6">
    <Badge tone="green"><CalendarDays className="h-3.5 w-3.5" /> Published timetable lookup</Badge>
    <h1 className="mt-5 font-display text-4xl font-semibold sm:text-5xl">Your module. Your exam details.</h1>
    <p className="mt-4 max-w-2xl leading-relaxed text-muted">Look up a module in UL’s currently published examination timetable. Check the session, date, time and venue together.</p>
    <form className="mt-8 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void lookup(code); }}>
      <label className="min-w-0 flex-1 space-y-2 text-sm font-medium">Module code<Input value={code} onChange={e => setCode(e.target.value.toUpperCase())} placeholder="e.g. CS4141" maxLength={10} autoCapitalize="characters" autoComplete="off" /></label>
      <Button type="submit" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}{busy ? "Checking UL…" : "Find exam"}</Button>
    </form>
    <p className="mt-3 text-xs leading-relaxed text-muted">Only the module code is submitted to UL’s public form. No student login or personal timetable is accessed. Verified results can be reused for up to 10 minutes.</p>
    {busy && <p role="status" className="mt-6 text-sm text-muted">Checking the published exam session and module details…</p>}
    {error && <p role="alert" className="mt-6 rounded-xl border border-warning/40 p-4 text-sm">{error}</p>}
    {result && <section className="mt-8 space-y-4" aria-label="Exam lookup results" aria-live="polite">
      <div className="flex flex-wrap items-center gap-3"><h2 className="text-xl font-semibold">{result.module}</h2><Badge tone={result.status === "found" ? "green" : "warn"}>{result.status === "found" ? "Published result" : result.status === "stale" ? "Older saved result — not reverified" : "No current appointment confirmed"}</Badge></div>
      {result.session && <p className="font-medium">Published session: {result.session} {result.academic_year}</p>}
      <p className="rounded-xl border border-border bg-surface p-4 text-sm leading-relaxed">{result.note}</p>
      {result.rows.map((exam, i) => <Card key={`${exam.date_iso}-${exam.time}-${i}`} className="p-6">
        <h3 className="font-semibold">{exam.name}</h3>
        <dl className="mt-5 grid gap-5 sm:grid-cols-3">
          <div><dt className="flex items-center gap-2 text-xs text-muted"><CalendarDays className="h-4 w-4" />Published date</dt><dd className="mt-2 font-semibold">{new Date(exam.date_iso + "T00:00:00Z").toLocaleDateString("en-IE", { day:"numeric", month:"long", year:"numeric", timeZone:"UTC" })}</dd><dd className="mt-1 text-sm text-muted">{exam.day}</dd></div>
          <div><dt className="flex items-center gap-2 text-xs text-muted"><Clock3 className="h-4 w-4" />Published time</dt><dd className="mt-2 text-2xl font-semibold tabular-nums">{exam.time}</dd></div>
          <div><dt className="flex items-center gap-2 text-xs text-muted"><MapPin className="h-4 w-4" />Published venue</dt><dd className="mt-2 font-semibold">{exam.building || "Not stated"}</dd><dd className="mt-1 text-sm">{exam.location || "Location not stated"}</dd></div>
        </dl>
        {exam.information && <p className="mt-4 text-sm text-muted">Published information: {exam.information}</p>}
      </Card>)}
      {result.checked_at && <p className="text-xs text-muted">Source checked {new Date(result.checked_at).toLocaleString("en-IE", { timeZone:"UTC" })} UTC. This is a source-check time, not the timetable’s publication date.</p>}
    </section>}
    <Card className="mt-8 p-6"><h2 className="font-semibold">Check before you travel.</h2><p className="mt-3 text-sm leading-relaxed text-muted">Timetables can change. A published module venue does not confirm your personal seat, registration or accommodations. Missing results do not mean you have no exam. Confirm your own arrangements with UL.</p><a href={OFFICIAL} target="_blank" rel="noreferrer" className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-emerald underline underline-offset-4">Open the official UL Module Exam Timetable<ExternalLink className="h-4 w-4" /></a></Card>
  </main><SiteFooter /></>;
}
