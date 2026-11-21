"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { CalendarClock, ExternalLink, FileText, Globe } from "lucide-react";
import { api, fmtDate, label, type Citation } from "@/lib/api";
import { Badge, Button, Dialog, DialogContent, Skeleton } from "@/components/ui";

function hostOf(url: string) {
  try {
    return url.startsWith("upload://") ? "Uploaded document" : new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function CitationCard({ c, onOpen, index }: { c: Citation; onOpen: (c: Citation) => void; index: number }) {
  const isPdf = c.content_type === "pdf";
  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      onClick={() => onOpen(c)}
      className="group flex w-full flex-col gap-1.5 rounded-xl border border-border bg-surface p-3 text-left transition hover:border-emerald/60 hover:shadow-sm"
      aria-label={`Open source ${c.id}: ${c.title}`}
    >
      <div className="flex items-center gap-2 text-[11px] text-muted">
        <span className="grid h-5 min-w-5 place-items-center rounded-md bg-forest px-1 text-[10px] font-semibold text-white">{c.id.replace("S", "")}</span>
        {isPdf ? <FileText className="h-3.5 w-3.5" /> : <Globe className="h-3.5 w-3.5" />}
        <span className="truncate">{hostOf(c.url)}</span>
        {c.page ? <span>· p.{c.page}</span> : null}
      </div>
      <p className="line-clamp-2 text-sm font-medium leading-snug group-hover:text-forest dark:group-hover:text-emerald">{c.title}</p>
      {c.section ? <p className="line-clamp-1 text-xs text-muted">{c.section}</p> : null}
      <div className="mt-0.5 flex flex-wrap gap-1">
        {c.academic_year ? <Badge tone="green">{c.academic_year}</Badge> : null}
        <Badge>{label(c.category)}</Badge>
      </div>
    </motion.button>
  );
}

export function SourcePreview({ c, onClose }: { c: Citation | null; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (!c) return;
    setText(null);
    setErr(false);
    api<{ text: string }>(`/api/chunks/${c.chunk_id}`).then((r) => setText(r.text)).catch(() => setErr(true));
  }, [c]);
  return (
    <Dialog open={!!c} onOpenChange={(o) => !o && onClose()}>
      {c ? (
        <DialogContent title={c.title} description={[c.section, c.page ? `Page ${c.page}` : null].filter(Boolean).join(" · ") || undefined}>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-muted">
            {c.academic_year ? <Badge tone="green">Academic year {c.academic_year}</Badge> : null}
            <Badge>{label(c.category)}</Badge>
            <span className="inline-flex items-center gap-1"><CalendarClock className="h-3.5 w-3.5" /> Retrieved {fmtDate(c.retrieved_at)}</span>
          </div>
          <div className="rounded-xl border border-border bg-surface-2 p-4 text-sm leading-relaxed">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted">Supporting passage</p>
            {err ? (
              <p className="whitespace-pre-wrap">{c.excerpt}</p>
            ) : text === null ? (
              <div className="space-y-2"><Skeleton className="h-4" /><Skeleton className="h-4 w-5/6" /><Skeleton className="h-4 w-4/6" /></div>
            ) : (
              <p className="max-h-80 overflow-y-auto whitespace-pre-wrap scrollbar-thin">{text}</p>
            )}
          </div>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted">Always check the original page — it may have been updated since it was retrieved.</p>
            {c.url.startsWith("http") ? (
              <Button asChild size="sm">
                <a href={c.url} target="_blank" rel="noopener noreferrer">
                  Open official source <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </Button>
            ) : null}
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}
