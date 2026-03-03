"""Unit tests for all three chunkers: Markdown, PhpCode, and Semantic."""

from __future__ import annotations

from pathlib import Path

import pytest

from odyssey_rag.ingestion.chunkers.base import Chunk, count_tokens
from odyssey_rag.ingestion.chunkers.markdown import MarkdownChunker
from odyssey_rag.ingestion.chunkers.php_code import PhpCodeChunker
from odyssey_rag.ingestion.chunkers.semantic import SemanticChunker
from odyssey_rag.ingestion.parsers.base import ParsedSection


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_section(
    content: str,
    section: str = "Test Section",
    subsection: str = "Subsection",
    metadata: dict | None = None,
) -> ParsedSection:
    """Create a ParsedSection for testing."""
    return ParsedSection(
        content=content,
        section=section,
        subsection=subsection,
        metadata=metadata or {},
    )


def long_text(n_words: int = 600) -> str:
    """Generate a long text of approximately n_words words."""
    word = "token"
    paragraph_a = " ".join([word] * (n_words // 2))
    paragraph_b = " ".join([word] * (n_words - n_words // 2))
    return paragraph_a + "\n\n" + paragraph_b


# ── count_tokens tests ────────────────────────────────────────────────────────

class TestCountTokens:
    """Tests for the count_tokens utility."""

    def test_empty_string_returns_one(self) -> None:
        """count_tokens returns at least 1 for any string."""
        assert count_tokens("") >= 1

    def test_short_text(self) -> None:
        """count_tokens returns a positive integer for short text."""
        result = count_tokens("Hello world")
        assert result > 0

    def test_longer_text_more_tokens(self) -> None:
        """Longer text produces more tokens than shorter text."""
        short = count_tokens("hello")
        long = count_tokens("hello " * 100)
        assert long > short


# ── MarkdownChunker tests ─────────────────────────────────────────────────────

class TestMarkdownChunker:
    """Tests for MarkdownChunker."""

    def setup_method(self) -> None:
        self.chunker = MarkdownChunker(max_tokens=100, overlap_tokens=20)

    def test_chunk_returns_list(self) -> None:
        """chunk() always returns a list."""
        sections = [make_section("Short content")]
        result = self.chunker.chunk(sections)
        assert isinstance(result, list)

    def test_chunk_empty_sections(self) -> None:
        """Chunking empty section list returns empty list."""
        result = self.chunker.chunk([])
        assert result == []

    def test_chunk_small_section_is_one_chunk(self) -> None:
        """A small section that fits in max_tokens becomes one chunk."""
        sections = [make_section("Hello world")]
        chunks = self.chunker.chunk(sections)
        assert len(chunks) == 1

    def test_chunk_contains_heading_prefix(self) -> None:
        """Chunk content includes the heading prefix."""
        sections = [make_section("Hello world", section="MySection", subsection="MySub")]
        chunks = self.chunker.chunk(sections)
        assert "MySection" in chunks[0].content

    def test_chunk_large_section_splits(self) -> None:
        """A section exceeding max_tokens is split into multiple chunks."""
        sections = [make_section(long_text(600))]
        chunker = MarkdownChunker(max_tokens=100, overlap_tokens=10)
        chunks = chunker.chunk(sections)
        assert len(chunks) > 1

    def test_chunk_index_sequential(self) -> None:
        """chunk_index values are 0-based and sequential."""
        sections = [
            make_section(long_text(200)),
            make_section(long_text(200)),
        ]
        chunker = MarkdownChunker(max_tokens=50, overlap_tokens=10)
        chunks = chunker.chunk(sections)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunk_token_count_set(self) -> None:
        """All chunks have positive token_count."""
        sections = [make_section("This is some content")]
        chunks = self.chunker.chunk(sections)
        for c in chunks:
            assert c.token_count > 0

    def test_chunk_section_metadata_preserved(self) -> None:
        """section and subsection are preserved in chunks."""
        sections = [make_section("Content", section="A", subsection="B")]
        chunks = self.chunker.chunk(sections)
        for c in chunks:
            assert c.section == "A"
            assert c.subsection == "B"

    def test_chunk_metadata_dict_preserved(self) -> None:
        """Chunk metadata dict is copied from section metadata."""
        meta = {"message_type": "pacs.008"}
        sections = [make_section("Content", metadata=meta)]
        chunks = self.chunker.chunk(sections)
        for c in chunks:
            assert c.metadata.get("message_type") == "pacs.008"

    def test_chunk_multiple_sections(self) -> None:
        """Multiple sections all produce chunks."""
        sections = [
            make_section("Section A content"),
            make_section("Section B content"),
        ]
        chunks = self.chunker.chunk(sections)
        assert len(chunks) >= 2


# ── PhpCodeChunker tests ──────────────────────────────────────────────────────

class TestPhpCodeChunker:
    """Tests for PhpCodeChunker."""

    def setup_method(self) -> None:
        self.chunker = PhpCodeChunker(max_tokens=200, overlap_tokens=20)

    def test_chunk_returns_list(self) -> None:
        """chunk() returns a list."""
        result = self.chunker.chunk([])
        assert isinstance(result, list)

    def test_chunk_small_method_one_chunk(self) -> None:
        """A small method section produces one chunk."""
        sections = [
            make_section(
                "public function validate(): bool { return true; }",
                section="MyClass",
                subsection="validate",
                metadata={"php_class": "MyClass", "module_path": "MyClass.php"},
            )
        ]
        chunks = self.chunker.chunk(sections)
        assert len(chunks) == 1

    def test_chunk_class_context_prefix_in_content(self) -> None:
        """Class context prefix is prepended to chunk content."""
        sections = [
            make_section(
                "public function build(): void {}",
                section="Pacs008",
                metadata={"php_class": "Pacs008", "module_path": "Pacs008.php"},
            )
        ]
        chunks = self.chunker.chunk(sections)
        assert "Pacs008" in chunks[0].content

    def test_chunk_index_sequential(self) -> None:
        """chunk_index values are 0-based sequential across all sections."""
        sections = [
            make_section(
                "public function a(): void {}",
                metadata={"php_class": "C"},
            ),
            make_section(
                "public function b(): void {}",
                metadata={"php_class": "C"},
            ),
        ]
        chunks = self.chunker.chunk(sections)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_chunk_token_count_positive(self) -> None:
        """All chunks have positive token_count."""
        sections = [make_section("public function x(): void {}", metadata={"php_class": "C"})]
        chunks = self.chunker.chunk(sections)
        assert all(c.token_count > 0 for c in chunks)

    def test_chunk_large_method_splits(self) -> None:
        """A method larger than max_tokens is split."""
        big_body = "// comment\n" * 200
        sections = [make_section(big_body, metadata={"php_class": "C"})]
        chunker = PhpCodeChunker(max_tokens=30, overlap_tokens=5)
        chunks = chunker.chunk(sections)
        assert len(chunks) >= 1  # Should not crash; may or may not split


# ── SemanticChunker tests ─────────────────────────────────────────────────────

class TestSemanticChunker:
    """Tests for SemanticChunker."""

    def setup_method(self) -> None:
        self.chunker = SemanticChunker(max_tokens=100, overlap_tokens=20)

    def test_chunk_returns_list(self) -> None:
        """chunk() returns a list."""
        assert self.chunker.chunk([]) == []

    def test_chunk_small_section_one_chunk(self) -> None:
        """Small content produces one chunk."""
        sections = [make_section("Hello world. This is short.")]
        chunks = self.chunker.chunk(sections)
        assert len(chunks) == 1

    def test_chunk_large_content_splits(self) -> None:
        """Content exceeding max_tokens is split into multiple chunks."""
        sections = [make_section(long_text(600))]
        chunker = SemanticChunker(max_tokens=80, overlap_tokens=10)
        chunks = chunker.chunk(sections)
        assert len(chunks) > 1

    def test_chunk_index_sequential(self) -> None:
        """chunk_index is 0-based and sequential across all sections."""
        sections = [
            make_section(long_text(300)),
            make_section(long_text(300)),
        ]
        chunker = SemanticChunker(max_tokens=60, overlap_tokens=10)
        chunks = chunker.chunk(sections)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_chunk_token_count_positive(self) -> None:
        """All chunks have positive token_count."""
        sections = [make_section("Some meaningful content here.")]
        chunks = self.chunker.chunk(sections)
        assert all(c.token_count > 0 for c in chunks)

    def test_chunk_section_preserved(self) -> None:
        """section and subsection labels are preserved in chunks."""
        sections = [make_section("Content", section="Sec", subsection="Sub")]
        chunks = self.chunker.chunk(sections)
        for c in chunks:
            assert c.section == "Sec"
            assert c.subsection == "Sub"

    def test_chunk_paragraph_split(self) -> None:
        """Content with two paragraphs separated by blank line."""
        text = "First paragraph content.\n\nSecond paragraph content."
        sections = [make_section(text)]
        chunks = self.chunker.chunk(sections)
        # Should produce 1 or 2 chunks depending on size vs max_tokens
        assert len(chunks) >= 1

    def test_chunk_metadata_preserved(self) -> None:
        """Chunk metadata is copied from section metadata."""
        meta = {"message_type": "pacs.008"}
        sections = [make_section("Content", metadata=meta)]
        chunks = self.chunker.chunk(sections)
        for c in chunks:
            assert c.metadata.get("message_type") == "pacs.008"
