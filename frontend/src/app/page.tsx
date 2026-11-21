"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, BookOpenCheck, Calculator, CalendarDays, FileSearch, Globe2, GraduationCap,
  Home, Layers, Library, Quote, Search, ShieldCheck, Sparkles, Wallet,
} from "lucide-react";
import { SiteFooter, SiteHeader, DISCLAIMER, UniversityResourceMark } from "@/components/site";
import { Button, Card, Skeleton } from "@/components/ui";
import { api, fmtDate, label, type Stats } from "@/lib/api";

const POPULAR = [
  { q: "How is QCA calculated at UL?", icon: Calculator },
  { q: "When does the 2026/27 autumn semester start?", icon: CalendarDays },
  { q: "How do I apply for on-campus accommodation?", icon: Home },
  { q: "What do international students need before arriving?", icon: Globe2 },
  { q: "What undergraduate scholarships are available?", icon: GraduationCap },
  { q: "How and when are tuition fees paid?", icon: Wallet },
];

const FEATURES = [
  { icon: ShieldCheck, title: "Grounded in official sources", body: "The assistant searches public UL pages and documents, and tells you when it cannot find reliable evidence." },
  { icon: Quote, title: "Citations you can check", body: "Open the source passages used in an answer, with the section, PDF page and collection date where available." },
  { icon: Layers, title: "The right detail first", body: "For tuition and entry questions, the assistant asks which programme, year or applicant route matters before looking for a specific answer." },
  { icon: CalendarDays, title: "Academic-year aware", body: "Sources show their academic year where known, so you can check whether the information applies to your case." },
  { icon: Calculator, title: "Student tools", body: "Compare courses, explore a grade target, calculate QCA and use a practical arrival checklist." },
  { icon: Library, title: "Open knowledge explorer", body: "Browse and search every indexed source, filter by category and year, and preview the content." },
];

const STEPS = [
  { t: "Ask", d: "Start with the question on your mind, in your own words." },
  { t: "Add context", d: "Share the programme, year or applicant route when a precise answer needs it." },
  { t: "Read", d: "Follow the answer as it appears, with links to the official source passages used." },
  { t: "Check", d: "Open a citation and confirm important decisions with the relevant UL office." },
  { t: "Take a step", d: "Compare a course, plan your grades or work through your arrival checklist." },
];

function StatsPanel() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    api<Stats>("/api/stats").then(setStats).catch(() => setErr(true));
  }, []);
  const items = stats
    ? [
        { k: "Indexed sources", v: stats.documents.toLocaleString() },
        { k: "Searchable passages", v: stats.chunks.toLocaleString() },
        { k: "PDF pages processed", v: stats.pdf_pages.toLocaleString() },
        { k: "Last synchronised", v: fmtDate(stats.last_synced) },
      ]
    : [];
  return (
    <Card className="p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-xl font-semibold">Live knowledge base</h2>
        {stats ? (
          <Link href="/knowledge-health" className="text-xs text-emerald underline underline-offset-4">See coverage and gaps</Link>
        ) : null}
      </div>
      {err ? (
        <p className="text-sm text-muted">Live coverage is temporarily unavailable. You can still browse courses and use the grade planner.</p>
      ) : !stats ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}
        </div>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {items.map((s) => (
              <div key={s.k} className="rounded-xl bg-surface-2 p-4">
                <dt className="text-xs text-muted">{s.k}</dt>
                <dd className="mt-1 text-2xl font-semibold tabular-nums">{s.v}</dd>
              </div>
            ))}
          </dl>
          {Object.keys(stats.categories).length > 0 ? (
            <div className="mt-5 flex flex-wrap gap-2">
              {Object.entries(stats.categories).sort((a, b) => b[1] - a[1]).map(([c, n]) => (
                <Link key={c} href={`/explorer?category=${c}`} className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:border-emerald hover:text-foreground">
                  {label(c)} · {n}
                </Link>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted">The source collection is being prepared. Please check back for coverage details.</p>
          )}
        </>
      )}
    </Card>
  );
}

