"""Shared output conversion helpers for MCP tool handlers.

All tools share the same output contract:
    {
        "evidence": [...],
        "gaps": [...],
        "followups": [...]
    }

Evidence items follow the MCP_TOOLS.md schema with score, snippet,
citations, and metadata.
"""

from __future__ import annotations

from odyssey_rag.retrieval.response_builder import RetrievalResponse


def to_mcp_output(response: RetrievalResponse) -> dict:
    """Convert a RetrievalResponse to the standard MCP output contract dict."""
    evidence = []
    for e in response.evidence:
        evidence.append(
            {
                "score": round(e.relevance, 4),
                "snippet": e.text,
                "citations": [
                    {
                        "source_type": e.source_type,
                        "source_id": c.source_path,
                        "locator": c.section or "",
                    }
                    for c in e.citations
                ],
                "metadata": {
                    "message_type": e.message_type,
                    "source_type": e.source_type,
                },
            }
        )
    return {
        "evidence": evidence,
        "gaps": response.gaps,
        "followups": response.followups,
    }
