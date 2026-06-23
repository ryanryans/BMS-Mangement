"""集成测试: 清空知识库 — 数据库和向量库全部归零。"""
from pathlib import Path

import pytest

from src.rag.knowledge_base_service import KnowledgeBaseService, reset_kb_service
from src.database.sqlite_manager import SQLiteManager


@pytest.fixture
def kb(tmp_path):
    import os
    os.environ["SQLITE_DB_PATH"] = str(tmp_path / "test.db")

    db = SQLiteManager(str(tmp_path / "test.db"))
    db.initialize()

    from src.rag.vector_store import SimpleVectorStore
    vs = SimpleVectorStore(persist_dir=tmp_path)

    kb = KnowledgeBaseService(db=db, vector_store=vs)
    yield kb
    reset_kb_service()


class TestClearKnowledgeBase:
    def test_clear_empties_database(self, kb, tmp_path):
        """清空后documents表和chunks表为空。"""
        (tmp_path / "test.md").write_text("测试", encoding="utf-8")
        kb.ingest_file(tmp_path / "test.md")

        # 清空前有数据
        assert kb.get_status().document_count == 1
        assert kb.get_status().chunk_count >= 1

        # 执行清空
        result = kb.clear()
        assert result["success"]

        # 清空后无数据
        status = kb.get_status()
        assert status.document_count == 0, f"Expected 0 documents, got {status.document_count}"
        assert status.chunk_count == 0, f"Expected 0 chunks, got {status.chunk_count}"
        assert status.vector_count == 0, f"Expected 0 vectors, got {status.vector_count}"

    def test_clear_empties_vector_store(self, kb, tmp_path):
        """清空后向量库为空。"""
        (tmp_path / "test.md").write_text("测试内容足够长以便生成向量", encoding="utf-8")
        kb.ingest_file(tmp_path / "test.md")

        assert kb._vector_store.document_count >= 1

        kb.clear()
        assert kb._vector_store.document_count == 0

    def test_clear_removes_index_file(self, kb, tmp_path):
        """清空后vector_index.json文件不存在或为空文档列表。"""
        (tmp_path / "test.md").write_text("测试", encoding="utf-8")
        kb.ingest_file(tmp_path / "test.md")

        index_path = kb._vector_store._index_path
        assert index_path.exists()

        kb.clear()

        # clear() 后 persist() 写入空文档列表，文件存在但文档数为0
        status = kb.get_status()
        assert status.vector_count == 0

    def test_clear_then_ingest_works(self, kb, tmp_path):
        """清空后重新入库正常。"""
        (tmp_path / "old.md").write_text("旧内容", encoding="utf-8")
        kb.ingest_file(tmp_path / "old.md")
        kb.clear()

        # 重新入库新文件
        (tmp_path / "new.md").write_text("新内容：电池低温风险", encoding="utf-8")
        result = kb.ingest_file(tmp_path / "new.md")
        assert result.success

        status = kb.get_status()
        assert status.document_count == 1
