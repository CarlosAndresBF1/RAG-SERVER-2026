"""Unit tests for MarkdownParser."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from odyssey_rag.ingestion.parsers.markdown import MarkdownParser

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


class TestMarkdownParser:
    """Tests for MarkdownParser."""

    def setup_method(self) -> None:
        self.parser = MarkdownParser()

    def test_supported_extensions(self) -> None:
        """supported_extensions returns .md, .txt, .rst."""
        exts = self.parser.supported_extensions()
        assert ".md" in exts
        assert ".txt" in exts
        assert ".rst" in exts

    def test_parse_annex_b_returns_sections(self) -> None:
        """Parsing the Annex B fixture returns multiple sections."""
        sections = self.parser.parse(str(FIXTURES / "sample_annex_b.md"))
        assert len(sections) >= 3

    def test_parse_annex_b_section_names(self) -> None:
        """Section names are non-empty strings derived from headings."""
        sections = self.parser.parse(str(FIXTURES / "sample_annex_b.md"))
        section_names = {s.section for s in sections if s.section}
        # H2 bodies become sections with H1 as section name; subsections come from H3
        assert len(section_names) > 0
        assert all(isinstance(name, str) and len(name) > 0 for name in section_names)

    def test_parse_annex_b_message_type_metadata(self) -> None:
        """Parser extracts message_type metadata from section body content."""
        sections = self.parser.parse(str(FIXTURES / "sample_annex_b.md"))
        # Sections whose body text mentions "pacs.008" explicitly
        types_found = {s.metadata.get("message_type") for s in sections if s.metadata.get("message_type")}
        assert "pacs.008" in types_found

    def test_parse_annex_b_iso_version_metadata(self) -> None:
        """Parser extracts iso_version metadata when body mentions full version string."""
        sections = self.parser.parse(str(FIXTURES / "sample_annex_b.md"))
        versions = {s.metadata.get("iso_version") for s in sections if s.metadata.get("iso_version")}
        assert len(versions) > 0

    def test_parse_annex_b_fields_metadata(self) -> None:
        """Parser extracts fields_in_section from Annex B table rows."""
        sections = self.parser.parse(str(FIXTURES / "sample_annex_b.md"))
        sections_with_fields = [
            s for s in sections if s.metadata.get("fields_in_section")
        ]
        assert len(sections_with_fields) > 0

    def test_parse_generic_md_returns_sections(self) -> None:
        """Parsing a generic Markdown file returns non-empty section list."""
        sections = self.parser.parse(str(FIXTURES / "sample_generic.md"))
        assert len(sections) >= 2

    def test_parse_generic_md_subsections(self) -> None:
        """H2 headings become section names for generic Markdown."""
        sections = self.parser.parse(str(FIXTURES / "sample_generic.md"))
        section_names = {s.section for s in sections if s.section}
        assert any(name for name in section_names if name)

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        """Parsing an empty file returns empty list."""
        empty = tmp_path / "empty.md"
        empty.write_text("")
        sections = self.parser.parse(str(empty))
        assert sections == []

    def test_parse_no_headings(self, tmp_path: Path) -> None:
        """A file with no headings is returned as a single section."""
        md = tmp_path / "flat.md"
        md.write_text("This is just plain text without any headings.\n\nSecond paragraph.")
        sections = self.parser.parse(str(md))
        assert len(sections) == 1
        assert "plain text" in sections[0].content

    def test_section_content_not_empty(self) -> None:
        """All returned sections have non-empty content."""
        sections = self.parser.parse(str(FIXTURES / "sample_annex_b.md"))
        for s in sections:
            assert s.content.strip() != ""

    def test_metadata_is_dict(self) -> None:
        """Section metadata is always a dictionary."""
        sections = self.parser.parse(str(FIXTURES / "sample_annex_b.md"))
        for s in sections:
            assert isinstance(s.metadata, dict)
