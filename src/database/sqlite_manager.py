"""SQLite 数据库管理器 — Agent 系统的持久化层。

学习要点：
  1. 连接管理：每个操作创建独立连接，用完即关（with 语句）
  2. WAL 模式：Write-Ahead Logging，允许并发读写
  3. 外键约束：PRAGMA foreign_keys=ON，保证数据一致性
  4. Row Factory：sqlite3.Row 让查询结果可以用列名访问
  5. 单例模式：get_db() 确保全局只有一个管理器实例
"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

from src.core.settings import get_settings

# 加载建表 SQL（从 schema.sql 文件读取）
SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


class SQLiteManager:
    """SQLite 数据库管理器 — 封装连接、建表、CRUD 操作。"""

    def __init__(self, db_path: str | None = None):
        settings = get_settings()
        self._db_path = db_path or settings.sqlite_db_path       # 可注入路径（测试用）
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接（每次调用都是新连接）。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row                           # 让查询结果支持 dict 访问
        conn.execute("PRAGMA journal_mode=WAL")                  # WAL 模式：更快、支持并发
        conn.execute("PRAGMA foreign_keys=ON")                   # 启用外键约束
        return conn

    def initialize(self) -> None:
        """初始化数据库：执行 schema.sql 建表。幂等操作（IF NOT EXISTS）。"""
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
                ("m0_full_schema",),
            )
            conn.commit()

    # ── 通用 SQL 操作 ─────────────────────────────────────────────

    def execute(self, sql: str, params: tuple | dict | None = None) -> sqlite3.Cursor:
        """执行 SQL 语句（INSERT/UPDATE/DELETE），自动提交。"""
        with self._connect() as conn:
            cursor = conn.execute(sql, params or ())
            conn.commit()
            return cursor

    def fetch_all(self, sql: str, params: tuple | dict | None = None) -> list[dict]:
        """查询多行，返回 dict 列表。"""
        with self._connect() as conn:
            rows = conn.execute(sql, params or ()).fetchall()
            return [dict(row) for row in rows]

    def fetch_one(self, sql: str, params: tuple | dict | None = None) -> dict | None:
        """查询单行，返回 dict 或 None。"""
        with self._connect() as conn:
            row = conn.execute(sql, params or ()).fetchone()
            return dict(row) if row else None

    # ── 文档操作 ──────────────────────────────────────────────────

    def check_file_hash(self, file_hash: str) -> dict | None:
        """检查文件 SHA256 是否已入库（用于去重）。"""
        return self.fetch_one(
            "SELECT * FROM documents WHERE file_hash = ? AND status = 'ingested'",
            (file_hash,),
        )

    def insert_document(self, doc_name: str, doc_type: str,
                        file_path: str | None = None, summary: str | None = None,
                        file_hash: str | None = None, file_size: int = 0,
                        content_type: str = "text_knowledge") -> str:
        """插入文档记录，返回生成的 doc_id。"""
        doc_id = f"doc-{uuid.uuid4().hex[:12]}"                    # 12位随机ID
        self.execute(
            "INSERT INTO documents(doc_id, doc_name, doc_type, content_type, "
            "file_path, file_hash, file_size, summary) VALUES(?,?,?,?,?,?,?,?)",
            (doc_id, doc_name, doc_type, content_type, file_path, file_hash, file_size, summary),
        )
        return doc_id

    def list_documents(self) -> list[dict]:
        """列出所有文档，按上传时间倒序。"""
        return self.fetch_all("SELECT * FROM documents ORDER BY upload_time DESC")

    def get_document(self, doc_id: str) -> dict | None:
        """查询单个文档。"""
        return self.fetch_one("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))

    def delete_document(self, doc_id: str) -> bool:
        """删除文档及关联的 chunks（外键 CASCADE 由应用层处理）。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            cursor = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ── Chunk 操作 ────────────────────────────────────────────────

    def insert_chunk(self, doc_id: str, content: str, chunk_id: str | None = None,
                     metadata_json: str = "{}") -> str:
        """插入一个文本块。"""
        cid = chunk_id or f"chunk-{uuid.uuid4().hex[:12]}"
        self.execute(
            "INSERT INTO chunks(chunk_id, doc_id, content, metadata_json) VALUES(?,?,?,?)",
            (cid, doc_id, content, metadata_json),
        )
        return cid

    def list_chunks(self, doc_id: str | None = None) -> list[dict]:
        """列出 chunk（可按文档过滤）。"""
        if doc_id:
            return self.fetch_all("SELECT * FROM chunks WHERE doc_id = ?", (doc_id,))
        return self.fetch_all("SELECT * FROM chunks ORDER BY created_at DESC")

    # ── 对话记录 ──────────────────────────────────────────────────

    def save_conversation(self, question: str, answer: str,
                          conversation_id: str | None = None,
                          used_docs_json: str = "[]",
                          used_tools_json: str = "[]",
                          latency_ms: int = 0) -> str:
        """保存一轮对话记录。"""
        cid = conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
        self.execute(
            "INSERT INTO conversations(conversation_id, question, answer, "
            "used_docs_json, used_tools_json, latency_ms) VALUES(?,?,?,?,?,?)",
            (cid, question, answer, used_docs_json, used_tools_json, latency_ms),
        )
        return cid

    def list_conversations(self, limit: int = 50) -> list[dict]:
        """列出最近对话。"""
        return self.fetch_all("SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?", (limit,))

    # ── 记忆操作 ──────────────────────────────────────────────────

    def save_memory(self, memory_type: str, content: str,
                    importance: int = 3, source: str | None = None) -> str:
        """保存一条长期记忆。importance 1-5，3是默认。"""
        mid = f"mem-{uuid.uuid4().hex[:12]}"
        self.execute(
            "INSERT INTO memories(memory_id, memory_type, content, importance, source) "
            "VALUES(?,?,?,?,?)",
            (mid, memory_type, content, importance, source),
        )
        return mid

    def list_memories(self, memory_type: str | None = None, enabled_only: bool = True) -> list[dict]:
        """列出记忆（可按类型过滤、只看启用的）。"""
        if memory_type:
            return self.fetch_all(
                "SELECT * FROM memories WHERE memory_type = ? AND enabled = ? "
                "ORDER BY created_at DESC",
                (memory_type, 1 if enabled_only else 0),
            )
        sql = "SELECT * FROM memories"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY created_at DESC"
        return self.fetch_all(sql)

    def disable_memory(self, memory_id: str) -> bool:
        """禁用记忆（软删除，不物理删除）。"""
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE memories SET enabled = 0, updated_at = CURRENT_TIMESTAMP "
                "WHERE memory_id = ?", (memory_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_memory(self, memory_id: str) -> bool:
        """物理删除记忆。"""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ── 反馈操作 ──────────────────────────────────────────────────

    def save_feedback(self, conversation_id: str | None, feedback_type: str,
                      comment: str | None = None, corrected_answer: str | None = None) -> str:
        """保存用户反馈。"""
        fid = f"feedback-{uuid.uuid4().hex[:12]}"
        self.execute(
            "INSERT INTO feedback(feedback_id, conversation_id, feedback_type, "
            "comment, corrected_answer) VALUES(?,?,?,?,?)",
            (fid, conversation_id, feedback_type, comment, corrected_answer),
        )
        return fid

    def list_feedback(self, limit: int = 50) -> list[dict]:
        return self.fetch_all("SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,))

    # ── 工具调用日志 ──────────────────────────────────────────────

    def log_tool_call(self, tool_name: str, input_json: str = "{}",
                      output_json: str = "{}", status: str = "success",
                      latency_ms: int = 0) -> str:
        """记录工具调用（用于分析和优化）。"""
        tid = f"tool-{uuid.uuid4().hex[:12]}"
        self.execute(
            "INSERT INTO tool_logs(tool_call_id, tool_name, input_json, output_json, "
            "status, latency_ms) VALUES(?,?,?,?,?,?)",
            (tid, tool_name, input_json, output_json, status, latency_ms),
        )
        return tid

    # ── 错误案例 ──────────────────────────────────────────────────

    def save_error_case(self, question: str, wrong_answer: str,
                        error_type: str = "unknown",
                        correction: str | None = None,
                        fix_strategy: str | None = None) -> str:
        """保存错误案例用于改进系统。"""
        cid = f"case-{uuid.uuid4().hex[:12]}"
        self.execute(
            "INSERT INTO error_cases(case_id, question, wrong_answer, error_type, "
            "correction, fix_strategy) VALUES(?,?,?,?,?,?)",
            (cid, question, wrong_answer, error_type, correction, fix_strategy),
        )
        return cid


# ── 全局单例 ─────────────────────────────────────────────────────

_db_instance: SQLiteManager | None = None


def get_db() -> SQLiteManager:
    """获取全局数据库管理器（懒加载单例）。"""
    global _db_instance
    if _db_instance is None:
        _db_instance = SQLiteManager()
        _db_instance.initialize()
    return _db_instance
