"""Knowledge base endpoints — 状态查询 / 检索 / 删除 / 清空 / 重建（统一入口）。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.api.responses import success_response
from src.api.schemas import (
    ApiResponse,
    KnowledgeBaseData,
    KnowledgeBaseQueryData,
    KnowledgeBaseQueryRequest,
    KnowledgeBaseSource,
)
from src.rag.knowledge_base_service import get_kb_service, reset_kb_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["knowledge_base"])


@router.get("/knowledge_base", response_model=ApiResponse)
def knowledge_base_status() -> dict:
    """获取知识库完整状态（文档数/chunk数/向量数/文档列表）。"""
    kb = get_kb_service()
    status = kb.get_status()
    data = KnowledgeBaseData(
        name="enterprise_kb",
        status=status.status,
        document_count=status.document_count,
        chunk_count=status.chunk_count,
        vector_store_path=status.vector_store_path,
        data_path=status.data_path,
        vector_store_ready=status.status == "ready",
        ingestion_enabled=True,
        mocked=True,
        vector_count=status.vector_count,
        documents=status.documents,
    )
    return success_response("Knowledge base status retrieved.", data.model_dump())


@router.post("/knowledge_base/query", response_model=ApiResponse)
def query_knowledge_base(request: KnowledgeBaseQueryRequest) -> dict:
    """检索知识库。"""
    kb = get_kb_service()
    result = kb.query(request.query, request.top_k)

    data = KnowledgeBaseQueryData(
        answer=result["answer"],
        sources=[
            KnowledgeBaseSource(
                source=s.get("filename", ""),
                filename=s.get("filename", ""),
                chunk_id=s.get("chunk_id", ""),
                score=s.get("score", 0.0),
                preview=s.get("preview", ""),
            )
            for s in result["sources"]
        ],
        top_k=request.top_k or 5,
        confidence=result["confidence"],
        evidence_count=result["evidence_count"],
        max_score=result["max_score"],
        deferred_or_mocked=True,
    )
    return success_response("Knowledge base query completed.", data.model_dump())


@router.delete("/knowledge_base/{doc_id}", response_model=ApiResponse)
def delete_document(doc_id: str) -> dict:
    """删除单个文档。"""
    kb = get_kb_service()
    doc = kb._db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    kb._db.delete_document(doc_id)
    # 同时从向量库中删除
    kb._vector_store.delete(doc_id)
    kb._vector_store.persist()
    return success_response(f"Document '{doc_id}' deleted.")


@router.delete("/knowledge_base", response_model=ApiResponse)
def clear_knowledge_base() -> dict:
    """清空整个知识库（删除所有文档/chunk/向量）。"""
    kb = get_kb_service()
    result = kb.clear()
    # 重置全局单例以确保后续操作使用全新状态
    reset_kb_service()
    return success_response(result["message"], result)


@router.post("/knowledge_base/rebuild", response_model=ApiResponse)
def rebuild_knowledge_base() -> dict:
    """从 raw_documents 重建知识库索引。"""
    reset_kb_service()  # 重置单例
    kb = get_kb_service()
    result = kb.rebuild_index()
    return success_response(result["message"], result)
