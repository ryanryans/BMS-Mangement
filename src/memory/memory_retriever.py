"""Memory Retriever — 根据查询检索相关的长期记忆（M3检索层）。"""

from __future__ import annotations

import logging

from src.memory.memory_store import MemoryItem, MemoryStore

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """检索与当前查询相关的长期记忆。

    检索策略:
    - 关键词匹配（content LIKE %query%）
    - 按重要性降序排列
    - 支持按类型过滤
    """

    def __init__(self, store: MemoryStore | None = None):
        self._store = store or MemoryStore()

    def retrieve_for_query(self, query: str, limit: int = 5) -> list[MemoryItem]:
        """获取与查询相关的记忆（跨类型关键词搜索）。"""
        results = self._store.search(query, limit=limit)

        logger.info(
            "Memory retrieval: query='%s' found=%d",
            query[:80], len(results),
        )
        return results

    def get_user_preferences(self) -> list[MemoryItem]:
        """获取所有启用的用户偏好。"""
        return self._store.list("user_preference", enabled_only=True)

    def get_project_context(self) -> list[MemoryItem]:
        """获取所有启用的项目背景。"""
        return self._store.list("project_context", enabled_only=True)

    def get_task_history(self, limit: int = 10) -> list[MemoryItem]:
        """获取最近的任务历史。"""
        items = self._store.list("task_history", enabled_only=True)
        return items[:limit]
