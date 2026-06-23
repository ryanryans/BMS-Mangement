"""Retriever — RAG 中"R"的核心组件。

功能：把用户查询转化为向量，从向量库中找到最相似的文档片段。

数据流：
  query → embedding → 向量库搜索 → SearchResult 列表 → Evidence 列表

Evidence vs SearchResult：
  — SearchResult 是向量库的原始输出（通用、低层）
  — Evidence 是经过元数据映射后的结构化输出（语义明确、上层使用）
  — Retriever 的职责就是完成这个映射
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.core.settings import get_settings
from src.rag.vector_store import SearchResult, SimpleVectorStore

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """一条检索证据 —— RAG 后续步骤（重排序、LLM）的标准输入。"""
    doc_id: str          # 文档唯一ID
    content: str         # 文本内容（完整）
    filename: str        # 来源文件名
    chunk_id: str        # 文本块ID
    score: float         # 相似度分数
    preview: str = ""    # 前 200 字预览
    metadata: dict = field(default_factory=dict)  # 附加元数据（content_type 等）

    def __post_init__(self):
        if not self.preview:
            self.preview = self.content[:200]


@dataclass
class RetrievalResult:
    """一次检索的完整结果。"""
    query: str
    evidences: list[Evidence] = field(default_factory=list)
    top_k: int = 5
    total_found: int = 0
    max_score: float = 0.0

    @property
    def has_evidence(self) -> bool:
        return len(self.evidences) > 0

    @property
    def is_strong(self) -> bool:
        """证据是否强（max_score ≥ 0.15）。"""
        return self.max_score >= 0.15


class Retriever:
    """检索器 —— 把向量库的 SearchResult 映射为结构化的 Evidence。

    设计要点：
    — 封装 SimpleVectorStore，不暴露底层实现细节
    — 元数据映射：确保 filename/chunk_id/content_type 等字段统一
    — 支持依赖注入：可以传入自定义 VectorStore（方便测试）
    """

    def __init__(self, vector_store: SimpleVectorStore | None = None):
        self._store = vector_store or SimpleVectorStore()
        self._settings = get_settings()

    @property
    def store(self) -> SimpleVectorStore:
        """暴露底层向量库（供入库操作）。"""
        return self._store

    def retrieve(self, query: str, top_k: int | None = None,
                 threshold: float | None = None) -> RetrievalResult:
        """执行检索，返回标准化的 Evidence 列表。

        注意：threshold=None 时使用 is None 检查而非 'or'，
        因为 threshold=0.0 是合法值（不过滤任何结果）。
        """
        top_k = self._settings.rag_top_k if top_k is None else top_k
        threshold = self._settings.rag_similarity_threshold if threshold is None else threshold

        results = self._store.search(query, top_k=top_k, threshold=threshold)

        # SearchResult → Evidence（元数据映射）
        evidences = []
        for r in results:
            evidences.append(Evidence(
                doc_id=r.doc_id, content=r.content,
                filename=r.metadata.get("filename", r.metadata.get("doc_name", "unknown")),
                chunk_id=r.metadata.get("chunk_id", r.doc_id),
                score=round(r.score, 4),
                metadata=r.metadata,                               # 透传 content_type 等
            ))

        max_score = max((e.score for e in evidences), default=0.0)

        logger.info("Retrieval: query='%s' top_k=%d found=%d max_score=%.4f",
                     query[:80], top_k, len(evidences), max_score)

        return RetrievalResult(query=query, evidences=evidences,
                               top_k=top_k, total_found=len(evidences), max_score=max_score)

    def add_document(self, content: str, metadata: dict | None = None,
                     doc_id: str | None = None) -> str:
        """快捷方法：向底层向量库添加文档。"""
        return self._store.add_document(content, metadata, doc_id)

    def add_documents(self, contents: list[str], metadatas: list[dict] | None = None) -> list[str]:
        """快捷方法：批量添加。"""
        return self._store.add_documents(contents, metadatas)

    def persist(self) -> None:
        """快捷方法：持久化。"""
        self._store.persist()
