"""Metadata extractor for ingestion pipeline.

Derives structured ChunkMetadata from Chunk objects based on content
analysis and parser-provided hints. Supports ISO 20022 domain concepts
(message types, XPaths, rule status, data types) and Odyssey PHP code
domain concepts (class, symbol, module path).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from odyssey_rag.ingestion.chunkers.base import Chunk

# ── Message type detection patterns ──────────────────────────────────────────

MESSAGE_TYPE_PATTERNS: dict[str, list[str]] = {
    "pacs.008": [r"pacs\.008", r"FIToFICstmrCdtTrf", r"Pacs008", r"CreditTransfer"],
    "pacs.002": [r"pacs\.002", r"FIToFIPmtStsRpt", r"Pacs002", r"PaymentStatusReport"],
    "pacs.004": [r"pacs\.004", r"PmtRtr", r"Pacs004", r"CreditTransferReturn"],
    "pacs.028": [r"pacs\.028", r"FIToFIPmtStsReq", r"Pacs028", r"Investigation"],
    "camt.056": [r"camt\.056", r"FIToFIPmtCxlReq", r"Camt056", r"RecallMessage"],
    "camt.029": [r"camt\.029", r"RsltnOfInvstgtn", r"Camt029", r"NegativeAnswer"],
    "pain.001": [r"pain\.001", r"CstmrCdtTrfInitn", r"Pain001", r"PaymentInitiation"],
    "pain.002": [r"pain\.002", r"CstmrPmtStsRpt", r"Pain002", r"StatusReport"],
    "pain.013": [r"pain\.013", r"CdtrPmtActvtnReq", r"Pain013", r"RequestToPay"],
    "pain.014": [r"pain\.014", r"CdtrPmtActvtnReqStsRpt", r"Pain014", r"RequestToPayResponse"],
}

# Compiled pattern sets for performance
_COMPILED_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    msg_type: [re.compile(p, re.IGNORECASE) for p in patterns]
    for msg_type, patterns in MESSAGE_TYPE_PATTERNS.items()
}

# ISO 20022 versioned message type (e.g. pacs.008.001.12)
_ISO_VERSION_RE = re.compile(
    r"\b(pacs|camt|pain)\.\d{3}\.\d{3}\.\d{2,3}\b",
    re.IGNORECASE,
)

# XPath patterns in Annex B tables (e.g. GrpHdr/MsgId, CdtTrfTxInf/PmtId)
_XPATH_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9]+(?:/[A-Z][a-zA-Z0-9]+)+)\b"
)

# Rule status column in Annex B (M=Mandatory, O=Optional, C=Conditional, D=Dependent)
_RULE_STATUS_RE = re.compile(r"\|\s*([MOCD])\s*\|")

# Data type patterns in Annex B tables
_DATA_TYPE_RE = re.compile(
    r"\b(Max\d+Text|ISODateTime|ActiveCurrencyAndAmount|BICFIIdentifier|"
    r"ExternalCategoryPurpose1Code|TrueFalseIndicator|DecimalNumber|"
    r"Max\d+NumericText|[A-Z][a-zA-Z0-9]+Code|[A-Z][a-zA-Z0-9]+Identifier)\b"
)


@dataclass
class ExtractedMetadata:
    """Structured metadata extracted from a chunk.

    All fields are optional — only populated when evidence is found.
    """

    source_type: str = ""
    message_type: Optional[str] = None
    iso_version: Optional[str] = None
    field_xpath: Optional[str] = None
    rule_status: Optional[str] = None
    data_type: Optional[str] = None
    module_path: Optional[str] = None
    php_class: Optional[str] = None
    php_symbol: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        """Serialize to a plain dictionary (excluding None values)."""
        return {
            k: v
            for k, v in {
                "source_type": self.source_type,
                "message_type": self.message_type,
                "iso_version": self.iso_version,
                "field_xpath": self.field_xpath,
                "rule_status": self.rule_status,
                "data_type": self.data_type,
                "module_path": self.module_path,
                "php_class": self.php_class,
                "php_symbol": self.php_symbol,
            }.items()
            if v is not None
        }


class MetadataExtractor:
    """Extract structured metadata from chunks.

    Combines:
    - Parser-provided hints already stored in ``chunk.metadata``
    - Content-based pattern matching (message types, XPaths, data types)

    Usage::

        extractor = MetadataExtractor()
        meta = extractor.extract(chunk, source_type="annex_b_spec")
    """

    def extract(self, chunk: Chunk, source_type: str) -> ExtractedMetadata:
        """Derive structured metadata from a chunk.

        Args:
            chunk:       Chunk object (from a chunker).
            source_type: Source type string (e.g. ``"annex_b_spec"``).

        Returns:
            ExtractedMetadata with all detected fields populated.
        """
        meta = ExtractedMetadata(source_type=source_type)

        # 1. Seed from parser-provided hints
        hints = chunk.metadata or {}
        if "message_type" in hints:
            meta.message_type = hints["message_type"]
        if "iso_version" in hints:
            meta.iso_version = hints["iso_version"]
        if "php_class" in hints:
            meta.php_class = hints["php_class"]
        if "php_symbol" in hints:
            meta.php_symbol = hints["php_symbol"]
        if "module_path" in hints:
            meta.module_path = hints["module_path"]
        if "field_xpath" in hints:
            meta.field_xpath = hints["field_xpath"]
        if "rule_status" in hints:
            meta.rule_status = hints["rule_status"]
        if "data_type" in hints:
            meta.data_type = hints["data_type"]

        # 2. Auto-detect message type from content (if not provided)
        if not meta.message_type:
            meta.message_type = self._detect_message_type(chunk.content)

        # 3. Auto-detect ISO version (if not provided)
        if not meta.iso_version and meta.message_type:
            meta.iso_version = self._detect_iso_version(chunk.content)

        # 4. Annex B-specific extraction
        if source_type == "annex_b_spec":
            if not meta.field_xpath:
                meta.field_xpath = self._extract_xpath(chunk.content)
            if not meta.rule_status:
                meta.rule_status = self._extract_rule_status(chunk.content)
            if not meta.data_type:
                meta.data_type = self._extract_data_type(chunk.content)

        return meta

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_message_type(self, text: str) -> Optional[str]:
        """Return the best-matching ISO 20022 message type for *text*."""
        scores: dict[str, int] = {}
        for msg_type, patterns in _COMPILED_PATTERNS.items():
            count = sum(len(p.findall(text)) for p in patterns)
            if count > 0:
                scores[msg_type] = count
        if not scores:
            return None
        return max(scores, key=scores.__getitem__)

    def _detect_iso_version(self, text: str) -> Optional[str]:
        """Extract a full ISO 20022 version string from *text*."""
        m = _ISO_VERSION_RE.search(text)
        return m.group(0).lower() if m else None

    def _extract_xpath(self, text: str) -> Optional[str]:
        """Extract the first XPath-like field reference from *text*.

        Looks for patterns like ``GrpHdr/MsgId`` typical in Annex B tables.
        """
        # Prefer table-cell format: first column of a pipe-delimited row
        table_row_re = re.compile(r"^\|\s*([A-Z][a-zA-Z0-9]+/[A-Z][a-zA-Z0-9/]+)\s*\|", re.MULTILINE)
        m = table_row_re.search(text)
        if m:
            return m.group(1)
        # Fallback: any XPath-like expression
        m2 = _XPATH_RE.search(text)
        return m2.group(1) if m2 else None

    def _extract_rule_status(self, text: str) -> Optional[str]:
        """Extract the first rule status character (M/O/C/D) from *text*."""
        m = _RULE_STATUS_RE.search(text)
        return m.group(1) if m else None

    def _extract_data_type(self, text: str) -> Optional[str]:
        """Extract the first ISO 20022 data type name from *text*."""
        m = _DATA_TYPE_RE.search(text)
        return m.group(0) if m else None
