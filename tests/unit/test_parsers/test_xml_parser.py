"""Unit tests for XmlExampleParser."""

from __future__ import annotations

from pathlib import Path


from odyssey_rag.ingestion.parsers.xml_example import XmlExampleParser

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


class TestXmlExampleParser:
    """Tests for XmlExampleParser."""

    def setup_method(self) -> None:
        self.parser = XmlExampleParser()

    def test_supported_extensions(self) -> None:
        """supported_extensions returns .xml."""
        exts = self.parser.supported_extensions()
        assert ".xml" in exts

    def test_parse_pacs008_returns_sections(self) -> None:
        """Parsing the pacs.008 fixture returns at least 2 sections."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        assert len(sections) >= 2

    def test_parse_pacs008_message_type_metadata(self) -> None:
        """message_type metadata is pacs.008 for the fixture."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        types = {s.metadata.get("message_type") for s in sections if s.metadata.get("message_type")}
        assert "pacs.008" in types

    def test_parse_pacs008_iso_version_metadata(self) -> None:
        """iso_version metadata is extracted from MsgDefIdr."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        versions = {s.metadata.get("iso_version") for s in sections if s.metadata.get("iso_version")}
        assert len(versions) > 0

    def test_parse_pacs008_from_bic(self) -> None:
        """from_bic metadata is extracted from AppHdr."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        bics = {s.metadata.get("from_bic") for s in sections if s.metadata.get("from_bic")}
        assert "BIMPAYBB" in bics

    def test_parse_full_xml_section_exists(self) -> None:
        """A full_xml subsection is always present."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        subsections = {s.subsection for s in sections}
        assert "full_xml" in subsections

    def test_parse_full_xml_content(self) -> None:
        """The full_xml section contains the raw XML text."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        full_xml_sections = [s for s in sections if s.subsection == "full_xml"]
        assert len(full_xml_sections) == 1
        assert "FIToFICstmrCdtTrf" in full_xml_sections[0].content

    def test_parse_corrupt_xml_returns_error_section(self, tmp_path: Path) -> None:
        """Corrupt XML returns a single parse_error section instead of raising."""
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("<unclosed>")
        sections = self.parser.parse(str(bad_xml))
        assert len(sections) == 1
        assert sections[0].section == "xml_parse_error"

    def test_parse_source_file_metadata(self) -> None:
        """source_file metadata is set on all sections."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        for s in sections:
            assert "source_file" in s.metadata

    def test_parse_content_not_empty(self) -> None:
        """All sections have non-empty content."""
        sections = self.parser.parse(str(FIXTURES / "sample_pacs008.xml"))
        for s in sections:
            assert s.content.strip() != ""
