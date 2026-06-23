"""集成测试: 上传 → 入库 → 数据库同步 → 检索验证。"""
import tempfile
from pathlib import Path

import pytest

from src.rag.knowledge_base_service import KnowledgeBaseService, reset_kb_service
from src.database.sqlite_manager import SQLiteManager


@pytest.fixture
def kb(tmp_path):
    """创建使用临时路径的知识库服务（隔离环境）。"""
    import os
    os.environ["SQLITE_DB_PATH"] = str(tmp_path / "test.db")
    os.environ["APP_ENV"] = "test"

    db = SQLiteManager(str(tmp_path / "test.db"))
    db.initialize()

    from src.rag.vector_store import SimpleVectorStore
    vs = SimpleVectorStore(persist_dir=tmp_path)

    kb = KnowledgeBaseService(db=db, vector_store=vs)
    yield kb
    # cleanup
    reset_kb_service()


class TestUploadAndIngest:
    def test_ingest_md_file_creates_db_records(self, kb, tmp_path):
        """上传MD文件后，documents表和chunks表有记录。"""
        md_file = tmp_path / "battery_test.md"
        md_file.write_text("# 电池知识\n低温快充可能导致锂枝晶生长，引发内部短路风险。", encoding="utf-8")

        result = kb.ingest_file(md_file)

        assert result.success, f"Ingest failed: {result.error}"
        assert result.chunk_count >= 1
        assert result.doc_id

        # 验证documents表
        doc = kb._db.get_document(result.doc_id)
        assert doc is not None
        assert doc["doc_name"] == "battery_test.md"

        # 验证chunks表
        chunks = kb._db.list_chunks(result.doc_id)
        assert len(chunks) >= 1

    def test_ingest_txt_file_creates_vector(self, kb, tmp_path):
        """上传TXT文件后，向量库有记录。"""
        txt_file = tmp_path / "knowledge.txt"
        txt_file.write_text("电池温度超过60度需要立即停机检查。电压低于3.0V时电池可能损坏。", encoding="utf-8")

        result = kb.ingest_file(txt_file)
        assert result.success
        assert result.vector_count >= 1

        # 验证向量库
        status = kb.get_status()
        assert status.vector_count >= 1

    def test_retrieve_after_ingest(self, kb, tmp_path):
        """入库后检索能命中新文档。"""
        md_file = tmp_path / "battery_risks.md"
        md_file.write_text(
            "# 电池风险\n\n"
            "## 低温快充风险\n"
            "低温（<0°C）下快充可能导致锂枝晶生长。"
            "锂枝晶会刺穿隔膜，引发内部短路。\n\n"
            "## 高温风险\n"
            "温度超过60°C可能触发热失控。",
            encoding="utf-8"
        )

        kb.ingest_file(md_file)

        # 检索低温快充
        answer = kb.query("低温快充可能带来什么风险？")
        assert answer["evidence_count"] >= 1, f"No evidence found: {answer}"
        assert answer["confidence"] != "low", f"Confidence too low: {answer['confidence']}"

        # 来源应该是battery_risks.md
        source_files = {s["filename"] for s in answer["sources"]}
        assert "battery_risks.md" in source_files, f"Expected battery_risks.md in sources: {source_files}"

    def test_batch_ingest(self, kb, tmp_path):
        """批量入库多个文件。"""
        (tmp_path / "f1.md").write_text("# 文件1\n电池基础知识：三元锂电池能量密度高，适合乘用车。磷酸铁锂安全性好。", encoding="utf-8")
        (tmp_path / "f2.md").write_text("# 文件2\n充电策略详解：快充需要在20-80% SOC区间进行。低温需预热到10度以上。", encoding="utf-8")
        (tmp_path / "f3.md").write_text("# 文件3\n故障排查指南：容量衰减过快可能是由于高温存储或低温快充引起。", encoding="utf-8")

        result = kb.ingest_files([
            tmp_path / "f1.md",
            tmp_path / "f2.md",
            tmp_path / "f3.md",
        ])
        assert result.total == 3
        assert result.success_count == 3, f"Expected 3 success, got {result.success_count}. Details: {[(d.file_name, d.error) for d in result.details]}"
        assert result.total_chunks >= 3

    def test_status_reflects_actual_state(self, kb, tmp_path):
        """get_status() 返回正确的文档数/chunk数/向量数。"""
        (tmp_path / "test.md").write_text("测试文档内容。", encoding="utf-8")
        kb.ingest_file(tmp_path / "test.md")

        status = kb.get_status()
        assert status.document_count == 1
        assert status.chunk_count >= 1
        assert status.vector_count >= 1
        assert status.status == "ready"
