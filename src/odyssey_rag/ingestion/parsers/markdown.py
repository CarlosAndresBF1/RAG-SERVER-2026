"""Markdown document parser.

Splits Markdown files by heading hierarchy (H1 → H2 → H3) into
ParsedSection objects. Designed primarily for Annex B specifications
and general technical documentation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from odyssey_rag.ingestion.parsers.base import BaseParser, ParsedSection

# Pattern that detects ISO 20022 message type prefixes in heading text
_MSG_TYPE_RE = re.compile(
    r"\b(pacs|camt|pain|acmt|admi|auth|caaa|caad|cain|camt|cafm|"
    r"reda|remt|secl|seev|setr|sese|semt|trck|xpay)\.\d{3}",
    re.IGNORECASE,
)

# Pattern that captures the full versioned message type (e.g. pacs.008.001.12)
_ISO_VERSION_RE = re.compile(
    r"\b(pacs|camt|pain|acmt|admi)\.\d{3}\.\d{3}\.\d{2,3}\b",
    re.IGNORECASE,
)

# Heading line pattern: capture level (1-3) and heading text
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

# Field names extracted from Annex B table content (comma-separated)
_FIELD_NAME_RE = re.compile(r"\|\s*([A-Za-z][A-Za-z0-9/]+)\s*\|")


def _extract_message_type(text: str) -> Optional[str]:
    """Return the first ISO 20022 message type found in text."""
    m = _MSG_TYPE_RE.search(text)
    if m:
        return m.group(0).lower()
    return None


def _extract_iso_version(text: str) -> Optional[str]:
    """Return the first full ISO version string found in text."""
    m = _ISO_VERSION_RE.search(text)
    if m:
        return m.group(0).lower()
    return None


def _extract_field_names(content: str) -> str:
    """Extract field names from Annex B table rows.

    Returns a comma-separated string of XPath-style field names found in
    the first column of Markdown table rows, e.g. ``"MsgId,CreDtTm,NbOfTxs"``.
    """
    names = _FIELD_NAME_RE.findall(content)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for n in names:
        if n not in seen and "/" not in n:
            seen.add(n)
            unique.append(n)
    return ",".join(unique)


class MarkdownParser(BaseParser):
    """Parse Markdown files into heading-delimited sections.

    Splits at H1, H2, and H3 boundaries. Each resulting section carries
    ``section`` (the H1/H2 text) and ``subsection`` (the H3 text, if any).
    Content between headings of the same level is grouped together.

    For Annex B specification files the parser additionally attempts to
    detect ``message_type``, ``iso_version``, and ``fields_in_section``
    metadata hints from the heading text and table content.
    """

    def parse(self, file_path: str) -> list[ParsedSection]:
        """Parse a Markdown file into structured sections.

        Args:
            file_path: Absolute or relative path to the ``.md`` file.

        Returns:
            Ordered list of ParsedSection objects with heading context.
        """
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        return self._split_by_headings(text)

    def supported_extensions(self) -> list[str]:
        """Return supported file extensions.

        Returns:
            List containing ``[".md", ".txt", ".rst"]``.
        """
        return [".md", ".txt", ".rst"]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _split_by_headings(self, text: str) -> list[ParsedSection]:
        """Split raw Markdown text into ParsedSection objects."""
        # Find all heading positions
        matches = list(_HEADING_RE.finditer(text))
        if not matches:
            # No headings — whole document is one section
            stripped = text.strip()
            if stripped:
                return [ParsedSection(content=stripped)]
            return []

        sections: list[ParsedSection] = []

        # Any content before the first heading
        pre = text[: matches[0].start()].strip()
        if pre:
            sections.append(ParsedSection(content=pre))

        # Track current heading context
        current_h1: Optional[str] = None
        current_h2: Optional[str] = None
        current_h3: Optional[str] = None

        for idx, match in enumerate(matches):
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # Content between this heading and the next
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()

            # Update heading context
            if level == 1:
                current_h1 = heading_text
                current_h2 = None
                current_h3 = None
            elif level == 2:
                current_h2 = heading_text
                current_h3 = None
            else:  # level == 3
                current_h3 = heading_text

            # Determine section / subsection labels
            section = current_h1 or current_h2
            subsection = current_h3 if level == 3 else (current_h2 if level == 2 else None)

            if not body:
                continue  # Skip empty content blocks

            # Build metadata hints
            full_text = f"{heading_text}\n{body}"
            metadata: dict[str, str] = {}

            msg_type = _extract_message_type(full_text)
            if msg_type:
                metadata["message_type"] = msg_type

            iso_ver = _extract_iso_version(full_text)
            if iso_ver:
                metadata["iso_version"] = iso_ver

            # Detect Annex B field tables (contain XPath patterns like GrpHdr/MsgId)
            if "|" in body and "/" in body:
                fields = _extract_field_names(body)
                if fields:
                    metadata["fields_in_section"] = fields

            sections.append(
                ParsedSection(
                    content=body,
                    section=section,
                    subsection=subsection,
                    metadata=metadata,
                )
            )

        return sections
