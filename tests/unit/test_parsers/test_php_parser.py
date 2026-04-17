"""Unit tests for PhpCodeParser."""

from __future__ import annotations

from pathlib import Path


from odyssey_rag.ingestion.parsers.php_code import PhpCodeParser

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


class TestPhpCodeParser:
    """Tests for PhpCodeParser."""

    def setup_method(self) -> None:
        self.parser = PhpCodeParser()

    def test_supported_extensions(self) -> None:
        """supported_extensions returns .php."""
        exts = self.parser.supported_extensions()
        assert ".php" in exts

    def test_parse_sample_returns_sections(self) -> None:
        """Parsing sample PHP file returns multiple sections."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        assert len(sections) >= 2

    def test_parse_class_overview_section_exists(self) -> None:
        """A class_overview section is extracted."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        subsections = {s.subsection for s in sections}
        assert "class_overview" in subsections

    def test_parse_methods_extracted(self) -> None:
        """Public methods are extracted as individual sections."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        method_sections = [s for s in sections if s.subsection == "buildDocument"]
        assert len(method_sections) >= 1

    def test_parse_php_class_metadata(self) -> None:
        """php_class metadata is set on all sections."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        for s in sections:
            assert s.metadata.get("php_class") == "Pacs008CreditTransfer"

    def test_parse_module_path_metadata(self) -> None:
        """module_path metadata is set on all sections."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        for s in sections:
            assert "module_path" in s.metadata

    def test_parse_php_symbol_on_method_sections(self) -> None:
        """Method sections have php_symbol metadata."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        method_sections = [
            s for s in sections
            if s.subsection not in ("class_overview", "constants_properties")
            and s.subsection is not None
        ]
        for s in method_sections:
            assert "php_symbol" in s.metadata

    def test_parse_section_name_is_class_name(self) -> None:
        """Section field reflects the class name."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        for s in sections:
            assert s.section == "Pacs008CreditTransfer"

    def test_parse_content_not_empty(self) -> None:
        """All sections have non-empty content."""
        sections = self.parser.parse(str(FIXTURES / "sample_php.php"))
        for s in sections:
            assert s.content.strip() != ""

    def test_parse_fallback_on_empty_file(self, tmp_path: Path) -> None:
        """Parser handles an empty PHP file without crashing."""
        f = tmp_path / "empty.php"
        f.write_text("<?php\n")
        sections = self.parser.parse(str(f))
        assert isinstance(sections, list)
