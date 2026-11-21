"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, CheckCircle2, Plus, RotateCcw, Target, Trash2, TriangleAlert } from "lucide-react";
import { SiteHeader, SiteFooter } from "@/components/site";
import { Badge, Button, Card, Input, Select } from "@/components/ui";
import { exampleMix, gradeRules, projectGrades, type PlannedModule } from "@/lib/grade-planner";

const initialModules = (): PlannedModule[] => Array.from({ length: 5 }, (_, i) => ({ id: `example-${i}`, name: "", credits: "6", grade: "B1", include: true }));
const f = (n: number) => n.toFixed(3);

export function GradePlanner() {
  const [current, setCurrent] = useState("3.10");
  const [completed, setCompleted] = useState("60");
  const [target, setTarget] = useState("3.30");
  const [modules, setModules] = useState(initialModules);
  const [example, setExample] = useState(true);
  const result = projectGrades(current, completed, target, modules);
  const update = (id: string, patch: Partial<PlannedModule>) => { setExample(false); setModules(rows => rows.map(m => m.id === id ? { ...m, ...patch } : m)); };
  const applyGrade = (grade: string) => { setExample(false); setModules(rows => rows.map(m => m.include ? { ...m, grade } : m)); };
  const reset = () => { setCurrent("3.10"); setCompleted("60"); setTarget("3.30"); setModules(initialModules()); setExample(true); };

  return <><SiteHeader /><main id="main" className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
      <div className="max-w-2xl"><Badge tone="green"><Target className="h-3 w-3" /> Plan your next step</Badge>
        <h1 className="mt-4 font-display text-4xl leading-tight sm:text-5xl">A clearer path to your target.</h1>
        <p className="mt-4 text-muted">See what your remaining grades could mean for your QCA. Explore a realistic mix, adjust each module, and compare it with your goal.</p>
      </div>
      <Button variant="outline" onClick={reset}><RotateCcw className="h-4 w-4" /> Reset example</Button>
    </div>
    <p className="mb-6 rounded-xl border border-border bg-surface px-4 py-3 text-sm text-muted">{example ? "Example inputs — replace these with your own. " : "Your scenario. "}Calculations run in your browser. Your grades are not sent to the AI or saved.</p>
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-6">
        <Card className="p-5 sm:p-6"><h2 className="text-lg font-semibold">1. Your starting point</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <label className="space-y-2 text-sm">Current QCA<Input aria-label="Current QCA" type="number" min="0" max="4" step="0.01" value={current} onChange={e => { setCurrent(e.target.value); setExample(false); }} /></label>
            <label className="space-y-2 text-sm">Counted credits<Input aria-label="Completed counted credits" type="number" min="0" max="600" step="0.5" value={completed} onChange={e => { setCompleted(e.target.value); setExample(false); }} /></label>
            <label className="space-y-2 text-sm">Target QCA<Input aria-label="Target QCA" type="number" min="0" max="4" step="0.01" value={target} onChange={e => { setTarget(e.target.value); setExample(false); }} /></label>
          </div>
          <p className="mt-4 text-xs leading-relaxed text-muted">Use credits that count towards this QCA. If your programme weights years differently, apply the same weighting to both completed and remaining credits. A rounded current QCA makes this an estimate.</p>
          <div className="mt-4 flex flex-wrap gap-2" aria-label="Choose target band">{gradeRules.classifications.map(c => <Button key={c.min_qca} size="sm" variant={Number(target) === c.min_qca ? "subtle" : "outline"} aria-pressed={Number(target) === c.min_qca} onClick={() => { setTarget(c.min_qca.toFixed(2)); setExample(false); }}>{c.min_qca.toFixed(2)} · {c.label.startsWith("First") ? "First" : c.label.includes("2.1") ? "2.1" : c.label.includes("2.2") ? "2.2" : "Third"}</Button>)}</div>
        </Card>
        <Card className="p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">2. Explore your remaining modules</h2><span className="text-xs text-muted">Up to 40 modules</span></div>
          <div className="my-4 flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => applyGrade("B1")}>All B1</Button><Button size="sm" variant="outline" onClick={() => applyGrade("A2")}>All A2</Button><Button size="sm" variant="outline" onClick={() => applyGrade("A1")}>All A1</Button></div>
          <ol className="space-y-3">{modules.map((m, i) => <li key={m.id} className="rounded-xl border border-border bg-background p-3">
            <div className="mb-3 flex items-center justify-between gap-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={m.include} onChange={e => update(m.id, { include: e.target.checked })} aria-label={`Include module ${i + 1}`} className="accent-[var(--emerald)]" />Module {i + 1}</label><Button variant="ghost" size="icon" aria-label={`Remove planned module ${i + 1}`} disabled={modules.length === 1} onClick={() => { setExample(false); setModules(rows => rows.filter(r => r.id !== m.id)); }}><Trash2 className="h-4 w-4" /></Button></div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-[minmax(0,1fr)_90px_120px]">
              <label className="col-span-2 space-y-1 text-xs text-muted sm:col-span-1">Name (optional)<Input aria-label={`Planned module ${i + 1} name`} value={m.name} placeholder="e.g. Machine Learning" maxLength={80} onChange={e => update(m.id, { name: e.target.value })} /></label>
              <label className="space-y-1 text-xs text-muted">Credits<Input aria-label={`Planned module ${i + 1} credits`} type="number" min="0.5" max="60" step="0.5" value={m.credits} onChange={e => update(m.id, { credits: e.target.value })} /></label>
              <label className="space-y-1 text-xs text-muted">Expected grade<Select className="w-full" aria-label={`Planned module ${i + 1} grade`} value={m.grade} onChange={e => update(m.id, { grade: e.target.value })}>{gradeRules.grades.map(g => <option key={g.grade} value={g.grade}>{g.grade} · {g.qpv.toFixed(1)}</option>)}</Select></label>
            </div>
          </li>)}</ol>
          <Button variant="outline" className="mt-4" disabled={modules.length >= 40} onClick={() => { setExample(false); setModules(rows => [...rows, { id: crypto.randomUUID(), name: "", credits: "6", grade: "B1", include: true }]); }}><Plus className="h-4 w-4" /> Add module</Button>
          <p className="mt-4 text-xs text-muted">Untick pass/fail-only outcomes such as P and N. F and NG count at 0 QPV; D1 is a compensating fail. Repeat caps and progression rules need separate checking.</p>
        </Card>
      </div>
      <aside id="projection" className="scroll-mt-20 space-y-4 lg:sticky lg:top-20" aria-label="Your projection">
        <Card className="overflow-hidden border-emerald/40"><div className="bg-emerald-soft p-5 sm:p-6"><p className="text-xs font-semibold uppercase tracking-widest text-muted">Your projected QCA</p>
          {"error" in result ? <p className="mt-4 text-sm" role="alert">{result.error}</p> : <>
            <div className="mt-3 flex items-end gap-3"><span className="font-display text-6xl tabular-nums">{f(result.projected)}</span><span className="pb-2 text-sm text-muted">/ 4.000</span></div>
            <p className="mt-2 text-sm">{result.band}</p><p className="mt-1 text-xs text-muted">Indicative band for the credits entered</p>
          </>}
        </div>{!("error" in result) && <div className="space-y-5 p-5 sm:p-6" aria-live="polite" aria-atomic="true">
          <div className="flex items-start gap-2 text-sm">{result.reached ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald" /> : <Target className="mt-0.5 h-4 w-4 shrink-0 text-emerald" />}<p>{result.reached ? "This scenario reaches your numeric target." : result.possible ? "Your target is within mathematical reach. Adjust your expected grades to explore it." : "Even all A1 grades would fall short with these credits. Try a revised target or check which credits count."}</p></div>
          <dl className="space-y-4 text-sm"><div className="flex justify-between gap-3"><dt className="text-muted">Target</dt><dd className="font-semibold tabular-nums">{f(result.goal)}</dd></div><div className="flex justify-between gap-3"><dt className="text-muted">Remaining counted credits</dt><dd>{result.remaining}</dd></div><div className="border-t border-border pt-4"><dt className="text-muted">Average QPV needed in remaining modules</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{result.required <= 0 ? "0.000" : f(result.required)}<span className="ml-2 text-xs font-normal text-muted">{!result.possible ? "above the 4.0 maximum" : "/ 4.000"}</span></dd></div><div className="flex justify-between gap-3"><dt className="text-muted">Best possible QCA (all A1)</dt><dd className="tabular-nums">{f(result.maximum)}</dd></div></dl>
          <Button className="w-full" disabled={!result.possible} onClick={() => { const mix = exampleMix(modules, result.required); if (mix) { setModules(mix); setExample(false); } }}>Apply one example grade mix <ArrowUpRight className="h-4 w-4" /></Button>
          <p className="text-xs leading-relaxed text-muted">The example uses adjacent passing grades and enough upgraded module credits to meet your target. It is one possible combination, not a prediction of your results.</p>
          {result.deficient && <p className="flex gap-2 text-sm text-amber-700 dark:text-amber-300"><TriangleAlert className="h-4 w-4 shrink-0" />This scenario contains D1, F or NG. A numeric QCA target does not establish progression or graduation eligibility.</p>}
          <details className="text-xs text-muted"><summary className="cursor-pointer">See the calculation</summary><p className="mt-2 leading-relaxed">Required average = (target × total counted credits − current QCA × completed counted credits) ÷ remaining counted credits. Calculations use full precision; results are displayed to three decimals.</p></details>
        </div>}</Card>
        <Card className="p-5 text-xs leading-relaxed text-muted"><p className="font-semibold text-foreground">Grounded in UL’s 2026/27 rules</p><p className="mt-2">Programme weighting, repeat restrictions and award eligibility can change the official result. Confirm which semesters and credits count with Academic Registry.</p><a href={gradeRules.sources[0].url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-emerald underline underline-offset-4">Read the official handbook <ArrowUpRight className="h-3 w-3" /></a><p className="mt-2">PDF pages 13–15: grades and bands. Page 26: QCA formula and weighting.</p><Link href="/tools#qca" className="mt-3 block text-emerald underline underline-offset-4">Calculate QCA from existing grades</Link></Card>
      </aside>
    </div>
    {!("error" in result) && <a href="#projection" className="sticky bottom-3 z-30 mt-5 flex items-center justify-between gap-3 rounded-xl border border-emerald/40 bg-surface px-4 py-3 text-sm shadow-lg lg:hidden"><span>Projected QCA <strong className="ml-1 tabular-nums">{f(result.projected)}</strong></span><span className="text-emerald">See projection ↑</span></a>}
  </main><SiteFooter /></>;
}
