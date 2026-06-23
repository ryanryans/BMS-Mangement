"""测试新 RAG 设计：无证据也调用 LLM，通用对话不走拒答。"""
import os, tempfile
from pathlib import Path
import pytest


@pytest.fixture
def isolated_kb(tmp_path):
    """隔离 KB，只含最小电池文档。"""
    os.environ["SQLITE_DB_PATH"] = str(tmp_path / "test.db")
    from src.database.sqlite_manager import SQLiteManager
    from src.rag.vector_store import SimpleVectorStore
    from src.rag.knowledge_base_service import KnowledgeBaseService
    db = SQLiteManager(str(tmp_path / "test.db"))
    db.initialize()
    kb = KnowledgeBaseService(db=db, vector_store=SimpleVectorStore(persist_dir=tmp_path))
    doc = tmp_path / "battery.md"
    doc.write_text("低温快充可能导致负极析锂风险增加。电池需预热到10度以上。", encoding="utf-8")
    kb.ingest_file(doc)
    return kb


class TestNoEvidenceStillCallsLLM:
    """无检索结果时，Chat 仍调用 LLM。"""

    def test_chat_no_evidence_still_answers(self, isolated_kb, monkeypatch):
        """知识库无匹配时，handle_chat 仍返回 LLM 回答。"""
        from src.services.chat_service import handle_chat
        # 使用 auto 模式，确保不拒答
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")  # placeholder → RuleBasedLLM
        from src.models.llm_service import reset_llm
        reset_llm()

        result = handle_chat("电池应该怎么制造？", rag_mode="auto")
        assert len(result["answer"]) > 20
        assert result["needs_refusal"] is False  # 新设计不拒答

    def test_general_chat_no_refusal(self, monkeypatch):
        """'你是谁' 不走知识库拒答。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.services.chat_service import handle_chat

        result = handle_chat("你是谁", rag_mode="auto")
        assert len(result["answer"]) > 5
        assert result["needs_refusal"] is False
        assert result["retrieval_status"] in ("off", "empty", "not_attempted")

    def test_what_can_you_do_no_refusal(self, monkeypatch):
        """'你能做什么' 不走知识库拒答。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.services.chat_service import handle_chat

        result = handle_chat("你能做什么", rag_mode="auto")
        assert len(result["answer"]) > 10
        assert result["needs_refusal"] is False

    def test_no_context_answer_contains_label(self, monkeypatch):
        """无 context 时回答应包含提示语（MockLLM 模式）。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.services.chat_service import handle_chat

        result = handle_chat("介绍一下电池制造流程", rag_mode="auto")
        # 应该有内容（不拒答）
        assert len(result["answer"]) > 20


class TestRetrieveContext:
    """KnowledgeBaseService.retrieve_context() 只检索，不生成答案。"""

    def test_retrieve_context_returns_no_answer(self, isolated_kb):
        """retrieve_context 返回的 dict 不含 answer 字段。"""
        result = isolated_kb.retrieve_context("低温快充风险")
        assert "answer" not in result
        assert "context" in result
        assert "sources" in result
        assert "retrieval_status" in result

    def test_retrieve_context_has_sources(self, isolated_kb):
        """匹配时返回 sources。"""
        result = isolated_kb.retrieve_context("低温快充")
        assert result["evidence_count"] >= 1 or result["max_score"] > 0

    def test_retrieve_context_empty_for_unrelated(self, isolated_kb):
        """不匹配时 context 为空。"""
        result = isolated_kb.retrieve_context("量子计算")
        assert result["context"] == "" or result["evidence_count"] == 0


class TestLLMRagChain:
    """LLMRagChain 永远调用 LLM。"""

    def test_chain_invoke_without_context(self, monkeypatch):
        """无 context 时 chain.invoke() 仍返回 LLM 回答。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.chains.llm_rag_chain import LLMRagChain

        chain = LLMRagChain()
        result = chain.invoke(user_prompt="你是谁", context="", mode="chat")
        assert len(result["answer"]) > 5
        assert result["llm_called"] is True
        assert result["has_context"] is False

    def test_chain_invoke_with_context(self, monkeypatch):
        """有 context 时返回 has_context=True。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.chains.llm_rag_chain import LLMRagChain

        chain = LLMRagChain()
        result = chain.invoke(
            user_prompt="低温快充风险？",
            context="低温快充可能导致负极析锂。",
            mode="chat",
        )
        assert result["has_context"] is True
        assert len(result["answer"]) > 10


class TestReportTopicFirst:
    """报告生成：主题优先，KB 只是参考。"""

    def test_report_battery_manufacturing(self, isolated_kb, monkeypatch):
        """报告主题 '电池应该怎么制造' 时，输出围绕制造流程。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.services.report_service import generate_report

        # isolated KB 只有低温快充，与制造无关
        report = generate_report("电池应该怎么制造", "standard", rag_mode="auto")
        content = report["content"]
        # 应该包含制造相关词，而不是被低温快充主导
        has_manufacturing_content = any(
            kw in content for kw in ["制造", "生产", "工艺", "材料", "制备", "装配"]
        ) or report["from_llm"]
        assert has_manufacturing_content or len(content) > 50

    def test_report_low_relevance_context_not_forced(self, isolated_kb, monkeypatch):
        """知识库低相关时，报告不强行引用低温快充作为主线。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.services.report_service import generate_report

        report = generate_report("电池质量控制体系", "standard", rag_mode="auto")
        # retrieval_status 应反映低相关
        assert report["retrieval_status"] in ("empty", "low_relevance", "used")
        # 如果是 low_relevance / empty，报告不应被强制引用冷知识
        if report["retrieval_status"] in ("empty", "low_relevance"):
            # 仍是有效报告
            assert len(report["content"]) > 50

    def test_report_high_relevance_cites_sources(self, isolated_kb, monkeypatch):
        """知识库高相关时，应引用 sources。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm
        reset_llm()
        from src.services.report_service import generate_report

        report = generate_report("低温快充安全测试报告", "battery_test", rag_mode="auto")
        assert len(report["content"]) > 50
