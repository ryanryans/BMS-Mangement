"""集成测试: 报告生成 — 基于模板和知识库内容生成结构化报告。"""
from pathlib import Path

import pytest

from src.tools.report_generation_tool import ReportGenerationTool
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


class TestReportGeneration:
    def test_standard_report_has_required_sections(self):
        """标准报告包含必需的段落。"""
        tool = ReportGenerationTool()
        content = tool.generate("低温快充测试数据分析", "standard")

        assert "低温快充测试数据分析" in content
        assert "报告概述" in content
        assert "数据分析" in content

    def test_weekly_report_has_required_sections(self):
        """周报包含本周完成/进行中/下周计划。"""
        tool = ReportGenerationTool()
        content = tool.generate("BMS项目周报", "weekly")

        assert "本周完成" in content
        assert "进行中" in content
        assert "下周计划" in content

    def test_battery_test_report_has_required_sections(self):
        """电池测试报告包含电压、温度、容量分析。"""
        tool = ReportGenerationTool()
        content = tool.generate("电芯循环测试", "battery_test")

        assert "电压分析" in content
        assert "温度分析" in content
        assert "容量评估" in content

    def test_report_with_kb_data(self, kb, tmp_path):
        """基于知识库检索内容生成报告。"""
        (tmp_path / "test_report.md").write_text(
            "# BMS测试报告\n温度在55度时效率下降至72%，需要优化散热。",
            encoding="utf-8"
        )
        kb.ingest_file(tmp_path / "test_report.md")

        kb_result = kb.query("BMS测试温度效率", top_k=3)
        assert kb_result["evidence_count"] >= 1

        tool = ReportGenerationTool()
        report_data = {
            "data_analysis": f"知识库检索结果: {kb_result['answer'][:200]}",
            "key_findings": f"找到{len(kb_result['sources'])}条相关记录",
        }
        content = tool.generate("BMS温度测试", "standard", data=report_data)
        assert "BMS温度测试" in content
        assert "报告概述" in content

    def test_report_generation_tool_returns_non_empty(self):
        """报告生成工具返回非空字符串。"""
        tool = ReportGenerationTool()
        for rtype in ["standard", "weekly", "battery_test"]:
            content = tool.generate("测试", rtype)
            assert len(content) > 100, f"Report type {rtype} is too short"
            assert "测试" in content
