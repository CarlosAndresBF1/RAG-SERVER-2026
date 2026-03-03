"""Abstract parser interface and ParsedSection data transfer object.

All document parsers implement BaseParser and return lists of ParsedSection
objects which carry the raw text plus structural hints for downstream
chunking and metadata extraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedSection:
    """A logical section extracted from a source file.

    Attributes:
        content:    The raw text content of the section.
        section:    Top-level heading (H1 / H2) — e.g. "pacs.008.001.12".
        subsection: Sub-heading (H3) — e.g. "Group Header (GrpHdr)".
        metadata:   Parser-provided hints used by the MetadataExtractor.
                    Keys include: ``message_type``, ``iso_version``,
                    ``php_class``, ``php_symbol``, ``module_path``.
    """

    content: str
    section: Optional[str] = None
    subsection: Optional[str] = None
    metadata: dict[str, str] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract base class for all document parsers.

    Concrete subclasses handle specific source types:
    - MarkdownParser   (annex_b_spec, tech_doc, claude_context, generic_text)
    - PhpCodeParser    (php_code)
    - XmlExampleParser (xml_example)
    - PostmanParser    (postman_collection)
    """

    @abstractmethod
    def parse(self, file_path: str) -> list[ParsedSection]:
        """Parse a file into a list of structured sections.

        Args:
            file_path: Absolute or relative path to the source file.

        Returns:
            Ordered list of ParsedSection objects. Empty list for empty files.

        Raises:
            IngestionError: If the file cannot be read or parsed.
        """

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return the file extensions this parser handles.

        Returns:
            List of lowercase extensions, e.g. [".md", ".markdown"].
        """
