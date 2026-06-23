"""集成测试: 清空知识库后只入库电池文档，验证不返回扫地机器人内容。"""
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


class TestNoOldPollution:
    def test_only_battery_content_after_clear_and_ingest(self, kb, tmp_path):
        """清空后只入库电池文档，查询不应返回扫地机器人内容。"""
        # 清空
        kb.clear()

        # 只入库电池知识
        battery_file = tmp_path / "battery_knowledge.md"
        battery_file.write_text(
            "# 电池知识\n"
            "低温快充可能导致锂枝晶生长，引发内部短路。\n"
            "温度超过60度需要立即停机检查。\n"
            "BMS需要监测电压、电流和温度。",
            encoding="utf-8"
        )
        kb.ingest_file(battery_file)

        # 查询低温快充风险
        answer = kb.query("低温快充可能带来什么风险？")
        assert answer["evidence_count"] >= 1

        # 所有来源必须是电池文件
        for s in answer["sources"]:
            assert "battery" in s["filename"].lower(), \
                f"Source should be about battery, got: {s['filename']}"

        # 不应包含扫地机器人相关内容
        assert "扫地" not in answer["answer"]
        assert "选购" not in answer["answer"]

    def test_no_evidence_for_unrelated_question(self, kb, tmp_path):
        """查询知识库中没有的内容应触发证据不足。"""
        kb.clear()

        battery_file = tmp_path / "battery.md"
        battery_file.write_text("电池温度管理：高温超过60度需要停机检查。", encoding="utf-8")
        kb.ingest_file(battery_file)

        # 查询不相关的问题
        answer = kb.query("扫地机器人的价格是多少？")
        # 应该证据不足
        assert answer["confidence"] == "low" or answer["evidence_count"] == 0, \
            f"Expected low confidence for unrelated query, got: {answer['confidence']}"

    def test_sources_have_correct_filenames(self, kb, tmp_path):
        """返回的source中filename应该是正确的。"""
        kb.clear()

        (tmp_path / "battery_guide.md").write_text(
            "电池充电指南：低温充电前需要将电池预热到10度以上。"
            "快充功率过高会加速电池老化。在零下环境中充电可能形成锂枝晶。",
            encoding="utf-8"
        )
        kb.ingest_file(tmp_path / "battery_guide.md")

        answer = kb.query("低温充电需要注意什么？")
        assert answer["evidence_count"] >= 1, f"Expected evidence, got: {answer}"
        source_files = {s["filename"] for s in answer["sources"]}
        assert "battery_guide.md" in source_files, f"Expected battery_guide.md in sources: {source_files}"
