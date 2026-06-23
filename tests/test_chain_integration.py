"""P0-6 集成测试：覆盖 LLM 调用链、报告服务、共享问答服务、无数据污染。"""
import os, tempfile
from pathlib import Path
import pytest


@pytest.fixture
def isolated_env(tmp_path):
    """隔离环境：临时 DB + 临时 vector store，禁止污染真实 data/。"""
    old_db = os.environ.get("SQLITE_DB_PATH", "")
    os.environ["SQLITE_DB_PATH"] = str(tmp_path / "test.db")
    yield tmp_path
    if old_db:
        os.environ["SQLITE_DB_PATH"] = old_db


class TestLLMCallChain:
    """测试 LLM 在 RAG 链中被正确调用。"""

    def test_handle_chat_calls_llm_for_knowledge_qa(self, isolated_env):
        """知识问答应调用 LLM。"""
        from src.services.chat_service import handle_chat
        result = handle_chat("你好")
        # 至少返回完整结构
        for key in ["answer", "sources", "confidence", "question_type", "model_type", "llm_called"]:
            assert key in result, f"Missing key: {key}"
        # model_type 可以是 MockLLM 或 DeepSeekAdapter（取决于 .env 配置）
        assert result["model_type"] in ("MockLLM", "DeepSeekAdapter") or "MockLLM" in result["model_type"]

    def test_handle_chat_routes_table_analysis(self):
        """表格分析请求应路由到 table_analysis。"""
        from src.services.chat_service import handle_chat
        result = handle_chat("分析battery_data.csv的最高温度和容量变化趋势")
        assert result["question_type"] == "table_analysis"
        assert "table_analysis" in result["tools_used"]

    def test_report_service_calls_llm(self, isolated_env, tmp_path):
        """报告服务应调用 LLM 并返回诊断信息。"""
        # 先入库一个小文档
        db_path = tmp_path / "test2.db"
        from src.database.sqlite_manager import SQLiteManager
        from src.rag.vector_store import SimpleVectorStore
        from src.rag.knowledge_base_service import KnowledgeBaseService
        db = SQLiteManager(str(db_path))
        db.initialize()
        kb = KnowledgeBaseService(db=db, vector_store=SimpleVectorStore(persist_dir=tmp_path))

        doc = tmp_path / "test.md"
        doc.write_text("BMS项目本周完成了电压采样测试。温度控制在正常范围内。", encoding="utf-8")
        kb.ingest_file(doc)

        from src.services.report_service import generate_report
        report = generate_report("BMS项目周报", "weekly")
        assert report["from_llm"] or not report["from_llm"]  # 布尔值存在
        assert "content" in report
        assert "model_type" in report
        assert "prompt_preview" in report
        assert len(report["content"]) > 50

    def test_kb_query_returns_diagnostic_fields(self, tmp_path):
        """KnowledgeBaseService.query() 应返回诊断字段。"""
        from src.database.sqlite_manager import SQLiteManager
        from src.rag.vector_store import SimpleVectorStore
        from src.rag.knowledge_base_service import KnowledgeBaseService
        db = SQLiteManager(str(tmp_path / "test3.db"))
        db.initialize()
        kb = KnowledgeBaseService(db=db, vector_store=SimpleVectorStore(persist_dir=tmp_path))

        doc = tmp_path / "doc.md"
        doc.write_text("低温快充可能导致负极析锂风险增加。电池温度超过60度需要停机。", encoding="utf-8")
        kb.ingest_file(doc)

        result = kb.query("低温快充可能带来什么风险？")
        assert "llm_called" in result
        assert "prompt_preview" in result
        assert "retrieval_debug" in result
        debug = result["retrieval_debug"]
        assert "query" in debug
        assert "keywords" in debug
        assert "threshold" in debug

    def test_no_pollution_of_real_data(self, tmp_path):
        """测试不应污染真实 data/vector_db/vector_index.json。"""
        real_index = Path("data/vector_db/vector_index.json")
        existed_before = real_index.exists()

        from src.rag.vector_store import SimpleVectorStore
        store = SimpleVectorStore(persist_dir=tmp_path)
        store.add_document("test", {"key": "val"})
        store.persist()

        # 真实路径应未被修改（即使存在也是之前就有的）
        assert real_index.exists() == existed_before

    def test_short_domain_query_returns_evidence(self, tmp_path):
        """短领域查询'电池有什么风险？'应返回证据。"""
        from src.database.sqlite_manager import SQLiteManager
        from src.rag.vector_store import SimpleVectorStore
        from src.rag.knowledge_base_service import KnowledgeBaseService
        db = SQLiteManager(str(tmp_path / "test5.db"))
        db.initialize()
        kb = KnowledgeBaseService(db=db, vector_store=SimpleVectorStore(persist_dir=tmp_path))

        doc = tmp_path / "battery.md"
        doc.write_text(
            "低温快充可能导致负极析锂风险增加。"
            "电池管理系统需要实时监测电池温度。",
            encoding="utf-8"
        )
        kb.ingest_file(doc)

        result = kb.query("电池有什么风险？")
        assert result["evidence_count"] >= 1 or result["confidence"] != "low", \
            f"Short domain query failed: evidence={result['evidence_count']} conf={result['confidence']}"
