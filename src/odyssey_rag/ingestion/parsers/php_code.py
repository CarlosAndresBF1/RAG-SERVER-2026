"""PHP source code parser.

Extracts class-level documentation and method-level sections from PHP
source files using regex-based analysis (no PHP AST required).
"""

from __future__ import annotations

import re
from pathlib import Path

from odyssey_rag.ingestion.parsers.base import BaseParser, ParsedSection

# Regex patterns for PHP structural elements
_CLASS_RE = re.compile(
    r"((?:/\*\*.*?\*/\s*)?)"  # Optional docblock (non-greedy)
    r"(?:abstract\s+|final\s+)?"
    r"class\s+(\w+)"  # Class name (group 2)
    r"(?:\s+extends\s+\w+)?"
    r"(?:\s+implements\s+[\w,\s]+)?",
    re.DOTALL,
)

_METHOD_RE = re.compile(
    r"((?:/\*\*.*?\*/\s*)?)"  # Optional docblock (non-greedy, group 1)
    r"(public|protected|private|static|\s)+"  # Visibility (group 2)
    r"\s*function\s+(\w+)\s*"  # Function name (group 3)
    r"\([^)]*\)"  # Parameters
    r"(?:\s*:\s*\??\w+)?",  # Optional return type hint
    re.DOTALL,
)

_CONST_RE = re.compile(r"(?:public\s+|protected\s+|private\s+)?const\s+(\w+)\s*=")

_PROPERTY_RE = re.compile(
    r"(?:public|protected|private)\s+(?:static\s+)?\??(?:\w+\s+)?\$(\w+)"
)

# Brace-matching helper: find the closing brace for a block starting at pos
_OPEN_BRACE_RE = re.compile(r"\{")
_CLOSE_BRACE_RE = re.compile(r"\}")


def _find_block_end(text: str, start: int) -> int:
    """Return the index of the closing brace that matches the opening brace at *start*.

    Scans forward from *start* counting brace depth. Returns -1 if not found.
    String literals and comments are not handled for performance reasons;
    this is acceptable for the ingestion use case where correctness of
    extraction matters more than perfect edge-case handling.
    """
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


class PhpCodeParser(BaseParser):
    """Parse PHP files into class/method-level ParsedSections.

    Extraction strategy:
    1. Find the class declaration and its docblock → ``class_overview`` section.
    2. Collect all constants and properties → ``constants_properties`` section.
    3. Extract each method with its docblock + signature + body → one section each.

    The relative file path is stored as ``module_path`` metadata on every
    resulting section.
    """

    def parse(self, file_path: str) -> list[ParsedSection]:
        """Parse a PHP file into structured sections.

        Args:
            file_path: Path to the ``.php`` file.

        Returns:
            Ordered list of ParsedSection objects.
        """
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        return self._extract_sections(text, str(path))

    def supported_extensions(self) -> list[str]:
        """Return supported file extensions.

        Returns:
            List containing ``[".php"]``.
        """
        return [".php"]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_sections(self, text: str, file_path: str) -> list[ParsedSection]:
        """Extract ParsedSection objects from PHP source text."""
        sections: list[ParsedSection] = []
        module_path = file_path

        # 1. Detect class name
        class_match = _CLASS_RE.search(text)
        class_name = class_match.group(2) if class_match else Path(file_path).stem

        # 2. Class overview: docblock + class declaration up to first method/property
        overview_content = self._extract_class_overview(text, class_name, file_path)
        if overview_content:
            sections.append(
                ParsedSection(
                    content=overview_content,
                    section=class_name,
                    subsection="class_overview",
                    metadata={
                        "php_class": class_name,
                        "module_path": module_path,
                    },
                )
            )

        # 3. Constants and properties
        consts_props = self._extract_consts_properties(text, class_name)
        if consts_props:
            sections.append(
                ParsedSection(
                    content=consts_props,
                    section=class_name,
                    subsection="constants_properties",
                    metadata={
                        "php_class": class_name,
                        "module_path": module_path,
                    },
                )
            )

        # 4. Methods
        for method_name, method_content in self._extract_methods(text):
            sections.append(
                ParsedSection(
                    content=method_content,
                    section=class_name,
                    subsection=method_name,
                    metadata={
                        "php_class": class_name,
                        "php_symbol": method_name,
                        "module_path": module_path,
                    },
                )
            )

        # Fallback: if nothing was extracted, return whole file as one section
        if not sections:
            sections.append(
                ParsedSection(
                    content=text.strip(),
                    section=class_name,
                    metadata={"module_path": module_path},
                )
            )

        return sections

    def _extract_class_overview(
        self, text: str, class_name: str, file_path: str
    ) -> str:
        """Extract the class-level docblock and declaration header."""
        class_match = _CLASS_RE.search(text)
        if not class_match:
            return ""

        # Start from the beginning of the docblock or class keyword
        start = class_match.start()
        class_end_in_text = class_match.end()

        # Find the opening brace of the class body
        open_brace = text.find("{", class_end_in_text)
        if open_brace == -1:
            return text[start:class_end_in_text].strip()

        # Take just the class declaration + a few lines inside (not full body)
        snippet_end = min(open_brace + 200, len(text))
        return text[start:snippet_end].strip()

    def _extract_consts_properties(self, text: str, class_name: str) -> str:
        """Extract constant and property declarations."""
        consts = _CONST_RE.findall(text)
        props = _PROPERTY_RE.findall(text)

        parts = []
        if consts:
            parts.append("Constants: " + ", ".join(consts))
        if props:
            parts.append("Properties: " + ", ".join(f"${p}" for p in props))

        if not parts:
            return ""
        return f"Class: {class_name}\n\n" + "\n".join(parts)

    def _extract_methods(self, text: str) -> list[tuple[str, str]]:
        """Extract (method_name, full_method_text) pairs."""
        results: list[tuple[str, str]] = []

        for m in _METHOD_RE.finditer(text):
            method_name = m.group(3)
            docblock = m.group(1).strip()

            # Find the opening brace of the method body
            brace_start = text.find("{", m.end())
            if brace_start == -1:
                continue

            brace_end = _find_block_end(text, brace_start)
            if brace_end == -1:
                continue

            # Compose readable snippet
            header = m.group(0).strip()
            body = text[brace_start : brace_end + 1]

            # Limit body to 2000 chars to avoid huge chunks; truncate cleanly
            if len(body) > 2000:
                body = body[:2000].rstrip() + "\n    // ... (truncated)"

            content_parts = []
            if docblock:
                content_parts.append(docblock)
            content_parts.append(header)
            content_parts.append(body)

            results.append((method_name, "\n".join(content_parts)))

        return results
