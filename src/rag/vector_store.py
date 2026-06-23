"""向量存储 — RAG 中"V"（Vector Store）的实现。

提供两种向量库：
  SimpleVectorStore — 本地 JSON 持久化 + cosine 相似度检索（零依赖）
  LocalVectorStore  — 词袋 + cosine 相似度（更轻量，向后兼容）

学习要点：
  1. 向量库的核心操作：add / search / persist / load
  2. Cosine 相似度公式：dot(a,b) / (||a|| * ||b||)
  3. JSON 持久化：把内存向量列表序列化到磁盘
  4. SearchResult 封装：doc_id + content + metadata + score
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.settings import get_settings
from src.rag.embedding_service import EmbeddingProvider, get_embedding_service


@dataclass
class VectorDocument:
    """向量库中的一条文档。"""
    doc_id: str
    content: str
    metadata: dict[str, Any]
    embedding: list[float] | None = None      # 预计算的向量（支持懒加载）


@dataclass
class SearchResult:
    """一次相似度搜索的结果。"""
    doc_id: str
    content: str
    metadata: dict[str, Any]
    score: float                                 # cosine 相似度分数


class SimpleVectorStore:
    """本地向量存储 — JSON 持久化 + cosine 相似度检索。

    不需要 ChromaDB、FAISS、Milvus 等外部依赖。
    开发阶段够用，生产可替换为专业向量数据库。
    """

    def __init__(
        self,
        persist_dir: Path | None = None,
        embedding: EmbeddingProvider | None = None,
    ):
        settings = get_settings()
        self._persist_dir = persist_dir or settings.vector_db_dir
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._embedding = embedding or get_embedding_service()
        self._documents: list[VectorDocument] = []
        self._index_path = self._persist_dir / "vector_index.json"
        self._load()                               # 启动时从磁盘加载已有向量

    @property
    def document_count(self) -> int:
        return len(self._documents)

    # ── 写入 ──────────────────────────────────────────────────────

    def add_document(self, content: str, metadata: dict[str, Any] | None = None,
                     doc_id: str | None = None) -> str:
        """添加单条文档：文本 → embedding → 存入内存。"""
        doc_id = doc_id or f"vec-{uuid.uuid4().hex[:12]}"
        embedding = self._embedding.encode(content)
        self._documents.append(VectorDocument(
            doc_id=doc_id, content=content,
            metadata=metadata or {}, embedding=embedding,
        ))
        return doc_id

    def add_documents(self, contents: list[str],
                      metadatas: list[dict] | None = None) -> list[str]:
        """批量添加文档。"""
        ids = []
        for i, content in enumerate(contents):
            meta = metadatas[i] if metadatas else {}
            ids.append(self.add_document(content, meta))
        return ids

    # ── 检索 ──────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5,
               threshold: float = 0.0) -> list[SearchResult]:
        """相似度检索：query → embedding → cosine 相似度 → top_k。

        时间复杂度 O(n)，n 为文档总数。万级文档以内可用。
        超过十万建议换 ChromaDB / FAISS。
        """
        if not self._documents:
            return []

        query_vec = self._embedding.encode(query)
        results: list[SearchResult] = []

        for doc in self._documents:
            if doc.embedding is None:                  # 懒加载：首次使用才计算
                doc.embedding = self._embedding.encode(doc.content)
            score = self._cosine_similarity(query_vec, doc.embedding)
            if score >= threshold:
                results.append(SearchResult(
                    doc_id=doc.doc_id, content=doc.content,
                    metadata=doc.metadata, score=score,
                ))

        results.sort(key=lambda r: (-r.score, r.doc_id))
        return results[:top_k]

    # ── 管理 ──────────────────────────────────────────────────────

    def delete(self, doc_id: str) -> bool:
        """按 ID 删除文档。"""
        for i, doc in enumerate(self._documents):
            if doc.doc_id == doc_id:
                self._documents.pop(i)
                return True
        return False

    def clear(self) -> None:
        """清空全部文档。"""
        self._documents.clear()

    # ── 持久化 ────────────────────────────────────────────────────

    def persist(self) -> None:
        """将内存中的向量序列化到 JSON 文件。"""
        data = {"documents": [{
            "doc_id": d.doc_id, "content": d.content,
            "metadata": d.metadata, "embedding": d.embedding,
        } for d in self._documents]}
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """从 JSON 文件反序列化到内存。"""
        if not self._index_path.exists():
            return
        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._documents = [VectorDocument(
                doc_id=d["doc_id"], content=d["content"],
                metadata=d.get("metadata", {}), embedding=d.get("embedding"),
            ) for d in data.get("documents", [])]
        except (json.JSONDecodeError, KeyError):
            self._documents = []

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """余弦相似度：cos(θ) = (A·B) / (||A|| * ||B||)。

        取值范围 [-1, 1]，0 表示完全不相关，1 表示完全相同。
        """
        if len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))      # 点积
        n1 = math.sqrt(sum(a * a for a in vec1))           # L2 范数
        n2 = math.sqrt(sum(b * b for b in vec2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)


# ── 向后兼容的 LocalVectorStore（词袋模型）────────────────────────

from src.rag.text_splitter import TextChunk
from collections import Counter
import re as _re

TOKEN_PATTERN = _re.compile(r"[\w一-鿿]+", _re.UNICODE)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: TextChunk
    score: float


class LocalVectorStore:
    """词袋 + cosine 相似度（最简向量库，零依赖）。"""

    def __init__(self, chunks: list[TextChunk]) -> None:
        self._chunks = chunks
        self._vectors = [_vectorize(c.text) for c in chunks]

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        q_vec = _vectorize(query)
        scored = [RetrievedChunk(chunk=c, score=_cosine_score(q_vec, v))
                  for c, v in zip(self._chunks, self._vectors)]
        scored.sort(key=lambda x: (-x.score, x.chunk.source, x.chunk.chunk_id))
        return [s for s in scored[:max(top_k, 0)] if s.score > 0]


def _vectorize(text: str) -> Counter[str]:
    """文本 → 词频向量。"""
    tokens = [t.lower() for t in TOKEN_PATTERN.findall(text)]
    if len(tokens) <= 1 and text:
        tokens = [c for c in text.lower() if not c.isspace()]
    return Counter(tokens)


def _cosine_score(left: Counter[str], right: Counter[str]) -> float:
    """词袋余弦相似度。"""
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    dot = sum(left[t] * right[t] for t in common)
    ln = math.sqrt(sum(v * v for v in left.values()))
    rn = math.sqrt(sum(v * v for v in right.values()))
    if ln == 0 or rn == 0:
        return 0.0
    return dot / (ln * rn)
