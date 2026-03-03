"""Search endpoint — POST /api/v1/search."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.deps import get_retrieval_engine
from odyssey_rag.api.schemas import CitationSchema, EvidenceItem, SearchRequest, SearchResponse
from odyssey_rag.retrieval.engine import RetrievalEngine

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    engine: RetrievalEngine = Depends(get_retrieval_engine),
    _: str = Depends(verify_api_key),
) -> SearchResponse:
    """Search the knowledge base and return relevant evidence."""
    tool_context: dict[str, str] = {}
    if request.message_type:
        tool_context["message_type"] = request.message_type
    if request.source_type:
        tool_context["source_type"] = request.source_type
    if request.focus:
        tool_context["focus"] = request.focus

    start = time.monotonic()
    response = await engine.search(
        raw_query=request.query,
        tool_context=tool_context or None,
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    evidence = [
        EvidenceItem(
            text=e.text,
            relevance=e.relevance,
            citations=[
                CitationSchema(
                    source_path=c.source_path,
                    section=c.section,
                    chunk_index=c.chunk_index,
                )
                for c in e.citations
            ],
            message_type=e.message_type,
            source_type=e.source_type,
        )
        for e in response.evidence
    ]

    return SearchResponse(
        query=response.query,
        evidence=evidence,
        gaps=response.gaps,
        followups=response.followups,
        metadata={
            "total_candidates": len(response.evidence),
            "search_time_ms": duration_ms,
        },
    )
