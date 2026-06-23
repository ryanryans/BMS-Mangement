"""Memory endpoints — list, view, delete memories."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.api.responses import success_response
from src.api.schemas import ApiResponse, MemoryData
from src.memory.memory_manager import get_memory_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["memory"])


@router.get("/memory", response_model=ApiResponse)
def memory_status() -> dict:
    """Get all memories."""
    manager = get_memory_manager()
    items = manager.list_memories()
    data = MemoryData(
        enabled=len(items) > 0,
        items=items,
        note=f"Total {len(items)} long-term memory items.",
    )
    return success_response("Memory list retrieved.", data.model_dump())


@router.delete("/memory/{memory_id}", response_model=ApiResponse)
def delete_memory(memory_id: str) -> dict:
    """Delete a specific memory."""
    manager = get_memory_manager()
    deleted = manager.delete_memory(memory_id)
    if deleted:
        return success_response(f"Memory '{memory_id}' deleted.")
    raise HTTPException(status_code=404, detail=f"Memory '{memory_id}' not found.")
