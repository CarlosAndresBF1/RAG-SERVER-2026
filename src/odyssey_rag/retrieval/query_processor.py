"""Query processor — parsing, expansion, and filter building.

Transforms a raw user query (from an MCP tool or API call) into
optimized forms for both vector and BM25 search, and builds metadata
filters for pre-filtering the result set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ── ISO 20022 abbreviation expansion table ────────────────────────────────────

EXPANSIONS: dict[str, str] = {
    "pacs": "payment clearing and settlement",
    "camt": "cash management",
    "pain": "payment initiation",
    "acmt": "account management",
    "admi": "administration",
    "GrpHdr": "Group Header",
    "CdtTrfTxInf": "Credit Transfer Transaction Information",
    "SttlmInf": "Settlement Information",
    "RsltnOfInvstgtn": "Resolution of Investigation",
    "FIToFICstmrCdtTrf": "FI-to-FI Customer Credit Transfer",
    "FIToFIPmtStsRpt": "FI-to-FI Payment Status Report",
    "FIToFIPmtCxlReq": "FI-to-FI Payment Cancellation Request",
    "BIC": "Business Identifier Code",
    "BICFI": "Business Identifier Code Financial Institution",
    "IBAN": "International Bank Account Number",
    "UETR": "Unique End-to-End Transaction Reference",
    "MsgId": "Message Identification",
    "CreDtTm": "Creation Date Time",
    "NbOfTxs": "Number of Transactions",
    "IntrBkSttlmAmt": "Interbank Settlement Amount",
    "PmtId": "Payment Identification",
    "M": "Mandatory",
    "O": "Optional",
    "C": "Conditional",
    "D": "Dependent",
}

# ── Message type detection patterns ──────────────────────────────────────────

_MSG_TYPE_PATTERNS: dict[str, list[str]] = {
    "pacs.008": [r"pacs\.008", r"FIToFICstmrCdtTrf", r"credit.?transfer", r"pacs\s*008"],
    "pacs.002": [r"pacs\.002", r"FIToFIPmtStsRpt", r"payment.?status", r"pacs\s*002"],
    "pacs.004": [r"pacs\.004", r"PmtRtr", r"payment.?return", r"pacs\s*004"],
    "pacs.028": [r"pacs\.028", r"FIToFIPmtStsReq", r"status.?request", r"pacs\s*028"],
    "camt.056": [r"camt\.056", r"FIToFIPmtCxlReq", r"recall", r"cancellation", r"camt\s*056"],
    "camt.029": [r"camt\.029", r"RsltnOfInvstgtn", r"resolution", r"camt\s*029"],
    "pain.001": [r"pain\.001", r"CstmrCdtTrfInitn", r"payment.?initiation", r"pain\s*001"],
    "pain.002": [r"pain\.002", r"CstmrPmtStsRpt", r"pain\s*002"],
    "pain.013": [r"pain\.013", r"CdtrPmtActvtnReq", r"request.?to.?pay", r"pain\s*013"],
    "pain.014": [r"pain\.014", r"CdtrPmtActvtnReqStsRpt", r"pain\s*014"],
}

_COMPILED_MSG_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    msg: [re.compile(p, re.IGNORECASE) for p in patterns]
    for msg, patterns in _MSG_TYPE_PATTERNS.items()
}

# ── Intent keyword patterns ───────────────────────────────────────────────────

_INTENT_PATTERNS: dict[str, list[str]] = {
    "message_type": [
        r"\bfields?\b", r"\bxpath\b", r"\bstructure\b", r"\bformat\b",
        r"\bspecification\b", r"\bannex\b", r"\bschema\b", r"\bdefinition\b",
    ],
    "business_rule": [
        r"\brule\b", r"\bmandatory\b", r"\boptional\b", r"\bconditional\b",
        r"\bvalidat\b", r"\bconstraint\b", r"\brequir\b", r"\bstatus\b.*\bM\b",
    ],
    "module": [
        r"\bclass\b", r"\bphp\b", r"\bmethod\b", r"\bimplement\b", r"\bcode\b",
        r"\bbuilder?\b", r"\bparser?\b", r"\bmodule\b", r"\bfunction\b",
    ],
    "error": [
        r"\berror\b", r"\bfail", r"\breject", r"\bRJCT\b", r"\bexception\b",
        r"\binvalid\b", r"\bwrong\b", r"\bproblem\b", r"\bfix\b",
    ],
}

_COMPILED_INTENT: dict[str, list[re.Pattern[str]]] = {
    intent: [re.compile(p, re.IGNORECASE) for p in patterns]
    for intent, patterns in _INTENT_PATTERNS.items()
}


@dataclass
class ProcessedQuery:
    """Processed version of the user's raw query.

    Attributes:
        raw:                    Original query text.
        normalized:             Lowercase, stripped.
        detected_message_type:  e.g. ``"pacs.008"`` or None.
        detected_intent:        One of ``message_type | business_rule | module | error | general``.
        bm25_query:             Expanded query for full-text search.
        vector_query:           Natural-language query for semantic search.
        metadata_filters:       Key-value filters for DB pre-filtering.
    """

    raw: str
    normalized: str
    detected_message_type: Optional[str]
    detected_intent: Optional[str]
    bm25_query: str
    vector_query: str
    metadata_filters: dict[str, str] = field(default_factory=dict)


class QueryProcessor:
    """Transform raw MCP tool input into search-ready queries.

    Usage::

        processor = QueryProcessor()
        q = processor.process("What are the mandatory fields for pacs.008?")
        # q.detected_message_type == "pacs.008"
        # q.detected_intent == "business_rule"
        # q.metadata_filters == {"message_type": "pacs.008"}
    """

    def process(
        self,
        raw_query: str,
        tool_context: Optional[dict[str, str]] = None,
    ) -> ProcessedQuery:
        """Process a raw query into optimized search forms.

        Args:
            raw_query:    The user's text query.
            tool_context: Optional parameters from an MCP tool call
                          (e.g. ``{"message_type": "pacs.008", "intent": "fields"}``).

        Returns:
            ProcessedQuery with all derived fields populated.
        """
        ctx = tool_context or {}
        normalized = raw_query.strip().lower()

        # Message type: prefer explicit tool_context parameter
        msg_type = ctx.get("message_type") or self._detect_message_type(normalized)

        # Intent: prefer explicit tool_context parameter
        intent = ctx.get("intent") or self._detect_intent(normalized)

        bm25_query = self._build_bm25_query(normalized, msg_type)
        vector_query = self._build_vector_query(raw_query, msg_type, intent)
        filters = self._build_filters(ctx, msg_type)

        return ProcessedQuery(
            raw=raw_query,
            normalized=normalized,
            detected_message_type=msg_type,
            detected_intent=intent,
            bm25_query=bm25_query,
            vector_query=vector_query,
            metadata_filters=filters,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _detect_message_type(self, text: str) -> Optional[str]:
        """Return the first matched ISO 20022 message type."""
        scores: dict[str, int] = {}
        for msg_type, patterns in _COMPILED_MSG_PATTERNS.items():
            count = sum(len(p.findall(text)) for p in patterns)
            if count > 0:
                scores[msg_type] = count
        if not scores:
            return None
        return max(scores, key=scores.__getitem__)

    def _detect_intent(self, text: str) -> Optional[str]:
        """Return the best-matching intent for the query."""
        scores: dict[str, int] = {}
        for intent, patterns in _COMPILED_INTENT.items():
            count = sum(len(p.findall(text)) for p in patterns)
            if count > 0:
                scores[intent] = count
        if not scores:
            return "general"
        return max(scores, key=scores.__getitem__)

    def _build_bm25_query(
        self, normalized: str, msg_type: Optional[str]
    ) -> str:
        """Expand abbreviations and add synonyms for BM25 search."""
        expanded = normalized
        for abbr, full in EXPANSIONS.items():
            if abbr.lower() in expanded:
                expanded = f"{expanded} {full}"
        if msg_type and msg_type not in expanded:
            expanded = f"{msg_type} {expanded}"
        return expanded

    def _build_vector_query(
        self,
        raw_query: str,
        msg_type: Optional[str],
        intent: Optional[str],
    ) -> str:
        """Build a natural-language query optimized for semantic search."""
        parts = [raw_query]
        if msg_type and msg_type.lower() not in raw_query.lower():
            parts.append(f"(ISO 20022 {msg_type})")
        if intent == "business_rule":
            parts.append("mandatory optional conditional field rule")
        elif intent == "module":
            parts.append("PHP class implementation code")
        return " ".join(parts)

    def _build_filters(
        self,
        ctx: dict[str, str],
        msg_type: Optional[str],
    ) -> dict[str, str]:
        """Build metadata filter dict for pre-filtering search results."""
        filters: dict[str, str] = {}
        if msg_type:
            filters["message_type"] = msg_type
        if "source_type" in ctx:
            filters["source_type"] = ctx["source_type"]
        return filters
