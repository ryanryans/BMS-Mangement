"""Memory Store — 基于SQLite的长期记忆持久化存储（M3数据层）。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from src.database.sqlite_manager import get_db

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """一条长期记忆。"""
    memory_id: str           # 记忆唯一ID
    memory_type: str         # 类型: user_preference/project_context/task_history/feedback_memory/tool_preference
    content: str             # 记忆内容
    importance: int = 3      # 重要性 1-5（5最高）
    source: str | None = None  # 来源对话ID
    enabled: bool = True     # 是否启用
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "memory_type": self.memory_type,
            "content": self.content,
            "importance": self.importance,
            "source": self.source,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class MemoryStore:
    """SQLite 记忆存储，提供 CRUD + 关键词搜索。

    5种记忆类型:
    - user_preference:  用户偏好（"喜欢简短回答"）
    - project_context:  项目背景（"BMS项目使用三元锂电池"）
    - task_history:     任务历史（"上周完成了循环测试"）
    - feedback_memory:  反馈记忆（"用户对温度分析满意"）
    - tool_preference:  工具偏好（"优先使用表格分析"）
    """

    VALID_TYPES = {
        "user_preference",
        "project_context",
        "task_history",
        "feedback_memory",
        "tool_preference",
    }

    def save(self, memory_type: str, content: str,
             importance: int = 3, source: str | None = None) -> str:
        """保存记忆，返回记忆ID。"""
        if memory_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid memory_type: {memory_type}. Must be one of {self.VALID_TYPES}")

        db = get_db()
        mid = db.save_memory(memory_type, content, importance, source)
        logger.info("Memory saved: type=%s id=%s importance=%d", memory_type, mid, importance)
        return mid

    def list(self, memory_type: str | None = None,
             enabled_only: bool = True) -> list[MemoryItem]:
        """列出记忆，可按类型过滤 + 只显示启用的。"""
        db = get_db()
        rows = db.list_memories(memory_type, enabled_only)
        return [MemoryItem(
            memory_id=r["memory_id"],
            memory_type=r["memory_type"],
            content=r["content"],
            importance=r.get("importance", 3),
            source=r.get("source"),
            enabled=bool(r.get("enabled", 1)),
            created_at=r.get("created_at", ""),
            updated_at=r.get("updated_at", ""),
        ) for r in rows]

    def get(self, memory_id: str) -> MemoryItem | None:
        """根据ID获取单条记忆。"""
        db = get_db()
        row = db.fetch_one("SELECT * FROM memories WHERE memory_id = ?", (memory_id,))
        if not row:
            return None
        return MemoryItem(
            memory_id=row["memory_id"],
            memory_type=row["memory_type"],
            content=row["content"],
            importance=row.get("importance", 3),
            source=row.get("source"),
            enabled=bool(row.get("enabled", 1)),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    def disable(self, memory_id: str) -> bool:
        """禁用记忆（软删除，不清除数据）。"""
        db = get_db()
        result = db.disable_memory(memory_id)
        if result:
            logger.info("Memory disabled: %s", memory_id)
        return result

    def delete(self, memory_id: str) -> bool:
        """永久删除记忆。"""
        db = get_db()
        result = db.delete_memory(memory_id)
        if result:
            logger.info("Memory deleted: %s", memory_id)
        return result

    def search(self, query: str, memory_type: str | None = None,
               limit: int = 10) -> list[MemoryItem]:
        """关键词搜索记忆（简单的 content LIKE %query%）。"""
        items = self.list(memory_type, enabled_only=True)
        query_lower = query.lower()
        matched = []
        for item in items:
            if query_lower in item.content.lower():
                matched.append(item)
        matched.sort(key=lambda m: -m.importance)                    # 重要性高的排在前面
        return matched[:limit]
