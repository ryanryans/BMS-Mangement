"""Upload endpoint — 批量上传文件并完整入库到知识库（通过统一的KnowledgeBaseService）。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.api.responses import success_response
from src.api.schemas import ApiResponse, UploadData
from src.core.settings import get_settings
from src.rag.knowledge_base_service import get_kb_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])

ALLOWED_UPLOAD_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".csv", ".xlsx", ".png", ".jpg", ".jpeg",
}


@router.post("/upload", response_model=ApiResponse)
async def upload(file: UploadFile = File(...)) -> dict:
    """上传单个文件并自动入库。"""
    settings = get_settings()
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{extension}'. Allowed: {allowed}.",
        )

    content = await file.read()

    # 保存到 raw_documents
    dest = settings.raw_documents_dir / filename
    dest.write_bytes(content)

    # 使用统一知识库服务入库
    kb = get_kb_service()
    result = kb.ingest_file(dest)

    data = UploadData(
        filename=filename,
        extension=extension,
        content_type=file.content_type,
        size_bytes=len(content),
        ingested=result.success,
        chunk_count=result.chunk_count,
        saved_path=str(dest),
        error=result.error if not result.success else "",
    )

    if result.success:
        return success_response(
            f"文件 '{filename}' 上传并入库成功: {result.chunk_count} chunks",
            data.model_dump(),
        )
    else:
        return success_response(
            f"文件 '{filename}' 已保存但入库失败: {result.error}",
            data.model_dump(),
        )
