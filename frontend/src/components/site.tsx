"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, Moon, Sun, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./ui";

export const DISCLAIMER =
  "UL Navigator AI is an independent student-led project and is not an official University of Limerick service.";

/** Official source identity, kept separate from the independent product's own mark. */
export function UniversityResourceMark({ compact = false }: { compact?: boolean }) {
  return <a href="https://www.ul.ie/" target="_blank" rel="noreferrer" aria-label="University of Limerick — official website" className={cn("inline-flex items-center gap-3 rounded-xl border border-border bg-white px-3 py-2", compact ? "" : "text-left")}>
    {/* The official site's SVG is served locally, preserving its original paths and proportions. */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src="/ul-logo.svg" width="148" height="68" alt="University of Limerick" className={compact ? "h-10 w-auto" : "h-14 w-auto"} />
    {!compact && <span className="border-l border-[#005C46]/15 pl-3 text-[11px] leading-relaxed text-[#005C46]">Official UL resources<br /><span className="font-semibold">Independent student companion</span></span>}
  </a>;
}

/** Original mark: a compass needle inside a rounded leaf - no UL branding. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <defs>
          <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--emerald)" />
            <stop offset="1" stopColor="var(--forest)" />
          </linearGradient>
        </defs>
        <path d="M16 2c7.7 0 14 6.3 14 14 0 7.7-6.3 14-14 14C8.3 30 2 23.7 2 16 2 8.3 8.3 2 16 2Z" fill="url(#lg)" />
        <path d="M16 7l3.4 9L16 25l-3.4-9L16 7Z" fill="#fff" opacity="0.95" />
        <path d="M16 7l3.4 9h-6.8L16 7Z" fill="#fff" />
        <circle cx="16" cy="16" r="1.6" fill="var(--forest)" />
      </svg>
      <span className="font-display text-[1.08rem] font-semibold tracking-tight">
        UL Navigator <span className="text-emerald">AI</span>
      </span>
    </span>
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

const NAV = [
  { href: "/chat", label: "Ask AI" },
  { href: "/courses", label: "Courses" },
  { href: "/explorer", label: "Knowledge" },
  { href: "/tools", label: "Student tools" },
  { href: "/knowledge-health", label: "Coverage" },
];

export function SiteHeader() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" aria-label="UL Navigator AI home">
          <Logo />
        </Link>
        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={cn(
                "rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:text-foreground",
                path === n.href && "text-foreground font-medium",
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button asChild size="sm" className="hidden sm:inline-flex">
            <Link href="/chat">Start chatting</Link>
          </Button>
          <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-border md:hidden"
            aria-label="Mobile"
          >
            <div className="flex flex-col p-3">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} className="rounded-lg px-3 py-3 text-sm hover:bg-surface-2">
                  {n.label}
                </Link>
              ))}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 text-sm text-muted sm:px-6 md:flex-row md:items-start md:justify-between">
        <div className="max-w-md space-y-2">
          <Logo />
          <p>{DISCLAIMER}</p>
          <p>Answers are generated from public UL web pages and documents. Always verify important information with the relevant UL office.</p>
        </div>
        <div className="space-y-1">
          <p className="font-medium text-foreground">Created by John Elifuraha Mziray</p>
          <p>BSc Artificial Intelligence &amp; Machine Learning, University of Limerick</p>
          <div className="flex flex-wrap gap-4 pt-2">
            <Link href="/courses" className="hover:text-foreground">Courses</Link>
            <Link href="/knowledge-health" className="hover:text-foreground">Coverage</Link>
            <Link href="/explorer" className="hover:text-foreground">Sources</Link>
            <Link href="/tools" className="hover:text-foreground">Tools</Link>
            <Link href="/grade-planner" className="hover:text-foreground">Grade planner</Link>
            <Link href="/curricula" className="hover:text-foreground">Programme modules</Link>
            <Link href="/about" className="hover:text-foreground">About</Link>
            <Link href="/privacy" className="hover:text-foreground">Privacy</Link>
            <Link href="/admin" className="hover:text-foreground">Admin</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
