"""Test Agentic RAG: query router, task planner, tool selector, verifier."""
from src.agents.query_router import QueryRouter
from src.agents.task_planner import TaskPlanner
from src.agents.tool_selector import ToolSelector
from src.agents.answer_verifier import AnswerVerifier


class TestQueryRouter:
    def test_route_general_chat(self):
        router = QueryRouter()
        result = router.route("你好")
        assert result.question_type == "general_chat"
        assert result.needs_rag is False

    def test_route_knowledge_qa(self):
        router = QueryRouter()
        result = router.route("如何维护HEPA滤网？")
        assert result.question_type in ("knowledge_qa", "general_chat")

    def test_route_table_analysis(self):
        router = QueryRouter()
        result = router.route("分析这个CSV表格的数据")
        assert result.question_type == "table_analysis"

    def test_route_document_summary(self):
        router = QueryRouter()
        result = router.route("帮我总结这份文档")
        assert result.question_type == "document_summary"

    def test_route_battery_query(self):
        router = QueryRouter()
        result = router.route("电池温度超过60度怎么办")
        assert result.question_type == "knowledge_qa"
        # 新路由规则：电池温度关键词优先匹配 ReAct 工具调用
        assert result.needs_tools  # 应该有工具推荐（rag_search 或 get_battery_temperature）

    def test_route_report_generation(self):
        router = QueryRouter()
        result = router.route("生成一份月度报告")
        assert result.question_type == "report_generation"


class TestTaskPlanner:
    def test_plan_knowledge_qa(self):
        planner = TaskPlanner()
        plan = planner.plan("knowledge_qa")
        assert plan.total_steps >= 3
        assert any(s.action == "rag_retrieve" for s in plan.steps)
        assert any(s.action == "verify_answer" for s in plan.steps)

    def test_plan_general_chat(self):
        planner = TaskPlanner()
        plan = planner.plan("general_chat")
        assert plan.total_steps == 1

    def test_plan_table_analysis(self):
        planner = TaskPlanner()
        plan = planner.plan("table_analysis")
        assert any(s.tool == "table_analysis" for s in plan.steps)


class TestToolSelector:
    def test_select_for_knowledge_qa(self):
        selector = ToolSelector()
        selection = selector.select("knowledge_qa", "如何保养机器人")
        assert "rag_search" in selection.tools

    def test_select_for_table(self):
        selector = ToolSelector()
        selection = selector.select("table_analysis", "分析电池数据")
        assert "table_analysis" in selection.tools

    def test_select_for_general(self):
        selector = ToolSelector()
        selection = selector.select("general_chat", "你好")
        assert len(selection.tools) == 0


class TestAnswerVerifier:
    def test_verify_with_evidence(self):
        verifier = AnswerVerifier()
        result = verifier.verify(
            "根据测试数据，电池最高温度为65°C",
            [{"content": "电池测试最高温度65°C", "score": 0.25}],
            0.25,
        )
        assert result.is_grounded
        assert result.confidence == "high"
        assert not result.needs_refusal

    def test_verify_no_evidence(self):
        verifier = AnswerVerifier()
        result = verifier.verify(
            "这个设备非常好用",
            [],
            0.0,
        )
        assert not result.is_grounded
        assert result.needs_refusal

    def test_verify_medium_confidence(self):
        verifier = AnswerVerifier()
        result = verifier.verify(
            "温度可能偏高",
            [{"content": "温度数据", "score": 0.12}],
            0.12,
        )
        assert result.confidence == "medium"
