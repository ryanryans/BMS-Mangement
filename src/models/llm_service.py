"""LLM 服务层 — Agent 开发中的"模型抽象"。

核心设计模式：依赖倒置 + 策略模式。

所有业务代码依赖 LLMProvider 接口（Protocol），而不是具体实现。
这样可以在不修改业务代码的情况下切换模型：
  — 有 API Key → DeepSeekAdapter（真实大模型）
  — 无 API Key → RuleBasedLLM（本地规则引擎）

学习要点：
  1. Protocol 定义接口契约（类似 Java 的 interface）
  2. 工厂函数 get_llm() 根据环境变量选择实现
  3. 单例模式避免重复初始化（reset_llm() 可清除缓存）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol

from src.core.settings import get_settings

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """LLM 提供者接口 —— 所有 LLM 实现必须满足的契约。"""
    def generate(self, prompt: str, **kwargs) -> str: ...
    def generate_with_context(self, question: str, context: str, **kwargs) -> str: ...


class RuleBasedLLM:
    """基于规则的本地 LLM 替代方案。

    为什么需要这个？
    — 开发和演示时不需要 API Key
    — 不需要网络连接
    — 行为完全可预测，方便调试

    工作原理：
    — 从 prompt 中提取用户问题和参考资料
    — 按文件名和关键句子结构化拼接
    — 不产生真正的自然语言生成（只是智能拼接）
    """

    def __init__(self):
        self._settings = get_settings()

    def generate(self, prompt: str, **kwargs) -> str:
        """处理 prompt，自动检测是否包含上下文。"""
        question = self._extract_question(prompt)       # 从模板中提取用户问题
        context = self._extract_context(prompt)          # 从模板中提取参考资料
        if context:
            return self.generate_with_context(question, context, **kwargs)
        return self._general_response(question)          # 无上下文 → 模板回复

    def generate_with_context(self, question: str, context: str, **kwargs) -> str:
        """基于上下文拼接结构化回答（Mock 模式下的 RAG 输出）。

        虽然做不到真正的语义理解，但能把检索到的资料按来源组织成可读格式。
        """
        import re
        if not context or len(context.strip()) < 10:
            return "无法回答——知识库资料不足。请上传更多相关文档。"

        # 按"参考资料编号"切分证据块
        ref_blocks = re.split(r'【参考资料\d+】', context)
        ref_blocks = [b.strip() for b in ref_blocks if b.strip()]

        answer_parts = ["根据知识库中的资料：\n"]

        for i, block in enumerate(ref_blocks[:5]):
            # 提取文件名
            file_match = re.search(r'来源文件:\s*(\S+)', block)
            filename = file_match.group(1) if file_match else f"来源{i+1}"

            # 清理内容（去除标记文本）
            content = re.sub(r'来源文件:\s*\S+', '', block)
            content = re.sub(r'相关度分数:\s*[\d.]+', '', content)
            content = content.strip()

            # 多分隔符切句，提取有效信息
            sentences = re.split(r'[。！？\n•·●#]+', content)
            key_sentences = [s.strip() for s in sentences if len(s.strip()) > 8]

            if key_sentences:
                answer_parts.append(f"{filename}：")
                for sentence in key_sentences[:3]:
                    answer_parts.append(f"  • {sentence}")
                answer_parts.append("")

        answer_parts.append("以上信息来自知识库检索结果，供参考。")
        return "\n".join(answer_parts)

    def _extract_question(self, prompt: str) -> str:
        """从 Prompt 模板中提取用户原始问题。"""
        markers = ["用户问题", "## User Question", "问题：", "Question:", "Human:"]
        for marker in markers:
            if marker in prompt:
                parts = prompt.split(marker, 1)
                if len(parts) > 1:
                    for line in parts[1].split("\n"):
                        q = line.strip()
                        if q and not q.startswith("#"):
                            return q
        # 兜底：取最后一行非空内容
        lines = [l.strip() for l in prompt.strip().split("\n") if l.strip()]
        return lines[-1] if lines else prompt[:100]

    def _extract_context(self, prompt: str) -> str:
        """从 Prompt 模板中提取知识库参考资料。"""
        markers = ["参考资料", "## Knowledge Base References", "Context:", "context:"]
        for marker in markers:
            if marker in prompt:
                parts = prompt.split(marker, 1)
                if len(parts) > 1:
                    # 上下文截止于下一个段落标题
                    end_markers = ["用户问题", "## User Question", "Question:", "## 回答"]
                    context = parts[1]
                    for em in end_markers:
                        if em in context:
                            context = context.split(em, 1)[0]
                    return context.strip()
        return ""

    def generate_with_tools(self, messages: list[dict], tools: list[dict],
                            system_prompt: str = "", **kwargs) -> dict:
        """Keyword matching for MockLLM to simulate function calling."""
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user": user_msg = m.get("content", ""); break
        import re
        kw_map = {
            "get_current_time": [
                "现在几点|当前时间|今天几号|几点了|时间是多少|现在时间|what time|current time|time.*now|what.*time"
            ],
            "get_city": [
                "哪个城市|所在城市|我在哪里|城市是哪里|what city|where am i|which city|my location|my city|北京|上海|深圳|哈尔滨|广州|杭州"
            ],
            "get_battery_temperature": [
                "电池.*温度|电池.*状态|实时温度|当前温度|电池.*多少度|battery.*temp|battery.*temperature|battery.*status|电池现在"
            ],
        }
        for tool_name, patterns in kw_map.items():
            for pat in patterns:
                if re.search(pat, user_msg, re.IGNORECASE):
                    td = next((t for t in tools if t.get("function", {}).get("name") == tool_name), None)
                    if td:
                        return {"answer": "", "tool_calls": [{"id": f"mock-{tool_name}", "name": tool_name, "args": {}}], "finish_reason": "tool_calls"}
        return {"answer": self._general_response(user_msg or "hello"), "tool_calls": [], "finish_reason": "stop"}

    def _general_response(self, question: str) -> str:
        """无上下文时的通用模板回复。"""
        q_lower = question.lower()

        if any(w in q_lower for w in ["你好", "hello", "hi"]):
            return "你好！我是企业级智能研发助手。可以提问知识库内容、上传文档分析、或生成报告。"

        if any(w in q_lower for w in ["帮助", "help", "功能"]):
            return ("我提供：1.知识库问答 2.文档总结 3.表格分析 4.报告生成 5.长期记忆。请上传文档开始使用。")

        return (
            f"收到问题：「{question[:50]}...」\n"
            "当前使用本地规则引擎（未连接大模型API）。\n"
            "配置 DEEPSEEK_API_KEY 到 .env 可获得 AI 智能回答。"
        )


# ── 全局单例 + 缓存管理 ──────────────────────────────────────────

_llm: Any = None


def get_llm():
    """获取 LLM 实例 —— 首次调用时根据环境变量决定用哪种实现。"""
    global _llm
    if _llm is None:
        from src.core.settings import has_deepseek_api_key
        if has_deepseek_api_key():
            from src.models.model_factory import create_chat_model
            _llm = create_chat_model()
        else:
            _llm = RuleBasedLLM()
    return _llm


def reset_llm() -> None:
    """清除 LLM 单例缓存 —— 用于 .env 变更后重新检测模型类型。"""
    global _llm
    _llm = None
    logger.info("LLM singleton reset")


def get_llm_provider_name(llm=None) -> str:
    """安全获取 provider 名称（不暴露 key）。"""
    if llm is None:
        llm = get_llm()
    return getattr(llm, 'provider_name', type(llm).__name__)


def get_llm_call_info(llm=None) -> dict:
    """获取最近一次 LLM 调用的状态信息。"""
    if llm is None:
        llm = get_llm()
    provider = get_llm_provider_name(llm)
    is_real = provider == "DeepSeekAdapter"
    return {
        "llm_provider": provider,
        "is_real_provider": is_real,
        "last_call_succeeded": getattr(llm, 'last_call_succeeded', None) if is_real else None,
        "last_error": getattr(llm, 'last_error', '') if is_real else '',
    }
