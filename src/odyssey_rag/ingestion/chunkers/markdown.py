"""Markdown-aware chunker.

Splits ParsedSection objects produced by MarkdownParser into chunks
that respect heading context, table rows, and overlap boundaries.
"""

from __future__ import annotations

from odyssey_rag.ingestion.chunkers.base import BaseChunker, Chunk, count_tokens
from odyssey_rag.ingestion.parsers.base import ParsedSection

# Markdown table row pattern: lines starting with | are table rows
_TABLE_ROW_MARKER = "|"


def _build_heading_prefix(section: ParsedSection) -> str:
    """Build a readable heading prefix from section/subsection labels."""
    parts = []
    if section.section:
        parts.append(f"## {section.section}")
    if section.subsection:
        parts.append(f"### {section.subsection}")
    if parts:
        return "\n".join(parts) + "\n\n"
    return ""


def _split_preserving_tables(text: str) -> list[str]:
    """Split text at paragraph boundaries while never breaking table rows.

    Table rows (lines starting with ``|``) are kept together with adjacent
    rows so that a complete table block is never split across chunks.

    Returns a list of paragraph blocks.
    """
    lines = text.splitlines()
    blocks: list[str] = []
    current_lines: list[str] = []

    for line in lines:
        if line.strip() == "":
            if current_lines:
                blocks.append("\n".join(current_lines))
                current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append("\n".join(current_lines))

    return [b for b in blocks if b.strip()]


class MarkdownChunker(BaseChunker):
    """Heading-aware chunker for Markdown content.

    Chunking strategy:
    1. If the entire section fits within ``max_tokens`` → one chunk.
    2. Otherwise → split at paragraph boundaries, accumulating paragraphs
       until the token budget is reached, then start a new chunk.
    3. Never split a table row in the middle — table blocks are atomic.
    4. Every chunk is prefixed with its heading context so that the
       embedded text is self-contained.
    5. An ``overlap_tokens``-worth of text from the previous chunk is
       prepended to each subsequent chunk.
    """

    def chunk(self, sections: list[ParsedSection]) -> list[Chunk]:
        """Split Markdown sections into token-bounded chunks.

        Args:
            sections: Ordered list of ParsedSection objects from MarkdownParser.

        Returns:
            Ordered list of Chunk objects with sequential ``chunk_index`` values.
        """
        chunks: list[Chunk] = []
        idx = 0

        for section in sections:
            prefix = _build_heading_prefix(section)
            content = section.content

            # Fast path: fits in one chunk
            full_text = prefix + content
            if count_tokens(full_text) <= self.max_tokens:
                chunks.append(
                    Chunk(
                        content=full_text,
                        token_count=count_tokens(full_text),
                        section=section.section,
                        subsection=section.subsection,
                        chunk_index=idx,
                        metadata=dict(section.metadata),
                    )
                )
                idx += 1
                continue

            # Slow path: split by paragraph
            paragraphs = _split_preserving_tables(content)
            current_parts: list[str] = []
            current_tokens = count_tokens(prefix)
            overlap_tail: str = ""

            for para in paragraphs:
                para_tokens = count_tokens(para)

                if current_tokens + para_tokens + 1 > self.max_tokens and current_parts:
                    # Flush current chunk
                    chunk_text = prefix + overlap_tail + "\n\n".join(current_parts)
                    chunks.append(
                        Chunk(
                            content=chunk_text,
                            token_count=count_tokens(chunk_text),
                            section=section.section,
                            subsection=section.subsection,
                            chunk_index=idx,
                            metadata=dict(section.metadata),
                        )
                    )
                    idx += 1

                    # Compute overlap tail from end of previous chunk
                    all_text = "\n\n".join(current_parts)
                    overlap_tail = self._tail_by_tokens(all_text, self.overlap_tokens)
                    current_parts = []
                    current_tokens = count_tokens(prefix) + count_tokens(overlap_tail)

                current_parts.append(para)
                current_tokens += para_tokens + 1  # +1 for separator

            # Flush remaining parts
            if current_parts:
                chunk_text = prefix + overlap_tail + "\n\n".join(current_parts)
                chunks.append(
                    Chunk(
                        content=chunk_text,
                        token_count=count_tokens(chunk_text),
                        section=section.section,
                        subsection=section.subsection,
                        chunk_index=idx,
                        metadata=dict(section.metadata),
                    )
                )
                idx += 1

        return chunks

    def _tail_by_tokens(self, text: str, max_overlap: int) -> str:
        """Return the last ``max_overlap`` tokens of *text* as a string."""
        words = text.split()
        # Approximate: 1 token ≈ 0.75 words; take slightly more to be safe
        word_count = max(1, int(max_overlap * 0.75))
        tail_words = words[-word_count:]
        tail = " ".join(tail_words)
        if tail:
            return tail + "\n\n"
        return ""