export default function Landing() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const go = (text: string) => {
    const t = text.trim();
    if (t) router.push(`/chat?q=${encodeURIComponent(t)}`);
  };
  return (
    <>
      <SiteHeader />
      <main id="main">
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="glow pointer-events-none absolute inset-0" />
          <div className="bg-grid pointer-events-none absolute inset-0" />
          <div className="relative mx-auto max-w-4xl px-4 pb-14 pt-14 text-center sm:px-6 sm:pt-20">
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
              <UniversityResourceMark />
              <p className="mt-4 text-xs font-medium uppercase tracking-widest text-emerald">Public beta · Your independent student companion</p>
            </motion.div>
            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.05 }}
              className="font-display mt-6 text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl"
            >
              Your next step at UL,{" "}
              <span className="text-forest dark:text-emerald">made clearer.</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.12 }}
              className="mx-auto mt-5 max-w-2xl text-lg text-muted"
            >
              Choose a course. Plan your grades. Find answers about student life—with official University of Limerick sources you can check.
            </motion.p>
            <motion.form
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              onSubmit={(e) => { e.preventDefault(); go(q); }}
              className="mx-auto mt-9 flex max-w-2xl items-center gap-2 rounded-2xl border border-border bg-surface p-2 shadow-[0_10px_40px_-12px_rgba(16,90,60,0.25)] focus-within:border-emerald"
              role="search"
            >
              <Search className="ml-2 h-5 w-5 shrink-0 text-muted" aria-hidden />
              <label htmlFor="hero-q" className="sr-only">Ask a question about UL</label>
              <input
                id="hero-q"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="e.g. When are accommodation fees due?"
                className="h-12 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted/70"
                maxLength={2000}
                autoComplete="off"
              />
              <Button type="submit" size="lg" disabled={!q.trim()} aria-label="Ask">
                Ask <ArrowRight className="h-4 w-4" />
              </Button>
            </motion.form>
            <p className="mt-4 text-xs text-muted">{DISCLAIMER}</p>
          </div>
        </section>

        <section className="mx-auto mb-10 max-w-6xl px-4 sm:px-6" aria-label="Choose your next step">
          <div className="grid gap-4 md:grid-cols-3">
            {[{href:"/courses",icon:GraduationCap,eyebrow:"Exploring your options",title:"Find your course.",body:"Build a shortlist and compare programme details from official course pages.",action:"Explore courses"},
              {href:"/grade-planner",icon:Calculator,eyebrow:"Working towards a goal",title:"Plan your grades.",body:"See the average you need, try a grade mix and test what is within reach.",action:"Open grade planner"},
              {href:"/tools#checklist",icon:Globe2,eyebrow:"Getting ready for UL",title:"Make a confident start.",body:"Work through an arrival checklist and find practical tools for student life.",action:"Explore student tools"}].map(({href,icon:Icon,eyebrow,title,body,action})=><Link key={href} href={href} className="group rounded-2xl border border-border bg-surface p-6 transition hover:-translate-y-1 hover:border-emerald/60 hover:shadow-md"><Icon className="h-7 w-7 text-emerald" /><p className="mt-5 text-xs uppercase tracking-widest text-muted">{eyebrow}</p><h2 className="mt-2 font-display text-2xl font-semibold">{title}</h2><p className="mt-3 text-sm leading-relaxed text-muted">{body}</p><span className="mt-5 inline-flex items-center gap-1 text-sm font-medium text-emerald">{action}<ArrowRight className="h-4 w-4" /></span></Link>)}
          </div>
          <p className="mt-4 text-center text-xs text-muted">Our collection is growing. <Link href="/knowledge-health" className="text-emerald underline underline-offset-4">Check what is covered and what still needs checking.</Link></p>
        </section>

        {/* Popular questions */}
        <section className="mx-auto max-w-6xl px-4 sm:px-6" aria-labelledby="popular">
          <h2 id="popular" className="mb-4 text-sm font-medium uppercase tracking-wider text-muted">Popular questions</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {POPULAR.map(({ q: text, icon: Icon }, i) => (
              <motion.button
                key={text}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                onClick={() => go(text)}
                className="group flex items-center gap-3 rounded-xl border border-border bg-surface p-4 text-left text-sm transition hover:-translate-y-0.5 hover:border-emerald/60 hover:shadow-md"
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-emerald-soft text-forest dark:text-emerald"><Icon className="h-4 w-4" /></span>
                <span className="flex-1">{text}</span>
                <ArrowRight className="h-4 w-4 text-muted opacity-0 transition group-hover:opacity-100" />
              </motion.button>
            ))}
          </div>
        </section>

        {/* Stats */}
        <section className="mx-auto mt-16 max-w-6xl px-4 sm:px-6">
          <StatsPanel />
        </section>

        {/* Features */}
        <section className="mx-auto mt-20 max-w-6xl px-4 sm:px-6" aria-labelledby="features">
          <h2 id="features" className="font-display text-3xl font-semibold tracking-tight">Built to be trusted</h2>
          <p className="mt-2 max-w-2xl text-muted">University information is high-stakes. UL Navigator AI is designed to show its work and to say “I don't know” rather than invent an answer.</p>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, body }, i) => (
              <motion.div key={title} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
                <Card className="h-full p-6">
                  <Icon className="h-6 w-6 text-emerald" aria-hidden />
                  <h3 className="mt-4 font-semibold">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="mx-auto mt-20 max-w-6xl scroll-mt-20 px-4 sm:px-6" aria-labelledby="how">
          <h2 id="how" className="font-display text-3xl font-semibold tracking-tight">From a question to a next step</h2>
          <p className="mt-2 max-w-2xl text-muted">A simple way to find useful information, check the evidence and decide what to do next.</p>
          <ol className="mt-8 grid gap-4 md:grid-cols-5">
            {STEPS.map((s, i) => (
              <motion.li key={s.t} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }} className="relative rounded-2xl border border-border bg-surface p-5">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-forest text-sm font-semibold text-white">{i + 1}</span>
                <h3 className="mt-3 font-semibold">{s.t}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{s.d}</p>
              </motion.li>
            ))}
          </ol>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <Card className="p-5 text-sm"><FileSearch className="mb-2 h-5 w-5 text-emerald" /><b>Check the original.</b> <span className="text-muted">Read the linked university page alongside the answer. Source coverage is growing, and details can change.</span></Card>
            <Card className="p-5 text-sm"><ShieldCheck className="mb-2 h-5 w-5 text-emerald" /><b>Know when to ask UL.</b> <span className="text-muted">Confirm decisions about immigration, fees and academic rules with the relevant university office.</span></Card>
            <Card className="p-5 text-sm"><BookOpenCheck className="mb-2 h-5 w-5 text-emerald" /><b>Help it improve.</b> <span className="text-muted">Use the feedback buttons on an answer to tell the project maintainer what was useful or needs attention.</span></Card>
          </div>
          <div className="mt-12 flex justify-center pb-6">
            <Button asChild size="lg"><Link href="/chat">Ask your first question <ArrowRight className="h-4 w-4" /></Link></Button>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
