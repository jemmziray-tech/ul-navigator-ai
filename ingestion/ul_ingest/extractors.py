"""Content extraction to structure-preserving Markdown.

HTML  -> main content only (nav/header/footer/cookie banners removed), headings, lists and
         tables preserved.
PDF   -> PyMuPDF; headings inferred from font size/weight, tables via find_tables(),
         `<!-- page: N -->` markers so every chunk keeps its page number.
CSV   -> one Markdown section per row (works for Book of Modules exports).
RTF / TXT / MD -> plain text.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import statistics
from collections import Counter
from urllib.parse import urlparse
from dataclasses import dataclass

from bs4 import BeautifulSoup
from markdownify import markdownify

log = logging.getLogger("ul_ingest.extract")

PAGE_MARK = "<!-- page: {n} -->"
PAGE_MARK_RE = re.compile(r"<!-- page: (\d+) -->")

REMOVE_SELECTORS = [
    "script", "style", "noscript", "iframe", "svg", "form", "header", "footer", "nav", "aside",
    "button", "[role=navigation]", "[role=banner]", "[role=contentinfo]", "[aria-hidden=true]",
    ".breadcrumb", ".breadcrumbs", ".cookie", "#cookie", ".cookies", ".eu-cookie-compliance",
    ".skip-link", ".visually-hidden", ".sr-only", ".social", ".share", ".pager", ".menu",
    ".sidebar", ".site-header", ".site-footer", ".region-header", ".region-footer",
    "#block-ul-main-menu", ".back-to-top",
]
MAIN_SELECTORS = ["main", "[role=main]", "article", "#main-content", "#content",
                  ".region-content", ".main-content", ".layout-content"]


@dataclass
class Extracted:
    title: str
    markdown: str
    page_count: int | None = None


def _clean_markdown(md: str) -> str:
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)            # images
    md = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^)]*\))*\)", r"\1", md)  # keep link text only
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    lines = [ln.rstrip() for ln in md.splitlines()]
    return "\n".join(lines).strip()


def extract_html(html: bytes | str, url: str = "") -> Extracted:
    soup = BeautifulSoup(html, "lxml")
    parsed = urlparse(url)
    if parsed.hostname in {"www.bookofmodules.ul.ie", "bookofmodules.ul.ie"}:
        # ASP.NET puts official module content inside its search/export form.
        # Select only the displayed details before generic form removal.
        details = soup.select_one("[id$='ModuleFull_ListViewUpdatePanel']")
        if details and details.select_one(".ModuleLayoutStyle"):
            root = BeautifulSoup(str(details), "lxml")
            heading = root.select_one(".ModuleLayoutStyle")
            label = re.sub(r"\s+", " ", heading.get_text(" ", strip=True))
            title = re.sub(r"^Module Code\s*-\s*Title:\s*", "", label).strip()
            for control in root.select("script, style, input, button, .DataPagerStyle"):
                control.decompose()
            md = markdownify(str(root), heading_style="ATX", bullets="-", strip=["a", "img"])
            return Extracted(title=title, markdown=_clean_markdown(md))
    title = ""
    if soup.title and soup.title.string:
        title = re.split(r"\s+[|\-–]\s+", soup.title.string.strip())[0]
    for sel in REMOVE_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    root = None
    for sel in MAIN_SELECTORS:
        root = soup.select_one(sel)
        if root and len(root.get_text(strip=True)) >= 20:
            break
        root = None
    root = root or soup.body or soup
    h1 = root.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(" ", strip=True)
    # A labelled contact link may hide the actual address. Retain public addresses.
    for anchor in root.select('a[href^="mailto:"]'):
        address = anchor.get("href", "")[7:].split("?", 1)[0]
        if address and address.lower() not in anchor.get_text().lower():
            anchor.append(" (" + address + ")")
    md = markdownify(str(root), heading_style="ATX", bullets="-", strip=["a", "img"])
    return Extracted(title=title or url, markdown=_clean_markdown(md))


def _table_md(table) -> str:
    try:
        return table.to_markdown(clean=True).strip()
    except Exception:  # pragma: no cover
        rows = table.extract()
        return "\n".join(" | ".join(c or "" for c in r) for r in rows)


def extract_pdf(data: bytes, extract_tables: bool = False, max_table_pages: int = 400) -> Extracted:
    """Text extraction with headings + page markers. Table detection (find_tables) is off by
    default: it is slow and can crash natively on some PDFs; table cells are still captured
    as text lines."""
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    sizes: list[float] = []
    for page in doc.pages(0, min(doc.page_count, 30)):
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for sp in line["spans"]:
                    if sp["text"].strip():
                        sizes.append(round(sp["size"], 1))
    body = statistics.mode(sizes) if sizes else 10.0
    title = (doc.metadata or {}).get("title") or ""
    out: list[str] = []
    for pno, page in enumerate(doc, start=1):
        out.append(PAGE_MARK.format(n=pno))
        table_rects = []
        if extract_tables and pno <= max_table_pages:
            try:
                for t in page.find_tables().tables:
                    if t.row_count >= 2 and t.col_count >= 2:
                        table_rects.append(pymupdf.Rect(t.bbox))
                        out.append(_table_md(t))
            except Exception as exc:  # pragma: no cover - malformed pages
                log.debug("table extraction failed p%s: %s", pno, exc)
        for b in page.get_text("dict")["blocks"]:
            if b.get("type") != 0:
                continue
            if any(pymupdf.Rect(b["bbox"]).intersects(r) for r in table_rects):
                continue
            for line in b.get("lines", []):
                text = "".join(sp["text"] for sp in line["spans"]).strip()
                if not text:
                    continue
                size = max(sp["size"] for sp in line["spans"])
                bold = all(sp["flags"] & 16 for sp in line["spans"] if sp["text"].strip())
                if len(text) < 120 and not text.endswith((".", ",", ";")):
                    if size >= body * 1.45:
                        out.append(f"\n# {text}\n")
                        continue
                    if size >= body * 1.18 or (bold and size >= body and len(text) < 80):
                        out.append(f"\n## {text}\n")
                        continue
                out.append(text)
            out.append("")
        if not title and pno == 1:
            first = [ln for ln in out if ln.startswith("#")]
            title = first[0].lstrip("# ").strip() if first else ""
    pages = doc.page_count
    doc.close()
    md = "\n".join(out)
    md = re.sub(r"(?<![.:!?|])\n(?=[a-z])", " ", md)  # re-join wrapped lines
    return Extracted(title=title, markdown=_clean_markdown(md), page_count=pages)


def extract_csv(data: bytes, title: str = "") -> Extracted:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    fields = [f for f in reader.fieldnames if f]
    code_col = next((f for f in fields if re.search(r"code", f, re.I)), None)
    name_col = next((f for f in fields if re.search(r"title|name", f, re.I)), None)
    parts = []
    for i, row in enumerate(reader, start=1):
        head = " ".join(x for x in [(row.get(code_col) or "").strip() if code_col else "",
                                    (row.get(name_col) or "").strip() if name_col else ""] if x)
        parts.append(f"## {head or f'Row {i}'}")
        for f in fields:
            val = (row.get(f) or "").strip()
            if val:
                parts.append(f"- **{f}:** {val}")
        parts.append("")
    return Extracted(title=title, markdown="\n".join(parts).strip())


def extract_rtf(data: bytes, title: str = "") -> Extracted:
    from striprtf.striprtf import rtf_to_text
    return Extracted(title=title, markdown=_clean_markdown(
        rtf_to_text(data.decode("utf-8", errors="replace"))))


def extract_text(data: bytes, title: str = "") -> Extracted:
    return Extracted(title=title, markdown=_clean_markdown(data.decode("utf-8", errors="replace")))


def _pdf_worker(data: bytes, conn) -> None:  # runs in a child process
    try:
        ex = extract_pdf(data)
        conn.send(("ok", ex.title, ex.markdown, ex.page_count))
    except Exception as exc:  # noqa: BLE001
        conn.send(("error", f"{type(exc).__name__}: {exc}", None, None))
    finally:
        conn.close()


def extract_pdf_isolated(data: bytes, timeout_s: float = 300.0) -> Extracted:
    """Parse a PDF in a separate process so a native MuPDF crash or hang only fails this
    one document instead of killing the whole ingestion run."""
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_pdf_worker, args=(data, child), daemon=True)
    proc.start()
    child.close()
    result = None
    if parent.poll(timeout_s):
        try:
            result = parent.recv()
        except EOFError:
            result = None
    proc.join(5)
    if proc.is_alive():
        proc.kill()
        raise RuntimeError(f"PDF extraction timed out after {timeout_s:.0f}s")
    if result is None:
        raise RuntimeError(f"PDF extraction crashed (exit code {proc.exitcode})")
    status, a, b, c = result
    if status != "ok":
        raise RuntimeError(a)
    return Extracted(title=a, markdown=b, page_count=c)


def extract(kind: str, data: bytes, url: str = "", title: str = "") -> Extracted:
    if kind == "html":
        return extract_html(data, url)
    if kind == "pdf":
        ex = extract_pdf_isolated(data)
        ex.title = title or ex.title
        return ex
    if kind == "csv":
        return extract_csv(data, title)
    if kind == "rtf":
        return extract_rtf(data, title)
    if kind in ("txt", "md"):
        return extract_text(data, title)
    raise ValueError(f"unsupported content type: {kind}")


# ------------------------------------------------------------------ boilerplate
def find_boilerplate_lines(docs: list[str], min_docs: int = 4, ratio: float = 0.3) -> set[str]:
    """Lines repeated across many pages of the site (menus, footers, banners)."""
    if len(docs) < min_docs:
        return set()
    df: Counter[str] = Counter()
    for md in docs:
        df.update({ln.strip() for ln in md.splitlines()
                   if ln.strip() and not ln.startswith("<!--") and len(ln.strip()) < 300})
    threshold = max(min_docs, int(len(docs) * ratio))
    return {ln for ln, n in df.items() if n >= threshold}


def remove_boilerplate(md: str, boilerplate: set[str]) -> str:
    if not boilerplate:
        return md
    kept = [ln for ln in md.splitlines() if ln.strip() not in boilerplate]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
