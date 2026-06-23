"""Pydantic models mirroring database tables for typed data access."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentRecord:
    doc_id: str
    doc_name: str
    doc_type: str
    file_path: str | None = None
    summary: str | None = None
    upload_time: str = ""
    status: str = "pending"


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    content: str
    content_type: str = "text"
    page: int = 0
    section: str | None = None
    metadata_json: str = "{}"
    embedding_id: str | None = None
    created_at: str = ""


@dataclass
class ConversationRecord:
    conversation_id: str
    user_id: str = "anonymous"
    question: str = ""
    answer: str = ""
    used_docs_json: str = "[]"
    used_tools_json: str = "[]"
    latency_ms: int = 0
    created_at: str = ""


@dataclass
class MemoryRecord:
    memory_id: str
    memory_type: str  # user_preference, project_context, task_history, feedback_memory, tool_preference
    content: str
    importance: int = 3
    source: str | None = None
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""


@dataclass
class FeedbackRecord:
    feedback_id: str
    conversation_id: str | None = None
    feedback_type: str = "rating"
    comment: str | None = None
    corrected_answer: str | None = None
    created_at: str = ""


@dataclass
class ToolLogRecord:
    tool_call_id: str
    tool_name: str
    input_json: str = "{}"
    output_json: str = "{}"
    status: str = "success"
    latency_ms: int = 0
    created_at: str = ""


@dataclass
class ErrorCaseRecord:
    case_id: str
    question: str | None = None
    wrong_answer: str | None = None
    error_type: str = "unknown"
    correction: str | None = None
    fix_strategy: str | None = None
    created_at: str = ""
