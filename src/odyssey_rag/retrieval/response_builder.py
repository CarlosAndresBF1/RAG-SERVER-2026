"""Response builder — assembles search results into the MCP output contract.

Converts a list of reranked SearchResult objects into a structured
RetrievalResponse with evidence items, knowledge-gap messages, and
follow-up query suggestions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from odyssey_rag.retrieval.query_processor import ProcessedQuery
from odyssey_rag.retrieval.vector_search import SearchResult

# Score normalisation: cross-encoder raw scores are approximately in
# [-10, 10].  We map to [0.0, 1.0] with a sigmoid.
_SIGMOID_SCALE = 1.0


def _sigmoid(x: float) -> float:
    """Sigmoid function for score normalization."""
    return 1.0 / (1.0 + math.exp(-x * _SIGMOID_SCALE))


@dataclass
class Citation:
    """Source reference for an evidence item.

    Attributes:
        source_path:  File path of the originating document.
        section:      Section label within the document.
        chunk_index:  Zero-based chunk position in the document.
    """

    source_path: str
    section: Optional[str]
    chunk_index: int


@dataclass
class Evidence:
    """A relevant chunk with relevance score and source citation.

    Attributes:
        text:         Chunk content (full text, no truncation in storage).
        relevance:    Normalized relevance score in [0.0, 1.0].
        citations:    Source references for this chunk.
        message_type: ISO 20022 message type, if applicable.
        source_type:  Document source type (e.g. ``"annex_b_spec"``).
    """

    text: str
    relevance: float
    citations: list[Citation] = field(default_factory=list)
    message_type: Optional[str] = None
    source_type: str = ""


@dataclass
class RetrievalResponse:
    """Structured response returned by the retrieval engine.

    This is the primary output contract consumed by MCP tools and the
    API layer.

    Attributes:
        query:     The original raw query string.
        evidence:  Top relevant chunks above the relevance threshold.
        gaps:      Identified knowledge gaps.
        followups: Suggested follow-up queries.
    """

    query: str
    evidence: list[Evidence] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    followups: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary for JSON output."""
        return {
            "query": self.query,
            "evidence": [
                {
                    "text": e.text,
                    "relevance": round(e.relevance, 4),
                    "message_type": e.message_type,
                    "source_type": e.source_type,
                    "citations": [
                        {
                            "source_path": c.source_path,
                            "section": c.section,
                            "chunk_index": c.chunk_index,
                        }
                        for c in e.citations
                    ],
                }
                for e in self.evidence
            ],
            "gaps": self.gaps,
            "followups": self.followups,
        }


class ResponseBuilder:
    """Assemble reranked search results into a structured RetrievalResponse.

    Args:
        threshold:          Minimum normalized relevance score (0.0–1.0)
                            to include a result as evidence (default 0.3).
        max_evidence_items: Maximum number of evidence items (default 8).
        max_followups:      Maximum follow-up suggestions (default 3).
    """

    def __init__(
        self,
        threshold: float = 0.3,
        max_evidence_items: int = 8,
        max_followups: int = 3,
    ) -> None:
        self.threshold = threshold
        self.max_evidence_items = max_evidence_items
        self.max_followups = max_followups

    def build(
        self,
        query: ProcessedQuery,
        reranked: list[SearchResult],
    ) -> RetrievalResponse:
        """Build a RetrievalResponse from reranked search results.

        Args:
            query:    The processed query (for gap/followup generation).
            reranked: Reranked SearchResult list (from reranker.rerank()).

        Returns:
            Structured RetrievalResponse.
        """
        evidence = self._build_evidence(reranked)
        gaps = self._detect_gaps(query, evidence)
        followups = self._suggest_followups(query, evidence)

        return RetrievalResponse(
            query=query.raw,
            evidence=evidence,
            gaps=gaps,
            followups=followups,
        )

    # ── Evidence building ─────────────────────────────────────────────────────

    def _build_evidence(self, reranked: list[SearchResult]) -> list[Evidence]:
        """Convert reranked results to Evidence items above threshold."""
        items: list[Evidence] = []
        for result in reranked:
            norm_score = _sigmoid(result.rerank_score)
            if norm_score < self.threshold:
                continue
            items.append(
                Evidence(
                    text=result.content,
                    relevance=round(norm_score, 4),
                    citations=[
                        Citation(
                            source_path=result.source_path,
                            section=result.section,
                            chunk_index=result.chunk_index,
                        )
                    ],
                    message_type=result.message_type,
                    source_type=result.source_type,
                )
            )
            if len(items) >= self.max_evidence_items:
                break
        return items

    # ── Gap detection ─────────────────────────────────────────────────────────

    def _detect_gaps(
        self, query: ProcessedQuery, evidence: list[Evidence]
    ) -> list[str]:
        """Identify knowledge gaps based on query vs available evidence."""
        gaps: list[str] = []

        if not evidence:
            gaps.append(f"No relevant documentation found for: {query.raw}")
            return gaps

        msg_type = query.detected_message_type
        intent = query.detected_intent

        # Annex B spec missing for a message_type query
        if msg_type:
            annex_sources = [e for e in evidence if e.source_type == "annex_b_spec"]
            if not annex_sources:
                gaps.append(
                    f"No Annex B specification found for {msg_type}. "
                    "Try ingesting IPS_Annex_B_Message_Specifications.md"
                )

        # PHP code missing for a module query
        if intent == "module":
            code_sources = [e for e in evidence if e.source_type == "php_code"]
            if not code_sources:
                gaps.append("No PHP implementation code found for this query")

        # Low confidence across all results
        if evidence and max(e.relevance for e in evidence) < 0.5:
            gaps.append(
                "All results have low confidence — consider rephrasing the query "
                "or using a more specific message type"
            )

        return gaps

    # ── Follow-up suggestions ─────────────────────────────────────────────────

    def _suggest_followups(
        self, query: ProcessedQuery, evidence: list[Evidence]
    ) -> list[str]:
        """Suggest useful next queries based on the current result set."""
        followups: list[str] = []
        msg_type = query.detected_message_type
        intent = query.detected_intent

        if msg_type and intent in ("message_type", "general"):
            followups.append(f"Find mandatory business rules for {msg_type}")
            followups.append(f"Find the PHP module implementing {msg_type}")

        if intent == "business_rule" and msg_type:
            followups.append(f"Find the PHP builder/parser for {msg_type}")

        if intent == "module":
            followups.append("Find the Annex B field specification for the related message type")
            followups.append("Find tests for this module")

        if intent == "error":
            followups.append("Search for the payment status report (pacs.002) reason codes")

        return followups[: self.max_followups]
