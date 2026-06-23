"""统一知识库服务 — RAG 系统中"检索+入库+管理"的核心。

这是整个 RAG 系统最核心的模块，学习 RAG 开发重点看这里。

三层设计：
  1. 入库层：文件解析 → 文本切分 → 向量化 → 写入向量库+数据库
  2. 检索层：向量检索 → 重排序 → 关键词增强 → 证据过滤
  3. 管理层：清空、重建、去重、状态查询

关键设计决策：
  — SHA256 文件哈希去重（避免重复入库）
  — content_type 分类（text_knowledge / table_knowledge / image_knowledge）
  — CSV 只入库摘要（不把原始数据行切 chunk 污染知识库）
  — 关键词+向量混合打分（MockEmbedding 弱，关键词权重更高）
  — 领域同义词扩展（解决"电池"→"battery"的跨语言匹配问题）
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.core.settings import get_settings
from src.database.sqlite_manager import get_db, SQLiteManager
from src.rag.document_loader import LoadedDocument, load_text_documents
from src.rag.text_splitter import TextChunk, split_documents
from src.rag.embedding_service import get_embedding_service, EmbeddingProvider
from src.rag.vector_store import SimpleVectorStore
from src.rag.retriever import Retriever, RetrievalResult, Evidence
from src.rag.reranker import SimpleReranker, RerankedEvidence

logger = logging.getLogger(__name__)


# ── 数据结构 ─────────────────────────────────────────────────────

@dataclass
class IngestResult:
    """单文件入库结果。"""
    file_name: str
    file_path: str
    file_size: int
    success: bool
    skipped_duplicate: bool = False   # SHA256 去重命中
    doc_id: str = ""
    chunk_count: int = 0
    vector_count: int = 0
    content_type: str = ""
    error: str = ""
    summary: str = ""


@dataclass
class BatchIngestResult:
    """批量入库汇总。"""
    total: int
    success_count: int
    skip_count: int
    fail_count: int
    total_chunks: int
    details: list[IngestResult]


@dataclass
class KnowledgeBaseStatus:
    """知识库状态快照。"""
    document_count: int
    chunk_count: int
    vector_count: int
    vector_store_path: str
    data_path: str
    status: str                   # ready / empty
    documents: list[dict] = field(default_factory=list)


class KnowledgeBaseService:
    """统一知识库服务 — 入库 / 检索 / 管理 的唯一入口。

    三类知识：
      text_knowledge  — txt/md/pdf/docx → 参与 RAG 问答
      table_knowledge — csv/xlsx → 只生成摘要，精确分析走 TableAnalysisTool
      image_knowledge — png/jpg → 图片理解工具专用
    """

    # ── 领域同义词表（解决中文→英文的跨语言匹配问题）───────────
    # 例如：用户输入"电池"，文档中写的是"battery"
    # 同义词扩展让关键词打分能命中英文文档中的对应词汇
    DOMAIN_SYNONYMS = {
        "电池": ["电芯", "cell", "储能", "充放电", "锂电", "battery"],
        "低温": ["低温", "零下", "寒冷", "低温环境", "冬季", "subzero", "cold"],
        "风险": ["风险", "危险", "危害", "安全隐患", "故障", "失效", "爆炸", "起火",
                "risk", "danger", "hazard", "failure"],
        "温度": ["温度", "高温", "过热", "发热", "热", "temperature", "heat"],
        "电压": ["电压", "电势", "电位", "voltage", "volt"],
        "容量": ["容量", "capability", "capacity", "ah", "储能", "能量"],
        "安全": ["安全", "保护", "防护", "safety", "protection"],
        "充电": ["充电", "快充", "慢充", "放电", "charge", "discharge"],
        "BMS": ["bms", "管理系统", "电池管理", "监控", "均衡"],
    }

    def __init__(
        self,
        db: SQLiteManager | None = None,          # 依赖注入：数据库
        vector_store: SimpleVectorStore | None = None,  # 依赖注入：向量库
        embedding: EmbeddingProvider | None = None,     # 依赖注入：embedding
    ):
        self._settings = get_settings()
        self._db = db or get_db()
        self._db.initialize()
        self._embedding = embedding or get_embedding_service()
        self._vector_store = vector_store or SimpleVectorStore(
            persist_dir=self._settings.vector_db_dir,
            embedding=self._embedding,
        )
        self._retriever = Retriever(self._vector_store)          # 检索器
        self._reranker = SimpleReranker()                        # 重排序器

    # ================================================================
    #  入库（Ingestion）
    # ================================================================

    def ingest_file(self, file_path: str | Path, force: bool = False) -> IngestResult:
        """入库单个文件：去重 → 分类 → 解析 → 切分 → 向量化 → 写数据库。

        这是 RAG 知识库的"写入"路径，完整演示了文档如何变为可检索的向量。
        """
        file_path = Path(file_path)
        file_name = file_path.name
        file_size = file_path.stat().st_size if file_path.exists() else 0

        try:
            # ── Step 0: SHA256 去重 ───────────────────────────────
            file_hash = self._compute_hash(file_path)
            existing = self._db.check_file_hash(file_hash)
            if existing and not force:
                return IngestResult(
                    file_name=file_name, file_path=str(file_path),
                    file_size=file_size, success=True, skipped_duplicate=True,
                    doc_id=existing["doc_id"],
                    content_type=existing.get("content_type", ""),
                    summary=f"文件已存在，跳过重复入库 (hash: {file_hash[:8]}...)"
                )

            # ── Step 1: 内容分类 ──────────────────────────────────
            suffix = file_path.suffix.lower()
            content_type = self._classify_content(suffix)          # .csv → table_knowledge

            # ── Step 2: 文件解析 ──────────────────────────────────
            docs = self._load_file(file_path, content_type)
            if not docs:
                return IngestResult(
                    file_name=file_name, file_path=str(file_path),
                    file_size=file_size, success=False, error="文件解析后无有效内容"
                )

            # ── Step 3: 数据库记录 ────────────────────────────────
            doc_type = suffix.lstrip(".")
            doc_id = self._db.insert_document(
                doc_name=file_name, doc_type=doc_type, content_type=content_type,
                file_path=str(file_path), file_hash=file_hash, file_size=file_size,
                summary=docs[0].content[:200] if docs else "",
            )

            # ── Step 4: 文本切分 ──────────────────────────────────
            raw_chunks = split_documents(docs, self._settings.rag_chunk_size,
                                         self._settings.rag_chunk_overlap)
            all_chunks = []
            for i, chunk in enumerate(raw_chunks):
                all_chunks.append(TextChunk(
                    text=chunk.text, source=chunk.source,
                    chunk_id=f"{doc_id}-chunk{i}",               # 唯一 chunk ID
                    metadata={**chunk.metadata, "content_type": content_type},
                ))

            if not all_chunks:
                return IngestResult(
                    file_name=file_name, file_path=str(file_path),
                    file_size=file_size, success=False, doc_id=doc_id,
                    error="文本切分后无chunk"
                )

            # ── Step 5: 向量化 + 写入向量库 ──────────────────────
            contents = [chunk.text for chunk in all_chunks]
            metadatas = [{                           # 元数据关联到向量条目
                "doc_id": doc_id, "filename": file_name,
                "chunk_id": chunk.chunk_id, "source": chunk.source,
                "content_type": content_type,
                "chunk_index": chunk.metadata.get("chunk_index", 0),
            } for chunk in all_chunks]
            self._vector_store.add_documents(contents, metadatas)

            # ── Step 6: 写入 chunks 表 ────────────────────────────
            for chunk, metadata in zip(all_chunks, metadatas):
                self._db.insert_chunk(
                    doc_id=doc_id, content=chunk.text,
                    chunk_id=chunk.chunk_id,
                    metadata_json=json.dumps(metadata, ensure_ascii=False),
                )

            # ── Step 7: 标记完成 + 持久化 ─────────────────────────
            self._db.execute("UPDATE documents SET status = ? WHERE doc_id = ?",
                             ("ingested", doc_id))
            self._vector_store.persist()                            # 写入磁盘

            logger.info("Ingested %s: type=%s doc_id=%s chunks=%d",
                        file_name, content_type, doc_id, len(all_chunks))

            return IngestResult(
                file_name=file_name, file_path=str(file_path), file_size=file_size,
                success=True, doc_id=doc_id, chunk_count=len(all_chunks),
                vector_count=len(contents), content_type=content_type,
                summary=f"成功入库: {len(all_chunks)} chunks"
            )

        except Exception as e:
            logger.error("Ingest failed for %s: %s", file_name, e)
            return IngestResult(file_name=file_name, file_path=str(file_path),
                                file_size=0, success=False, error=str(e))

    def ingest_files(self, file_paths: list[str | Path], force: bool = False) -> BatchIngestResult:
        """批量入库。"""
        results = [self.ingest_file(fp, force=force) for fp in file_paths]
        return BatchIngestResult(
            total=len(results),
            success_count=sum(1 for r in results if r.success and not r.skipped_duplicate),
            skip_count=sum(1 for r in results if r.skipped_duplicate),
            fail_count=sum(1 for r in results if not r.success),
            total_chunks=sum(r.chunk_count for r in results),
            details=results,
        )

    # ================================================================
    #  检索（Retrieval）
    # ================================================================

    def retrieve_context(self, query: str, top_k: int | None = None,
                         prefer_content_type: str | None = None,
                         min_score: float = 0.10) -> dict[str, Any]:
        """轻量检索：只返回 context/sources/debug，不生成最终答案。

        这是 RAG 中"R"（Retrieval）的纯实现。
        answer 的生成留给上层的 LLMRagChain。
        """
        import time
        start = time.time()

        top_k = top_k or self._settings.rag_top_k
        threshold = min_score

        # 领域短查询自动放宽阈值
        query_keywords = self._extract_keywords(query)
        has_domain = any(kw.lower() in str(self.DOMAIN_SYNONYMS).lower() for kw in query_keywords)
        if len(query) < 30 and has_domain:
            threshold = max(0.03, threshold * 0.5)

        # ── 向量检索 ──────────────────────────────────────────────
        retrieval = self._retriever.retrieve(query, top_k=top_k * 2, threshold=0.0)

        # ── 重排序 + 关键词增强打分 ───────────────────────────────
        reranked = self._reranker.rerank(query, retrieval.evidences)
        original_kw = self._extract_raw_keywords(query)
        expanded_kw = self._extract_keywords(query)

        for r in reranked:
            cl = r.evidence.content.lower()
            orig_hits = sum(1 for kw in original_kw if kw.lower() in cl)
            orig_score = orig_hits / max(len(original_kw), 1) if original_kw else 0
            syn_hits = sum(1 for kw in expanded_kw if kw.lower() in cl
                           and kw.lower() not in [o.lower() for o in original_kw])
            syn_bonus = min(0.3, syn_hits * 0.10)
            r.reranked_score = 0.3 * r.reranked_score + 0.7 * (orig_score + syn_bonus)

        # 短查询 keyword substring fallback
        if len(reranked) == 0 and len(query.strip()) <= 8:
            fallback = self._keyword_substring_scan(query, top_k)
            if fallback:
                from src.rag.reranker import RerankedEvidence
                from src.rag.retriever import Evidence
                for item in fallback:
                    ev = Evidence(doc_id=item["doc_id"], content=item["content"],
                                  filename=item.get("filename", ""), chunk_id=item.get("chunk_id", ""),
                                  score=item["score"], metadata=item.get("metadata", {}))
                    reranked.append(RerankedEvidence(
                        evidence=ev, original_score=0, reranked_score=item["score"], keyword_overlap=1.0))

        # content_type 排序：text_knowledge 优先
        def _tp(r):
            ct = r.evidence.metadata.get("content_type") or "text_knowledge"
            return 0 if ct == "text_knowledge" else (2 if ct == "table_knowledge" else 1)

        reranked.sort(key=lambda r: (_tp(r), -r.reranked_score))

        if prefer_content_type:
            reranked = [r for r in reranked
                        if (r.evidence.metadata.get("content_type") or "text_knowledge") == prefer_content_type]

        filtered = [r for r in reranked if r.reranked_score >= threshold][:top_k]
        max_score = max((r.reranked_score for r in filtered), default=0.0)

        # ── 构建 sources 和 context ───────────────────────────────
        sources = []
        for r in filtered:
            sources.append({
                "doc_id": r.evidence.doc_id, "filename": r.evidence.filename,
                "chunk_id": r.evidence.chunk_id, "score": round(r.reranked_score, 4),
                "preview": r.evidence.preview, "content": r.evidence.content,
                "content_type": r.evidence.metadata.get("content_type", ""),
            })

        context_parts = [f"【来源{i+1}】{s['filename']}: {s['content'][:800]}" for i, s in enumerate(sources)]
        context = "\n\n".join(context_parts) if context_parts else ""

        retrieval_status = "used" if context else "empty"
        if max_score > 0 and max_score < threshold:
            retrieval_status = "low_relevance"

        return {
            "context": context, "sources": sources,
            "max_score": max_score, "evidence_count": len(sources),
            "has_relevant_context": bool(context),
            "retrieval_status": retrieval_status,
            "retrieval_debug": {
                "query": query, "keywords": self._extract_keywords(query),
                "threshold": threshold, "max_score": max_score,
                "latency_ms": round((time.time() - start) * 1000, 1),
            },
        }

    # ================================================================
    #  管理（Management）
    # ================================================================

    def get_status(self) -> KnowledgeBaseStatus:
        """获取知识库完整状态。"""
        docs = self._db.list_documents()
        chunks = self._db.list_chunks()
        seen = set()
        unique_docs = []
        for doc in docs:
            if doc["doc_id"] not in seen:
                seen.add(doc["doc_id"])
                doc["chunk_count"] = len(self._db.list_chunks(doc["doc_id"]))
                unique_docs.append(doc)
        return KnowledgeBaseStatus(
            document_count=len(unique_docs), chunk_count=len(chunks),
            vector_count=self._vector_store.document_count,
            vector_store_path=str(self._settings.vector_db_dir / "vector_index.json"),
            data_path=str(self._settings.data_dir),
            status="ready" if self._vector_store.document_count > 0 else "empty",
            documents=unique_docs,
        )

    def clear(self) -> dict[str, Any]:
        """清空知识库：删除索引文件 + 清空向量库 + 清空全部数据表。"""
        index_path = self._settings.vector_db_dir / "vector_index.json"
        if index_path.exists():
            try: index_path.unlink()
            except Exception: pass
        self._vector_store.clear()
        import sqlite3
        conn = sqlite3.connect(self._db._db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        for table in ["chunks", "documents", "conversations", "memories",
                       "feedback", "tool_logs", "error_cases"]:
            conn.execute(f"DELETE FROM {table}")
        conn.commit(); conn.close()
        return {"success": True, "message": "知识库已清空"}

    def rebuild_index(self) -> dict[str, Any]:
        """从 raw_documents 重建整个知识库索引。"""
        raw_dir = self._settings.raw_documents_dir
        if not raw_dir.exists():
            return {"success": False, "message": "raw_documents目录不存在"}
        self.clear()
        files = [f for f in raw_dir.iterdir() if f.suffix.lower() in {".txt", ".md", ".csv"} and f.is_file()]
        if not files:
            return {"success": True, "message": "无支持文档", "ingested": 0}
        result = self.ingest_files(files)
        return {"success": True,
                "message": f"重建完成: {result.success_count}新 + {result.skip_count}跳过, {result.total_chunks} chunks"}

    # ── 兼容旧 API：query() 委托给 retrieve_context ──────────────

    def query(self, question: str, top_k: int | None = None,
              prefer_content_type: str | None = None) -> dict[str, Any]:
        """兼容旧版 API：内部调用 retrieve_context + 构建简易回答。"""
        r = self.retrieve_context(question, top_k, prefer_content_type)
        confidence = "high" if r["max_score"] >= 0.20 else ("medium" if r["max_score"] >= 0.10 else "low")
        answer = (f"检索到{r['evidence_count']}条资料，最高分{r['max_score']:.4f}。"
                  if r["has_relevant_context"]
                  else "未找到足够相关证据。")
        r["answer"] = answer
        r["confidence"] = confidence
        r["llm_called"] = False
        r["llm_provider"] = "N/A"
        r["real_llm_called"] = False
        r["real_llm_success"] = False
        r["prompt_preview"] = ""
        return r

    def delete_document(self, doc_id: str) -> bool:
        """删除单个文档及其全部 chunks。"""
        if not self._db.get_document(doc_id):
            return False
        self._db.delete_document(doc_id)
        self._vector_store.delete(doc_id); self._vector_store.persist()
        return True

    # ================================================================
    #  辅助方法
    # ================================================================

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """SHA256 文件哈希（去重）。"""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _classify_content(suffix: str) -> str:
        """按扩展名分类内容类型。"""
        if suffix in (".txt", ".md", ".pdf", ".docx"): return "text_knowledge"
        elif suffix in (".csv", ".xlsx", ".xls"): return "table_knowledge"
        elif suffix in (".png", ".jpg", ".jpeg"): return "image_knowledge"
        return "text_knowledge"

    @staticmethod
    def _extract_raw_keywords(text: str) -> list[str]:
        """提取原始关键词（不含同义词扩展）。"""
        tokens = []
        tokens.extend(re.findall(r'[a-zA-Z0-9]{2,}', text.lower()))
        for block in re.findall(r'[一-鿿]{2,}', text):
            for n in [2, 3]:
                for i in range(len(block) - n + 1):
                    tokens.append(block[i:i+n])
        seen = set()
        return [t for t in tokens if not (t in seen or seen.add(t))]

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """提取关键词（含领域同义词扩展）。"""
        raw = KnowledgeBaseService._extract_raw_keywords(text)
        return KnowledgeBaseService._expand_keywords(raw)

    @staticmethod
    def _expand_keywords(keywords: list[str]) -> list[str]:
        """根据领域词表扩展同义词（只加分，不进分母）。"""
        expanded = list(keywords)
        for kw in keywords:
            for domain_word, synonyms in KnowledgeBaseService.DOMAIN_SYNONYMS.items():
                if kw.lower() == domain_word.lower() or kw.lower() in [s.lower() for s in synonyms]:
                    for syn in synonyms:
                        if syn.lower() not in [e.lower() for e in expanded]:
                            expanded.append(syn)
        return expanded

    def _keyword_substring_scan(self, query: str, top_k: int) -> list[dict]:
        """短查询 fallback：直接扫描向量库文本做子串匹配。"""
        results = []
        query_lower = query.lower()
        search_terms = [query_lower]
        for ch in re.findall(r'[\w一-鿿]+', query_lower):
            search_terms.append(ch)
        for ch in re.findall(r'[\w一-鿿]{2,}', query_lower):
            search_terms.append(ch)
        for doc in self._vector_store._documents:
            hits = sum(1 for term in search_terms if term in doc.content.lower())
            if hits > 0:
                score = min(0.50, 0.10 + hits * 0.05)
                results.append({
                    "doc_id": doc.doc_id, "content": doc.content,
                    "filename": doc.metadata.get("filename", ""),
                    "chunk_id": doc.metadata.get("chunk_id", doc.doc_id),
                    "score": round(score, 4), "metadata": doc.metadata,
                })
        results.sort(key=lambda r: -r["score"])
        return results[:top_k]

    def _load_file(self, file_path: Path, content_type: str = "text_knowledge") -> list[LoadedDocument]:
        """按文件类型加载文档内容。"""
        suffix = file_path.suffix.lower()
        if suffix in (".txt", ".md"):
            content = None
            for enc in ["utf-8", "utf-8-sig", "gbk", "gb2312"]:
                try:
                    content = file_path.read_text(encoding=enc)
                    if content.strip(): break
                except (UnicodeDecodeError, UnicodeError): continue
            if content is None:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            if not content.strip(): return []
            return [LoadedDocument(content=content, source=str(file_path),
                    metadata={"filename": file_path.name, "extension": suffix,
                              "size_bytes": file_path.stat().st_size, "content_type": content_type})]
        elif suffix == ".csv":
            summary = self._csv_to_summary(file_path)
            if not summary: return []
            return [LoadedDocument(content=summary, source=str(file_path),
                    metadata={"filename": file_path.name, "extension": suffix,
                              "size_bytes": file_path.stat().st_size, "content_type": "table_knowledge"})]
        else:
            docs = load_text_documents(file_path.parent, (suffix.lstrip("."),))
            return [d for d in docs if Path(d.source) == file_path]

    def _csv_to_summary(self, file_path: Path) -> str:
        """CSV → 结构化摘要（不包含原始数据行，避免污染知识库）。"""
        import csv
        for encoding in ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    rows = list(csv.DictReader(f))
                if not rows: continue
                columns = list(rows[0].keys())
                numeric_stats = {}
                for col in columns:
                    vals = []
                    for row in rows:
                        try: vals.append(float(row[col]))
                        except (ValueError, TypeError): pass
                    if len(vals) > len(rows) * 0.5:
                        numeric_stats[col] = {"min": min(vals), "max": max(vals),
                                              "mean": round(sum(vals) / len(vals), 2)}
                lines = [f"[TABLE SUMMARY] {file_path.name}",
                         f"Columns ({len(columns)}): {', '.join(columns)}", f"Rows: {len(rows)}"]
                if numeric_stats:
                    lines.append("Numeric stats:")
                    for col, s in numeric_stats.items():
                        lines.append(f"  {col}: min={s['min']}, max={s['max']}, mean={s['mean']}")
                return "\n".join(lines)
            except (UnicodeDecodeError, Exception): continue
        return f"[TABLE SUMMARY] {file_path.name}"


# ── 全局单例 ─────────────────────────────────────────────────────

_kb_service: KnowledgeBaseService | None = None


def get_kb_service() -> KnowledgeBaseService:
    global _kb_service
    if _kb_service is None:
        _kb_service = KnowledgeBaseService()
    return _kb_service


def reset_kb_service() -> KnowledgeBaseService:
    """重置单例（测试或重建索引后使用）。"""
    global _kb_service
    _kb_service = KnowledgeBaseService()
    return _kb_service
