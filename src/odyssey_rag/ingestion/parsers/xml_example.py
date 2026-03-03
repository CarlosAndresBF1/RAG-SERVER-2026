"""ISO 20022 XML example parser.

Parses ISO 20022 XML message files and extracts structural sections
(AppHdr, GrpHdr, transaction blocks) along with message type metadata.
Uses the standard library ``xml.etree.ElementTree``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from odyssey_rag.ingestion.parsers.base import BaseParser, ParsedSection

# Namespace → short message-type prefix mapping
_NS_MESSAGE_MAP: dict[str, str] = {
    "urn:iso:std:iso:20022:tech:xsd:pacs.008": "pacs.008",
    "urn:iso:std:iso:20022:tech:xsd:pacs.002": "pacs.002",
    "urn:iso:std:iso:20022:tech:xsd:pacs.004": "pacs.004",
    "urn:iso:std:iso:20022:tech:xsd:pacs.028": "pacs.028",
    "urn:iso:std:iso:20022:tech:xsd:camt.056": "camt.056",
    "urn:iso:std:iso:20022:tech:xsd:camt.029": "camt.029",
    "urn:iso:std:iso:20022:tech:xsd:pain.001": "pain.001",
    "urn:iso:std:iso:20022:tech:xsd:pain.002": "pain.002",
    "urn:iso:std:iso:20022:tech:xsd:pain.013": "pain.013",
    "urn:iso:std:iso:20022:tech:xsd:pain.014": "pain.014",
}

# Regex fallback to detect message type from any text
_MSG_TYPE_CONTENT_RE = re.compile(
    r"\b(pacs|camt|pain)\.\d{3}\b",
    re.IGNORECASE,
)

# ISO version pattern (e.g. pacs.008.001.12)
_ISO_VERSION_RE = re.compile(
    r"\b(pacs|camt|pain)\.\d{3}\.\d{3}\.\d{2,3}\b",
    re.IGNORECASE,
)


def _strip_ns(tag: str) -> str:
    """Remove XML namespace URI from a qualified tag name."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _element_to_text(element: ET.Element, indent: int = 0) -> str:
    """Recursively convert an ElementTree element to a readable text representation."""
    pad = "  " * indent
    tag = _strip_ns(element.tag)
    text_val = (element.text or "").strip()
    lines = [f"{pad}<{tag}>{'  ' + text_val if text_val else ''}"]
    for child in element:
        lines.append(_element_to_text(child, indent + 1))
    lines.append(f"{pad}</{tag}>")
    return "\n".join(lines)


def _detect_message_type_from_ns(ns_map: dict[str, str]) -> Optional[str]:
    """Detect message type from XML namespace declarations."""
    for ns_uri, msg_type in _NS_MESSAGE_MAP.items():
        for uri in ns_map.values():
            if uri == ns_uri:
                return msg_type
    return None


def _detect_message_type_from_text(text: str) -> Optional[str]:
    """Fallback: detect message type by scanning text content."""
    m = _MSG_TYPE_CONTENT_RE.search(text)
    return m.group(0).lower() if m else None


def _detect_iso_version(text: str) -> Optional[str]:
    """Extract full ISO 20022 version string from text."""
    m = _ISO_VERSION_RE.search(text)
    return m.group(0).lower() if m else None


