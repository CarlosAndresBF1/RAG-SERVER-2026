"""Feedback endpoint — POST /api/v1/feedback.

Stores user/agent quality ratings for retrieval responses.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.deps import get_async_session
from odyssey_rag.api.schemas import FeedbackRequest, FeedbackResponse
from odyssey_rag.db.models import Feedback
from odyssey_rag.db.repositories.feedback import FeedbackRepository

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
) -> FeedbackResponse:
    """Record quality feedback for a retrieved chunk."""
    try:
        chunk_uuid = uuid.UUID(request.chunk_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid chunk_id format (expected UUID)"
        )

    feedback_repo = FeedbackRepository(session)
    feedback = Feedback(
        id=uuid.uuid4(),
        query=request.query,
        chunk_ids=[chunk_uuid],
        rating=request.rating,
        comment=request.comment,
    )
    await feedback_repo.insert(feedback)

    return FeedbackResponse(id=str(feedback.id), status="accepted")
