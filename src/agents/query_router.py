"""Query Router — Agent 开发中的"意图识别"组件。

这是 Agent 的第一步：理解用户想做什么，决定走哪条处理链路。

【改进 vs 旧版】
  旧版：纯正则匹配，18+ 条规则，未命中时只能靠问号猜测
  新版：
    1. 正则快速通道（有明确触发词的直接命中，零 Token 消耗）
    2. LLM 语义兜底（正则未命中时，用 LLM 做 few-shot 分类）
    这样既保留了速度，又获得了语义理解能力。

【生产实践】
  这个"正则 + LLM fallback"的两级路由是工业界常见模式：
  - 80% 的请求被正则快速命中（无额外 Token 消耗）
  - 20% 的模糊请求交给 LLM 语义分类（消耗少量 Token）

7 种问题类型对应 7 条处理链路：
  general_chat      → 纯 LLM（"你好"、"你是谁"）
  knowledge_qa      → RAG 检索增强（"低温快充风险？"）
  document_summary  → RAG + 摘要（"总结这份文档"）
  table_analysis    → 表格工具（"分析CSV数据"）
  image_understanding → 图片工具（"这张图是什么"）
  report_generation → 报告生成（"写份周报"）
  memory_query      → 记忆检索（"我之前问过什么"）
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── 支持的问题类型 ────────────────────────────────────────────────

VALID_TYPES = {
    "general_chat", "knowledge_qa", "document_summary",
    "table_analysis", "image_understanding", "report_generation", "memory_query",
}


@dataclass
class RouteDecision:
    """路由决策 —— 告诉后续链路该怎么处理这个问题。"""
    question_type: str        # 判定的问题类型
    confidence: str           # 分类置信度: high / medium / low
    needs_rag: bool           # 是否需要走 RAG 检索
    needs_tools: list[str]    # 需要调用的工具列表
    reasoning: str            # 分类理由（调试用）
    routed_by: str = "regex"  # 路由方式: regex / llm / fallback


class QueryRouter:
    """两级路由器：正则快速通道 + LLM 语义兜底。

    路由规则是有序的 —— 越具体的规则越靠前，优先级越高。
    例如"分析表格最高温度"同时含"表格"和"温度"，
    "表格分析"排在"电池温度"前面，所以优先命中为 table_analysis。
    """

    # 【有序路由表】key=正则, value=(问题类型, 工具列表)
    # 排列原则：从具体到宽泛，工具触发词 > 领域词 > 通用词
    ROUTING_RULES: list[tuple[str, str, list[str]]] = [

        # ── ReAct 实时数据工具（需要调用工具获取实时数据）─────────
        (
            r"现在几点|当前时间|今天几号|几点了|时间是多少|今天日期|星期几"
            r"|what time|what date|what day|current time|current date|time now",
            "knowledge_qa", ["react_tools"],
        ),
        (
            r"哪个城市|我在哪|城市.*温度|城市.*环境"
            r"|what city|where am i|which city|my location|my city",
            "knowledge_qa", ["react_tools"],
        ),
        (
            r"电池.*温度|电池.*状态|电芯.*温度|电芯.*电压|实时温度"
            r"|battery.*temp|battery.*temperature|battery.*status|battery.*voltage",
            "knowledge_qa", ["react_tools"],
        ),

        # ── 表格分析（数值统计类问题，走 TableAnalysisTool）────────
        (
            r"最高温度|最低温度|最大值|最小值|平均值|标准差"
            r"|分析.*csv|分析.*表格|表格.*分析|csv.*分析"
            r"|温度.*趋势|电压.*变化|容量.*衰减|容量.*变化"
            r"|多少钱|参数.*对比|规格.*参数|数据是多少",
            "table_analysis", ["table_analysis"],
        ),

        # ── 报告生成 ───────────────────────────────────────────────
        (
            r"生成.*报告|生成.*周报|生成.*月报|项目.*报告|测试.*报告"
            r"|写.*报告|报告.*生成|周报|月报",
            "report_generation", ["report_generation"],
        ),

        # ── 图片理解 ───────────────────────────────────────────────
        (
            r"图片|图像|照片|截图|看图|image|picture|photo",
            "image_understanding", ["image_understanding"],
        ),

        # ── 文档摘要 ───────────────────────────────────────────────
        (
            r"总结|摘要|概括|归纳|summarize|summary|要点|概述",
            "document_summary", ["document_summary"],
        ),

        # ── 记忆查询 ───────────────────────────────────────────────
        (
            r"记得|之前.*说|上次.*说|我的偏好|我的习惯|记住|memory|记忆",
            "memory_query", [],
        ),

        # ── 闲聊（放较后，因为"帮助"等词可能出现在知识问答里）────
        (
            r"^(你好|hello|hi|hey|嗨)$|你是谁|谢谢|再见|bye"
            r"|你能做什么|你有什么功能|help me",
            "general_chat", [],
        ),

        # ── 电池/BMS 领域知识问答（领域专词，高置信度走 RAG）─────
        (
            r"低温|快充|析锂|极化|锂枝晶|隔膜|热失控|过充|过放"
            r"|BMS|SOC|SOH|电池.*安全|电池.*风险|电池.*容量|充电.*策略"
            r"|电池.*原理|电芯.*设计|电池.*寿命|循环.*次数",
            "knowledge_qa", ["rag_search"],
        ),
    ]

    def route(self, query: str) -> RouteDecision:
        """对用户输入进行分类，返回路由决策。

        流程：
          1. 遍历正则规则表，命中即返回（高效，零 Token 消耗）
          2. 未命中 → 调用 LLM 做语义分类（消耗少量 Token，但语义准确）
          3. LLM 也失败 → 规则兜底（有问号→knowledge_qa，否则→general_chat）
        """
        query_lower = query.lower().strip()

        # ── 第一级：正则快速通道 ──────────────────────────────────
        for pattern, qtype, tools in self.ROUTING_RULES:
            if re.search(pattern, query_lower):
                logger.info("Route[regex]: type=%s query='%s'", qtype, query[:30])
                return RouteDecision(
                    question_type=qtype,
                    confidence="high",
                    needs_rag=qtype in ("knowledge_qa", "document_summary"),
                    needs_tools=tools,
                    reasoning=f"正则匹配: {pattern[:40]}",
                    routed_by="regex",
                )

        # ── 第二级：LLM 语义兜底 ─────────────────────────────────
        # 正则未命中时，用 LLM 的语义理解能力做分类
        # 例如："我想了解一下锂电池的充放电机理" → 没有明确触发词，但语义上是 knowledge_qa
        llm_result = self._llm_classify(query)
        if llm_result:
            return llm_result

        # ── 第三级：规则兜底 ──────────────────────────────────────
        # LLM 调用失败（网络问题、Mock 模式）时的最终保障
        if "?" in query or "？" in query or any(
            w in query for w in ["什么", "如何", "怎么", "为什么", "哪个", "哪里"]
        ):
            return RouteDecision(
                question_type="knowledge_qa", confidence="low",
                needs_rag=True, needs_tools=["rag_search"],
                reasoning="含疑问词，推断为知识问答",
                routed_by="fallback",
            )

        return RouteDecision(
            question_type="general_chat", confidence="low",
            needs_rag=False, needs_tools=[],
            reasoning="未命中任何规则，默认闲聊",
            routed_by="fallback",
        )

    def _llm_classify(self, query: str) -> RouteDecision | None:
        """用 LLM 做语义意图分类（正则兜底第二级）。

        使用 few-shot prompt，让 LLM 输出 JSON 格式的分类结果。
        失败时返回 None，由上层触发第三级规则兜底。
        """
        try:
            from src.models.llm_service import get_llm
            from src.utils.config_handler import get_prompt_templates

            # 从 YAML 加载意图分类提示词
            tpl = get_prompt_templates()
            prompt_tpl = tpl["routing"]["intent_classification"]["content"]
            prompt = prompt_tpl.format(question=query)

            llm = get_llm()
            raw = llm.generate(prompt)

            # 解析 LLM 返回的 JSON
            # 兼容 LLM 可能在 JSON 前后输出多余文字的情况
            match = re.search(r'\{[^{}]+\}', raw, re.DOTALL)
            if not match:
                return None

            data = json.loads(match.group())
            qtype = data.get("type", "").strip()
            if qtype not in VALID_TYPES:
                return None

            confidence_val = float(data.get("confidence", 0.5))
            confidence = "high" if confidence_val >= 0.8 else ("medium" if confidence_val >= 0.5 else "low")

            logger.info("Route[llm]: type=%s confidence=%.2f query='%s'",
                        qtype, confidence_val, query[:30])

            return RouteDecision(
                question_type=qtype,
                confidence=confidence,
                needs_rag=qtype in ("knowledge_qa", "document_summary"),
                needs_tools=_default_tools(qtype),
                reasoning=data.get("reasoning", "LLM语义分类"),
                routed_by="llm",
            )

        except Exception as e:
            # LLM 分类失败（包括 Mock 模式下 JSON 解析失败），静默降级
            logger.debug("LLM routing failed (expected in mock mode): %s", e)
            return None


def _default_tools(qtype: str) -> list[str]:
    """按问题类型返回默认工具列表。"""
    mapping = {
        "knowledge_qa": ["rag_search"],
        "document_summary": ["document_summary", "rag_search"],
        "table_analysis": ["table_analysis"],
        "image_understanding": ["image_understanding"],
        "report_generation": ["report_generation", "rag_search"],
        "general_chat": [],
        "memory_query": [],
    }
    return mapping.get(qtype, [])
