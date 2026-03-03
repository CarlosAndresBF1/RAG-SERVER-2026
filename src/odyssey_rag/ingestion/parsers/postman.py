"""Postman collection JSON parser.

Parses Postman v2.1 collection files into ParsedSection objects where
each HTTP request becomes one section. Folder structure maps to
section/subsection hierarchy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from odyssey_rag.ingestion.parsers.base import BaseParser, ParsedSection

# Regex to detect ISO 20022 message type from URL or request body
_MSG_TYPE_RE = re.compile(
    r"\b(pacs|camt|pain|acmt|admi)\.\d{3}\b",
    re.IGNORECASE,
)


def _detect_message_type(text: str) -> Optional[str]:
    """Return the first ISO 20022 message type prefix found in text."""
    m = _MSG_TYPE_RE.search(text)
    return m.group(0).lower() if m else None


def _format_headers(headers: list[dict[str, Any]]) -> str:
    """Format a list of Postman header objects as readable text."""
    if not headers:
        return ""
    lines = []
    for h in headers:
        key = h.get("key", "")
        value = h.get("value", "")
        if key:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def _format_body(body: Optional[dict[str, Any]]) -> str:
    """Format Postman request body as readable text."""
    if not body:
        return ""
    mode = body.get("mode", "")
    if mode == "raw":
        raw = body.get("raw", "")
        return raw if raw else ""
    if mode == "urlencoded":
        items = body.get("urlencoded", [])
        pairs = [f"{i.get('key', '')}={i.get('value', '')}" for i in items]
        return "&".join(pairs)
    if mode == "formdata":
        items = body.get("formdata", [])
        pairs = [f"{i.get('key', '')}={i.get('value', '')}" for i in items]
        return "\n".join(pairs)
    return str(body)


def _format_response(response: dict[str, Any]) -> str:
    """Format a Postman example response as readable text."""
    name = response.get("name", "response")
    status = response.get("status", "")
    code = response.get("code", "")
    body = response.get("body", "") or ""
    return f"Example Response — {name} ({code} {status}):\n{body}"


class PostmanParser(BaseParser):
    """Parse Postman collection v2.1 JSON files into request sections.

    Each HTTP request in the collection becomes one ParsedSection.
    Folder structure in the collection maps to:
    - ``section``: top-level folder name (or collection name if no folders).
    - ``subsection``: request name.

    Content includes method, URL, headers, request body, and example responses.
    """

    def parse(self, file_path: str) -> list[ParsedSection]:
        """Parse a Postman collection file into structured sections.

        Args:
            file_path: Path to the ``.postman_collection.json`` file.

        Returns:
            Ordered list of ParsedSection objects (one per request).
        """
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="replace")

        try:
            collection = json.loads(text)
        except json.JSONDecodeError:
            return [
                ParsedSection(
                    content=text.strip(),
                    section="postman_parse_error",
                    metadata={"source_file": path.name},
                )
            ]

        collection_name = (
            collection.get("info", {}).get("name", path.stem)
        )
        items = collection.get("item", [])
        sections: list[ParsedSection] = []
        self._traverse_items(items, collection_name, None, sections)
        return sections

    def supported_extensions(self) -> list[str]:
        """Return supported file extensions.

        Returns:
            List containing ``[".json"]``.
        """
        return [".json"]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _traverse_items(
        self,
        items: list[dict[str, Any]],
        section: str,
        subsection: Optional[str],
        sections: list[ParsedSection],
    ) -> None:
        """Recursively traverse Postman collection items."""
        for item in items:
            # Sub-folder: recurse with updated section hierarchy
            if "item" in item:
                folder_name = item.get("name", "")
                # Use folder as subsection when inside a top-level section;
                # otherwise promote it to section
                if subsection is None:
                    self._traverse_items(item["item"], section, folder_name, sections)
                else:
                    self._traverse_items(item["item"], section, f"{subsection}/{folder_name}", sections)
            else:
                # Leaf request
                section_obj = self._parse_request(item, section, subsection)
                if section_obj is not None:
                    sections.append(section_obj)

    def _parse_request(
        self,
        item: dict[str, Any],
        section: str,
        subsection: Optional[str],
    ) -> Optional[ParsedSection]:
        """Convert a single Postman request item to a ParsedSection."""
        request = item.get("request")
        if not request:
            return None

        name = item.get("name", "unnamed")
        method = request.get("method", "GET")

        # URL
        url_obj = request.get("url", {})
        if isinstance(url_obj, str):
            url = url_obj
        else:
            url = url_obj.get("raw", "")

        # Headers
        headers_raw = request.get("header", [])
        headers_text = _format_headers(headers_raw)

        # Body
        body_text = _format_body(request.get("body"))

        # Example responses
        response_texts: list[str] = []
        for resp in item.get("response", []):
            response_texts.append(_format_response(resp))

        # Build readable content
        parts = [f"{method} {url}"]
        if headers_text:
            parts.append(f"Headers:\n{headers_text}")
        if body_text:
            parts.append(f"Request Body:\n{body_text}")
        for r in response_texts[:3]:  # Cap at 3 examples
            parts.append(r)

        content = "\n\n".join(parts)

        # Metadata
        meta: dict[str, str] = {"request_method": method}
        if url:
            meta["url"] = url
        msg_type = _detect_message_type(content)
        if msg_type:
            meta["message_type"] = msg_type

        return ParsedSection(
            content=content,
            section=section,
            subsection=subsection or name,
            metadata=meta,
        )
