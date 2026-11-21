"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import type { Citation } from "@/lib/api";

/** Renders an answer; [S1] markers become clickable citation chips. */
export function Markdown({
  content,
  citations,
  onCite,
}: {
  content: string;
  citations: Citation[];
  onCite: (c: Citation) => void;
}) {
  const byId = new Map(citations.map((c) => [c.id, c]));
  const linked = content.replace(/\[S(\d+)\]/g, "[S$1](#cite-S$1)");
  return (
    <div className="prose-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          a({ href, children }) {
            if (href?.startsWith("#cite-")) {
              const id = href.slice(6);
              const c = byId.get(id);
              return (
                <button
                  type="button"
                  onClick={() => c && onCite(c)}
                  disabled={!c}
                  title={c ? `${c.title}${c.section ? " — " + c.section : ""}` : "Source"}
                  aria-label={c ? `Source ${id}: ${c.title}` : `Source ${id}`}
                  className="mx-0.5 inline-flex h-[1.15rem] min-w-[1.4rem] -translate-y-0.5 items-center justify-center rounded-md bg-emerald-soft px-1 align-middle text-[10px] font-semibold text-forest no-underline transition hover:bg-emerald hover:text-white disabled:opacity-60 dark:text-emerald"
                >
                  {id.replace("S", "")}
                </button>
              );
            }
            const external = href?.startsWith("http");
            return (
              <a href={href} target={external ? "_blank" : undefined} rel={external ? "noopener noreferrer" : undefined}>
                {children}
              </a>
            );
          },
        }}
      >
        {linked}
      </ReactMarkdown>
    </div>
  );
}
