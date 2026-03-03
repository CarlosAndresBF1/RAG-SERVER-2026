"""Semantic (paragraph-aware) chunker.

Fallback chunker for generic text, PDFs, and any source type without a
dedicated chunker. Splits at paragraph boundaries with token-aware
accumulation and configurable overlap.
"""

from __future__ import annotations

import re

from odyssey_rag.ingestion.chunkers.base import BaseChunker, Chunk, count_tokens
from odyssey_rag.ingestion.parsers.base import ParsedSection

# Sentence boundary pattern (used only when a single paragraph exceeds max_tokens)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text at double-newline paragraph boundaries."""
    paragraphs = re.split(r"\n{2,}", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_into_sentences(text: str) -> list[str]:
    """Split a long paragraph into individual sentences."""
    parts = _SENTENCE_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


class SemanticChunker(BaseChunker):
    """Token-aware paragraph-splitting chunker.

    Chunking strategy:
    1. Split each ParsedSection at ``\\n\\n`` paragraph boundaries.
    2. Accumulate paragraphs into a chunk until ``max_tokens`` would be exceeded.
    3. If a single paragraph exceeds ``max_tokens``, split it at sentence
       boundaries; if a sentence still exceeds the limit, hard-split by token
       count.
    4. Carry ``overlap_tokens`` from the end of the previous chunk into the
       next one.
    5. Preserve ``section`` and ``subsection`` from the source ParsedSection.
    """

    def chunk(self, sections: list[ParsedSection]) -> list[Chunk]:
        """Split generic sections into token-bounded chunks.

        Args:
            sections: Ordered list of ParsedSection objects.

        Returns:
            Ordered list of Chunk objects with sequential ``chunk_index`` values.
        """
        chunks: list[Chunk] = []
        idx = 0

        for section in sections:
            new_chunks = self._chunk_section(section)
            for c in new_chunks:
                c.chunk_index = idx
                idx += 1
            chunks.extend(new_chunks)

        return chunks

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _chunk_section(self, section: ParsedSection) -> list[Chunk]:
        """Chunk a single ParsedSection into token-bounded pieces."""
        paragraphs = _split_into_paragraphs(section.content)
        if not paragraphs:
            return []

        # Expand paragraphs that exceed max_tokens into sentence-level pieces
        units: list[str] = []
        for para in paragraphs:
            if count_tokens(para) <= self.max_tokens:
                units.append(para)
            else:
                sentences = _split_into_sentences(para)
                for sent in sentences:
                    if count_tokens(sent) <= self.max_tokens:
                        units.append(sent)
                    else:
                        # Hard split by approximate word count
                        units.extend(self._hard_split(sent))

        return self._accumulate(units, section)

    def _hard_split(self, text: str) -> list[str]:
        """Split text that exceeds max_tokens by words."""
        words = text.split()
        # Approximate: max_tokens * 0.75 words per chunk
        words_per_chunk = max(1, int(self.max_tokens * 0.75))
        result = []
        for i in range(0, len(words), words_per_chunk):
            result.append(" ".join(words[i : i + words_per_chunk]))
        return result

    def _accumulate(
        self, units: list[str], section: ParsedSection
    ) -> list[Chunk]:
        """Accumulate text units into chunks with overlap."""
        chunks: list[Chunk] = []
        current: list[str] = []
        current_tokens = 0
        overlap_tail = ""

        for unit in units:
            unit_tokens = count_tokens(unit)

            if current_tokens + unit_tokens > self.max_tokens and current:
                # Flush
                chunk_text = (overlap_tail + "\n\n".join(current)).strip()
                chunks.append(
                    Chunk(
                        content=chunk_text,
                        token_count=count_tokens(chunk_text),
                        section=section.section,
                        subsection=section.subsection,
                        chunk_index=0,  # assigned by caller
                        metadata=dict(section.metadata),
                    )
                )
                overlap_tail = self._compute_overlap("\n\n".join(current))
                current = []
                current_tokens = count_tokens(overlap_tail)

            current.append(unit)
            current_tokens += unit_tokens

        # Flush remaining
        if current:
            chunk_text = (overlap_tail + "\n\n".join(current)).strip()
            chunks.append(
                Chunk(
                    content=chunk_text,
                    token_count=count_tokens(chunk_text),
                    section=section.section,
                    subsection=section.subsection,
                    chunk_index=0,
                    metadata=dict(section.metadata),
                )
            )

        return chunks

    def _compute_overlap(self, text: str) -> str:
        """Return the last ``overlap_tokens`` worth of text for overlap."""
        words = text.split()
        word_count = max(1, int(self.overlap_tokens * 0.75))
        tail = " ".join(words[-word_count:])
        return tail + "\n\n" if tail else ""
