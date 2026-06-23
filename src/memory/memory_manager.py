"""Memory Manager — 长期记忆统一入口：抽取 → 存储 → 检索 → 管理（M3核心）。"""

from __future__ import annotations

import logging
from typing import Any

from src.memory.memory_store import MemoryItem, MemoryStore
from src.memory.memory_extractor import MemoryCandidate, MemoryExtractor
from src.memory.memory_retriever import MemoryRetriever

logger = logging.getLogger(__name__)


class MemoryManager:
    """长期记忆管理统一入口，协调存储、抽取、检索三个子模块。

    规则:
    - 只有 importance ≥ 3 的信息才入库（避免噪音）
    - 支持禁用但不自动删除
    - 检索采用关键词匹配 + 重要性排序
    """

    def __init__(
        self,
        store: MemoryStore | None = None,
        extractor: MemoryExtractor | None = None,
        retriever: MemoryRetriever | None = None,
    ):
        self._store = store or MemoryStore()                         # SQLite持久化存储
        self._extractor = extractor or MemoryExtractor()             # 关键词触发的记忆抽取
        self._retriever = retriever or MemoryRetriever(self._store)  # 记忆检索器

    # === 写入 ===

    def process_conversation(self, question: str, answer: str,
                             conversation_id: str = "") -> list[str]:
        """处理一轮对话：抽取候选记忆 → 过滤低重要性 → 保存。"""
        candidates = self._extractor.extract_candidates(question, answer, conversation_id)
        saved_ids = []
        for candidate in candidates:
            if candidate.importance >= 3:                            # 重要性阈值过滤
                mid = self._store.save(
                    memory_type=candidate.memory_type,
                    content=candidate.content,
                    importance=candidate.importance,
                    source=candidate.source,
                )
                saved_ids.append(mid)
        logger.info("Processed conversation: %d candidates, %d saved",
                     len(candidates), len(saved_ids))
        return saved_ids

    def add_manual_memory(self, memory_type: str, content: str,
                          importance: int = 4, source: str | None = None) -> str:
        """手动添加一条记忆（如用户明确表示'记住这个'）。"""
        return self._store.save(memory_type, content, importance, source)

    # === 读取 ===

    def get_context_for_query(self, query: str) -> dict[str, Any]:
        """获取与当前查询相关的所有记忆上下文。"""
        memories = self._retriever.retrieve_for_query(query)
        preferences = self._retriever.get_user_preferences()
        project = self._retriever.get_project_context()

        return {
            "relevant_memories": [m.to_dict() for m in memories],    # 关键词匹配的记忆
            "user_preferences": [m.to_dict() for m in preferences],  # 用户偏好记忆
            "project_context": [m.to_dict() for m in project],       # 项目背景记忆
            "total_relevant": len(memories),
        }

    def list_memories(self, memory_type: str | None = None) -> list[dict]:
        """列出所有启用的记忆（可按类型过滤）。"""
        items = self._store.list(memory_type, enabled_only=True)
        return [m.to_dict() for m in items]

    def get_memory(self, memory_id: str) -> dict | None:
        """获取单条记忆。"""
        item = self._store.get(memory_id)
        return item.to_dict() if item else None

    # === 管理 ===

    def disable_memory(self, memory_id: str) -> bool:
        """禁用记忆（软删除，可恢复）。"""
        return self._store.disable(memory_id)

    def delete_memory(self, memory_id: str) -> bool:
        """永久删除记忆。"""
        return self._store.delete(memory_id)


# ---- 全局单例 ----

_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """获取MemoryManager全局单例。"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
