"""Adaptive, structure-aware chunking of extracted Markdown.

* Splits on headings, keeping the heading path ("Fees > Payment > Instalments") as the
  chunk's section metadata and tracking PDF page markers.
* Packs paragraphs up to `size` words with `overlap` words carried over inside a section.
* Tables are kept intact when they fit; large tables are split by rows with the header
  row repeated in every piece.
* Very small sections are merged with the following section so we don't index fragments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .extractors import PAGE_MARK_RE

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*#*\s*$")


@dataclass
class Block:
    text: str
    section: str
    page: int | None
    is_table: bool = False

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass
class ChunkDraft:
    text: str
    section: str
    page: int | None

    @property
    def word_count(self) -> int:
        return len(self.text.split())


def parse_blocks(markdown: str) -> list[Block]:
    blocks: list[Block] = []
    stack: list[tuple[int, str]] = []
    page: int | None = None
    buf: list[str] = []
    in_table = False

    def section() -> str:
        return " > ".join(t for _, t in stack)[:480]

    def flush():
        nonlocal buf, in_table
        text = "\n".join(buf).strip()
        if text:
            blocks.append(Block(text, section(), page, in_table))
        buf, in_table = [], False

    for line in markdown.splitlines():
        pm = PAGE_MARK_RE.match(line.strip())
        if pm:
            flush()
            page = int(pm.group(1))
            continue
        hm = HEADING_RE.match(line)
        if hm:
            flush()
            level, title = len(hm.group(1)), hm.group(2).strip("*_ ")
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            continue
        is_table_line = line.lstrip().startswith("|")
        if is_table_line != in_table and buf:
            flush()
        in_table = is_table_line
        if not line.strip():
            if not in_table:
                flush()
            continue
        buf.append(line)
    flush()
    return blocks


def _split_table(block: Block, size: int) -> list[Block]:
    rows = block.text.splitlines()
    header = rows[:2] if len(rows) > 2 and set(rows[1].replace("|", "").strip()) <= set("-: ") else rows[:1]
    body = rows[len(header):]
    out, cur = [], []
    for r in body:
        cur.append(r)
        if len(" ".join(header + cur).split()) >= size:
            out.append(Block("\n".join(header + cur), block.section, block.page, True))
            cur = []
    if cur:
        out.append(Block("\n".join(header + cur), block.section, block.page, True))
    return out


def _split_long_text(block: Block, size: int) -> list[Block]:
    sents = re.split(r"(?<=[.!?])\s+", block.text)
    out, cur = [], []
    for s in sents:
        if cur and len(" ".join(cur + [s]).split()) > size:
            out.append(Block(" ".join(cur), block.section, block.page))
            cur = []
        cur.append(s)
    if cur:
        out.append(Block(" ".join(cur), block.section, block.page))
    # hard split for pathological text without sentence boundaries
    final = []
    for b in out:
        words = b.text.split()
        for i in range(0, len(words), size):
            final.append(Block(" ".join(words[i:i + size]), b.section, b.page))
    return final


def chunk_markdown(markdown: str, size: int = 260, overlap: int = 50,
                   min_words: int = 40, preserve_sections: bool = False) -> list[ChunkDraft]:
    blocks: list[Block] = []
    for b in parse_blocks(markdown):
        if b.words <= size:
            blocks.append(b)
        elif b.is_table:
            blocks.extend(_split_table(b, size))
        else:
            blocks.extend(_split_long_text(b, size))

    chunks: list[ChunkDraft] = []
    cur: list[Block] = []

    def emit():
        if not cur:
            return
        text = "\n\n".join(b.text for b in cur).strip()
        chunks.append(ChunkDraft(text, cur[0].section, cur[0].page))

    for b in blocks:
        if cur:
            same_section = b.section == cur[0].section
            cur_words = sum(x.words for x in cur)
            too_big = cur_words + b.words > size
            # adaptive: tiny sections are merged forward instead of emitted alone
            if too_big or (not same_section and (preserve_sections or cur_words >= min_words)):
                emit()
                carry: list[Block] = []
                if same_section and overlap > 0 and not b.is_table and not cur[-1].is_table:
                    tail = cur[-1].text.split()[-overlap:]
                    if len(tail) < cur[-1].words:
                        carry = [Block(" ".join(tail), cur[-1].section, cur[-1].page)]
                cur = carry
        cur.append(b)
    emit()

    # merge a trailing fragment into its predecessor
    if not preserve_sections and len(chunks) >= 2 and chunks[-1].word_count < min_words // 2:
        last = chunks.pop()
        chunks[-1].text += "\n\n" + last.text
    return [c for c in chunks if c.word_count >= (1 if preserve_sections else 5)]
