"""Test SQLite database initialization and CRUD operations."""
import sqlite3

from src.database.sqlite_manager import SQLiteManager


def test_initialize_database_creates_all_tables(tmp_path):
    """Test that database init creates all required tables."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(str(db_path))
    manager.initialize()

    with sqlite3.connect(str(db_path)) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t[0] for t in tables}

    expected = {
        "schema_migrations", "documents", "chunks", "conversations",
        "memories", "feedback", "tool_logs", "error_cases",
    }
    assert expected <= table_names, f"Missing tables: {expected - table_names}"


def test_document_crud(tmp_path):
    """Test document insert, list, get, delete."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(str(db_path))
    manager.initialize()

    # Insert
    doc_id = manager.insert_document("test.txt", "text", "/path/to/test.txt", "A test doc")
    assert doc_id.startswith("doc-")

    # List
    docs = manager.list_documents()
    assert len(docs) == 1
    assert docs[0]["doc_name"] == "test.txt"

    # Get
    doc = manager.get_document(doc_id)
    assert doc is not None
    assert doc["doc_type"] == "text"

    # Delete
    assert manager.delete_document(doc_id) is True
    assert manager.get_document(doc_id) is None


def test_memory_crud(tmp_path):
    """Test memory insert, list, disable, delete."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(str(db_path))
    manager.initialize()

    # Insert
    mid = manager.save_memory("user_preference", "喜欢简洁回答", importance=5)
    assert mid.startswith("mem-")

    # List
    items = manager.list_memories("user_preference")
    assert len(items) == 1
    assert "简洁" in items[0]["content"]

    # Disable
    assert manager.disable_memory(mid) is True
    assert len(manager.list_memories("user_preference")) == 0

    # Delete
    assert manager.delete_memory(mid) is True


def test_conversation_save(tmp_path):
    """Test conversation saving."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(str(db_path))
    manager.initialize()

    cid = manager.save_conversation(
        "什么是RAG?", "RAG是检索增强生成",
        used_docs_json='[{"file":"doc1"}]',
        latency_ms=150,
    )
    assert cid.startswith("conv-")

    convs = manager.list_conversations(limit=10)
    assert len(convs) == 1


def test_feedback_save(tmp_path):
    """Test feedback saving."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(str(db_path))
    manager.initialize()

    fid = manager.save_feedback("conv-1", "rating", "很有帮助")
    assert fid.startswith("feedback-")

    items = manager.list_feedback()
    assert len(items) >= 1


def test_error_case_save(tmp_path):
    """Test error case saving."""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(str(db_path))
    manager.initialize()

    cid = manager.save_error_case(
        "电池最高温度多少?",
        "不知道",
        "knowledge_gap",
        "需要上传电池测试数据",
        "完善电池数据文档",
    )
    assert cid.startswith("case-")
