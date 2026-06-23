"""Feedback endpoint — records user feedback persistently."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.api.responses import success_response
from src.api.schemas import ApiResponse, FeedbackData, FeedbackRequest
from src.database.sqlite_manager import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=ApiResponse)
def feedback(request: FeedbackRequest) -> dict:
    """Submit feedback for a conversation or answer."""
    db = get_db()
    feedback_id = db.save_feedback(
        conversation_id=getattr(request, "conversation_id", None),
        feedback_type="rating",
        comment=request.comment,
        corrected_answer=getattr(request, "corrected_answer", None),
    )
    data = FeedbackData(
        feedback_id=feedback_id,
        accepted=True,
    )
    logger.info("Feedback saved: id=%s rating=%d", feedback_id, request.rating)
    return success_response("Feedback recorded.", data.model_dump())
