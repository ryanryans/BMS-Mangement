"""共享报告服务 — 主题优先，知识库资料仅作参考。

- 用户报告主题是最高优先级
- 知识库资料只是可选增强
- 不相关则不使用
- 无资料也生成完整报告
"""
from __future__ import annotations

import logging
from typing import Any

from src.chains.llm_rag_chain import LLMRagChain
from src.rag.knowledge_base_service import get_kb_service
from src.models.model_factory import get_model_status
from src.tools.report_generation_tool import ReportGenerationTool

logger = logging.getLogger(__name__)


def generate_report(
    topic: str,
    report_type: str = "standard",
    period: str | None = None,
    rag_mode: str = "auto",
) -> dict[str, Any]:
    """生成结构化报告：LLM 优先，模板仅作 fallback。

    Args:
        topic: 报告主题（最高优先级）
        report_type: standard / weekly / battery_test
        period: 可选周期
        rag_mode: auto / strict / off
    """
    model_info = get_model_status()
    kb = get_kb_service()

    # 1. 检索知识库（可选）
    retrieval = kb.retrieve_context(topic, top_k=8)
    context = retrieval["context"]
    sources = retrieval["sources"]
    retrieval_status = retrieval["retrieval_status"]
    has_relevant = retrieval["has_relevant_context"]

    # 2. strict 模式 + 无相关资料 → 拒答
    if rag_mode == "strict" and not has_relevant:
        return {
            "topic": topic, "report_type": report_type,
            "content": "当前知识库中没有与报告主题直接相关的资料，无法生成基于知识库的报告。请上传相关文档或切换到 auto 模式。",
            "from_llm": False, "llm_called": False,
            "llm_provider": model_info["llm_provider"],
            "real_llm_success": False, "model_type": model_info["model_type"],
            "is_mock": model_info["is_mock"], "fallback_reason": "strict模式无相关资料",
            "sources_used": 0, "prompt_preview": "",
        }

    # 3. 调用 LLMRagChain（auto / off 模式都走这里）
    chain = LLMRagChain()
    chain_result = chain.invoke(
        user_prompt=topic,
        context=context if context and has_relevant else "",
        mode="report",
        extra_vars={"topic": topic, "report_type": report_type},
    )

    from_llm = chain_result.get("real_llm_success", False)
    llm_answer = chain_result["answer"]

    # 4. 如果 LLM 输出太短或不可用，回退模板
    if not llm_answer or len(llm_answer.strip()) < 80:
        tool = ReportGenerationTool()
        report_data = {"summary": f"本报告针对「{topic}」进行分析（模板生成，未调用真实大模型）。"}
        if sources:
            report_data["data_analysis"] = "\n".join(
                f"- {s['filename']}: {s['preview'][:200]}" for s in sources[:3]
            )
        content = tool.generate(topic, report_type, data=report_data, period=period)
        fallback_reason = "LLM输出过短，回退模板"
    else:
        content = llm_answer
        fallback_reason = ""

    # 5. Mock 模式标注
    if model_info["is_mock"]:
        content = (
            f"> ⚠️ 当前为 MockLLM / RuleBasedLLM 模式，未调用真实大模型。"
            f"配置 DEEPSEEK_API_KEY 到 .env 可获得 AI 生成的完整报告。\n\n---\n\n{content}"
        )

    return {
        "topic": topic, "report_type": report_type,
        "content": content,
        "from_llm": from_llm,
        "llm_called": chain_result["llm_called"],
        "llm_provider": chain_result["llm_provider"],
        "real_llm_success": chain_result.get("real_llm_success", False),
        "model_type": model_info["model_type"],
        "is_mock": model_info["is_mock"],
        "fallback_reason": fallback_reason,
        "retrieval_status": retrieval_status,
        "sources_used": len(sources),
        "prompt_preview": chain_result.get("prompt_preview", "")[:500],
    }