class XmlExampleParser(BaseParser):
    """Parse ISO 20022 XML message example files.

    Produces the following sections from each XML file:

    1. ``apphdr`` — Application header fields (From/To BIC, MsgDefIdr, BizMsgIdr).
    2. ``group_header`` — GrpHdr element subtree (message ID, settlement info, etc.).
    3. ``transactions`` — One section per ``CdtTrfTxInf``/``TxInf`` block (or the
       full body when no transaction-level elements exist).
    4. ``full_xml`` — The entire XML document as plain text (for literal matching).
    """

    def parse(self, file_path: str) -> list[ParsedSection]:
        """Parse an XML file into structured sections.

        Args:
            file_path: Path to the ``.xml`` file.

        Returns:
            Ordered list of ParsedSection objects.
        """
        path = Path(file_path)
        raw = path.read_text(encoding="utf-8", errors="replace")

        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            # Corrupt XML — return whole file as a single section
            return [
                ParsedSection(
                    content=raw.strip(),
                    section="xml_parse_error",
                    metadata={"source_file": path.name},
                )
            ]

        # Detect message type
        ns_map = {k: v for k, v in root.attrib.items() if "xmlns" in k}
        # ElementTree does not expose namespace map directly; we scan the raw text
        ns_map_raw = dict(re.findall(r'xmlns(?::(\w+))?="([^"]+)"', raw))
        message_type = _detect_message_type_from_ns(ns_map_raw) or _detect_message_type_from_text(raw)
        iso_version = _detect_iso_version(raw)

        # Try to read AppHdr BIC fields
        from_bic, to_bic = self._extract_apphdr_bics(root, raw)

        base_meta: dict[str, str] = {"source_file": path.name}
        if message_type:
            base_meta["message_type"] = message_type
        if iso_version:
            base_meta["iso_version"] = iso_version
        if from_bic:
            base_meta["from_bic"] = from_bic
        if to_bic:
            base_meta["to_bic"] = to_bic

        sections: list[ParsedSection] = []
        section_name = message_type or path.stem

        # 1. AppHdr section
        apphdr_text = self._extract_apphdr(root)
        if apphdr_text:
            sections.append(
                ParsedSection(
                    content=apphdr_text,
                    section=section_name,
                    subsection="apphdr",
                    metadata=dict(base_meta),
                )
            )

        # 2. Group Header section
        grphdr_text = self._extract_named_element(root, {"GrpHdr", "grpHdr"})
        if grphdr_text:
            sections.append(
                ParsedSection(
                    content=grphdr_text,
                    section=section_name,
                    subsection="group_header",
                    metadata=dict(base_meta),
                )
            )

        # 3. Transaction blocks
        tx_sections = self._extract_transactions(root, section_name, base_meta)
        sections.extend(tx_sections)

        # 4. Full XML (for literal search)
        sections.append(
            ParsedSection(
                content=raw.strip(),
                section=section_name,
                subsection="full_xml",
                metadata=dict(base_meta),
            )
        )

        return sections

    def supported_extensions(self) -> list[str]:
        """Return supported file extensions.

        Returns:
            List containing ``[".xml"]``.
        """
        return [".xml"]

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_apphdr(self, root: ET.Element) -> str:
        """Extract AppHdr element or its equivalent from the root."""
        # ISO 20022 business application header is commonly in the root or first child
        for elem in root.iter():
            tag = _strip_ns(elem.tag)
            if tag in ("AppHdr", "BizMsgEnvlp", "BusinessApplicationHeader"):
                return _element_to_text(elem)
        return ""

    def _extract_apphdr_bics(
        self, root: ET.Element, raw: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Extract From/To BIC codes from AppHdr fields."""
        from_bic: Optional[str] = None
        to_bic: Optional[str] = None

        for elem in root.iter():
            tag = _strip_ns(elem.tag)
            if tag in ("Fr", "From"):
                # BIC is typically nested inside Fr/FIId/FinInstnId/BICFI
                for child in elem.iter():
                    if _strip_ns(child.tag) in ("BICFI", "BIC"):
                        from_bic = (child.text or "").strip() or None
                        break
            elif tag in ("To",):
                for child in elem.iter():
                    if _strip_ns(child.tag) in ("BICFI", "BIC"):
                        to_bic = (child.text or "").strip() or None
                        break

        # Regex fallback
        if not from_bic:
            m = re.search(r"<Fr>.*?<BICFI>([^<]+)</BICFI>", raw, re.DOTALL)
            if m:
                from_bic = m.group(1).strip()
        if not to_bic:
            m = re.search(r"<To>.*?<BICFI>([^<]+)</BICFI>", raw, re.DOTALL)
            if m:
                to_bic = m.group(1).strip()

        return from_bic, to_bic

    def _extract_named_element(
        self, root: ET.Element, tag_names: set[str]
    ) -> str:
        """Find first element whose local name is in *tag_names* and convert to text."""
        for elem in root.iter():
            if _strip_ns(elem.tag) in tag_names:
                return _element_to_text(elem)
        return ""

    def _extract_transactions(
        self,
        root: ET.Element,
        section_name: str,
        base_meta: dict[str, str],
    ) -> list[ParsedSection]:
        """Extract individual transaction/instruction blocks."""
        tx_tags = {"CdtTrfTxInf", "TxInf", "OrgnlTxRef", "RtrRsnInf", "Ntfctn"}
        tx_elements = [e for e in root.iter() if _strip_ns(e.tag) in tx_tags]

        if not tx_elements:
            # No transaction-level elements: treat full body as transactions section
            body_text = _element_to_text(root)
            if body_text:
                return [
                    ParsedSection(
                        content=body_text,
                        section=section_name,
                        subsection="body",
                        metadata=dict(base_meta),
                    )
                ]
            return []

        sections = []
        for i, elem in enumerate(tx_elements):
            content = _element_to_text(elem)
            meta = dict(base_meta)
            meta["transaction_index"] = str(i)
            sections.append(
                ParsedSection(
                    content=content,
                    section=section_name,
                    subsection=f"transaction_{i}",
                    metadata=meta,
                )
            )

        return sections
