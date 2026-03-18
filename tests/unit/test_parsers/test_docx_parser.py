"""Unit tests for DocxParser."""

from __future__ import annotations

from pathlib import Path

import pytest

from odyssey_rag.ingestion.parsers.docx import DocxParser

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"
SAMPLE_DOCX = FIXTURES / "sample_document.docx"


@pytest.fixture(autouse=True)
def _require_fixture() -> None:
    if not SAMPLE_DOCX.exists():
        pytest.skip("sample_document.docx fixture not found")


class TestDocxParser:
    """Tests for DocxParser."""

    def setup_method(self) -> None:
        self.parser = DocxParser()

    def test_supported_extensions(self) -> None:
        exts = self.parser.supported_extensions()
        assert ".doc" in exts
        assert ".docx" in exts

    def test_parse_returns_sections(self) -> None:
        """Parsing a .docx returns multiple sections."""
        sections = self.parser.parse(str(SAMPLE_DOCX))
        assert len(sections) >= 3

    def test_parse_extracts_heading_as_section(self) -> None:
        """Heading 1 becomes the section name."""
        sections = self.parser.parse(str(SAMPLE_DOCX))
        section_names = {s.section for s in sections if s.section}
        assert "Sample Document Title" in section_names

    def test_parse_extracts_subsection(self) -> None:
        """Heading 2/3 become subsection names."""
        sections = self.parser.parse(str(SAMPLE_DOCX))
        subsection_names = {s.subsection for s in sections if s.subsection}
        assert len(subsection_names) > 0

    def test_parse_extracts_paragraph_content(self) -> None:
        """Paragraph text appears in section content."""
        sections = self.parser.parse(str(SAMPLE_DOCX))
        all_content = " ".join(s.content for s in sections)
        assert "introduction paragraph" in all_content

    def test_parse_extracts_tables(self) -> None:
        """Table content is extracted into sections."""
        sections = self.parser.parse(str(SAMPLE_DOCX))
        table_sections = [s for s in sections if s.subsection == "Table"]
        assert len(table_sections) >= 1
        table_text = table_sections[0].content
        assert "MsgId" in table_text

    def test_parse_empty_file(self, tmp_path: Path) -> None:
        """Parsing an empty .docx returns an empty list."""
        import docx

        empty = tmp_path / "empty.docx"
        docx.Document().save(str(empty))
        sections = self.parser.parse(str(empty))
        assert sections == []


class TestDocxParserLegacyDoc:
    """Tests for legacy .doc handling."""

    def setup_method(self) -> None:
        self.parser = DocxParser()

    def test_doc_raw_fallback(self, tmp_path: Path) -> None:
        """For a .doc file without antiword, raw text extraction is attempted."""
        # Create a fake .doc with some readable text embedded
        doc_file = tmp_path / "test.doc"
        doc_file.write_bytes(b"\x00" * 100 + b"This is readable text in a doc file" + b"\x00" * 50)
        sections = self.parser.parse(str(doc_file))
        # May or may not extract text depending on the raw content
        # At minimum it should not crash
        assert isinstance(sections, list)
