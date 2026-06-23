"""Pydantic schemas for the FastAPI service layer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    """Shared API response envelope."""
    success: bool
    message: str
    data: Any | None = None
    error: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = None


class ChatData(BaseModel):
    answer: str
    conversation_id: str | None = None
    question_type: str = "general_chat"
    sources: list[dict[str, Any]] = []
    confidence: str = "medium"
    tools_used: list[str] = []
    latency_ms: float = 0.0
    evidence_count: int = 0
    needs_refusal: bool = False
    model_type: str = "MockLLM"
    llm_called: bool = False
    prompt_preview: str = ""


class UploadData(BaseModel):
    filename: str
    extension: str
    content_type: str | None = None
    size_bytes: int
    ingested: bool = False
    chunk_count: int = 0
    saved_path: str = ""
    error: str = ""


class KnowledgeBaseData(BaseModel):
    name: str
    status: str
    document_count: int
    chunk_count: int = 0
    vector_count: int = 0
    vector_store_path: str | None = None
    data_path: str | None = None
    vector_store_ready: bool = False
    ingestion_enabled: bool = True
    mocked: bool = True
    documents: list[dict[str, Any]] = []


class KnowledgeBaseQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)


class KnowledgeBaseSource(BaseModel):
    source: str
    filename: str
    chunk_id: str
    score: float
    preview: str


class KnowledgeBaseQueryData(BaseModel):
    answer: str
    sources: list[KnowledgeBaseSource]
    top_k: int
    confidence: str = "medium"
    evidence_count: int = 0
    max_score: float = 0.0
    deferred_or_mocked: bool = True


class MemoryData(BaseModel):
    enabled: bool
    items: list[dict[str, Any]]
    note: str


class FeedbackRequest(BaseModel):
    target: str = Field(..., min_length=1)
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    conversation_id: str | None = None
    corrected_answer: str | None = None


class FeedbackData(BaseModel):
    feedback_id: str
    accepted: bool


class ReportRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    user_id: str | None = None
    month: str | None = None
    report_type: str = "standard"


class ReportData(BaseModel):
    report_id: str
    status: str
    deferred: bool = True
    summary: str
    content: str = ""
