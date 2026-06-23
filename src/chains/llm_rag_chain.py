"""LLM RAG Chain — Agent 开发中 "Chain" 概念的轻量实现。

【学习要点】什么是 Chain？
  LangChain 中最基础的概念：把多个步骤串联成一条流水线：
    prompt_template | model | output_parser

  这里的 LLMRagChain 是同样的思想，自主实现，更透明易懂：
    用户问题 + 知识库上下文 → 填充 Prompt 模板 → 调用 LLM → 返回结构化结果

【重要改进 vs 旧版】
  旧版：提示词硬编码在 Python 字符串里
  新版：从 config/prompt_templates.yaml 加载 → 改提示词不用动代码

  旧版：ReAct 工具描述硬写在字符串里
  新版：从 ToolRegistry 动态生成 → 加工具不用动 Chain
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.models.llm_service import get_llm, get_llm_provider_name, get_llm_call_info
from src.utils.config_handler import get_prompt_templates

logger = logging.getLogger(__name__)


# ── 提示词加载（从 YAML 统一管理，不再硬编码在这里）──────────────

def _get_template(section: str, key: str) -> str:
    """从 prompt_templates.yaml 加载指定模板。加载失败时返回内置兜底模板。"""
    try:
        tpl = get_prompt_templates()
        return tpl[section][key]["content"]
    except (KeyError, TypeError) as e:
        logger.warning("Prompt template [%s][%s] not found: %s, using fallback", section, key, e)
        return _FALLBACK_TEMPLATES.get(f"{section}.{key}", "{user_prompt}\n\n{context}")


# 兜底模板（YAML 加载失败时使用，避免服务崩溃）
_FALLBACK_TEMPLATES = {
    "system.bms_expert": (
        "你是一名企业级电池管理系统（BMS）研发专家，"
        "专注于电池材料、BMS架构、SOC/SOH算法、热管理和安全工程。"
    ),
    "chat.rag_enhanced": (
        "你是一名企业级智能研发助手。\n\n"
        "## 用户问题\n{user_prompt}\n\n"
        "## 知识库参考资料\n{context}\n\n"
        "请基于参考资料回答问题，资料为空时基于专业知识回答，不要拒答。"
    ),
    "report.standard": (
        "你是报告专家。\n\n## 主题\n{topic}\n\n## 类型\n{report_type}\n\n"
        "## 参考\n{context}\n\n请生成完整报告。"
    ),
}


class LLMRagChain:
    """统一 LLM 调用链 —— 从 Prompt 模板到 LLM 输出的完整流程。

    使用方式：
        chain = LLMRagChain()
        result = chain.invoke(user_prompt="锂电池低温充电风险？", context="【来源1】...")
        print(result["answer"])

    支持的 mode（对应 prompt_templates.yaml 中的不同模板）：
        chat    → chat.rag_enhanced（默认，RAG增强问答）
        strict  → chat.strict_rag（严格RAG，无资料则拒答）
        report  → report.standard（报告生成）
        general → chat.general（纯LLM，不走RAG）
        memory  → chat.rag_enhanced（用记忆上下文替代知识库上下文）
    """

    def __init__(self, llm=None):
        # 依赖注入：允许外部传入 LLM 实例，方便测试时替换 Mock
        self.llm = llm or get_llm()

    def invoke(
        self,
        user_prompt: str,
        context: str = "",
        mode: str = "chat",
        extra_vars: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """执行一次完整的 LLM 调用。

        流程：
          1. 按 mode 从 YAML 选择对应模板
          2. 填充占位符 {user_prompt} {context} 等
          3. 拼接系统身份（System Prompt）
          4. 调用 LLM
          5. 返回结构化结果（answer + 诊断信息）

        Args:
            user_prompt: 用户的原始问题或经历史注入处理后的问题
            context: 知识库检索结果或记忆上下文，空字符串=纯LLM模式
            mode: 选择哪套提示词模板
            extra_vars: 报告生成等场景需要的额外模板变量（如 topic, report_type）
        """
        has_context = bool(context.strip())

        # 1. 选择提示词模板
        template = self._select_template(mode)
        system_prompt = _get_template("system", "bms_expert")

        # 2. 填充模板变量
        fmt_vars: dict[str, str] = {
            "user_prompt": user_prompt,
            "context": context if has_context else "（当前知识库暂无相关资料）",
            "mode": mode,
            # 报告模式的额外变量
            "topic": user_prompt,
            "report_type": "标准报告",
        }
        if extra_vars:
            fmt_vars.update(extra_vars)

        try:
            user_part = template.format(**fmt_vars)
        except KeyError as e:
            # 模板变量缺失时，用原始问题兜底（不崩溃）
            logger.warning("Template formatting failed (missing key %s), using raw prompt", e)
            user_part = user_prompt

        # 3. 拼接完整 Prompt（System 身份 + 用户模板）
        full_prompt = f"{system_prompt}\n\n{user_part}"

        # 4. 调试日志（查看实际发给 LLM 的内容）
        logger.debug("Prompt: %d chars, mode=%s, has_context=%s", len(full_prompt), mode, has_context)

        # 5. 调用 LLM
        try:
            answer = self.llm.generate(full_prompt, system_prompt=system_prompt)
        except TypeError:
            # RuleBasedLLM 不支持 system_prompt 参数，降级调用
            answer = self.llm.generate(full_prompt)

        # 6. 收集调用信息（供前端展示）
        provider = get_llm_provider_name(self.llm)
        llm_info = get_llm_call_info(self.llm)

        return {
            "answer": answer,
            "prompt_preview": full_prompt[:500],
            "llm_provider": provider,
            "has_context": has_context,
            "llm_called": True,
            "real_llm_called": provider == "DeepSeekAdapter",
            "real_llm_success": (
                provider == "DeepSeekAdapter"
                and llm_info.get("last_call_succeeded") is not False
            ),
            "mode": mode,
        }

    @staticmethod
    def _select_template(mode: str) -> str:
        """按 mode 选择对应的提示词模板。"""
        mapping = {
            "chat": ("chat", "rag_enhanced"),
            "strict": ("chat", "strict_rag"),
            "report": ("report", "standard"),
            "general": ("chat", "general"),
            "memory": ("chat", "rag_enhanced"),  # 记忆查询复用 RAG 模板，context 换成记忆
        }
        section, key = mapping.get(mode, ("chat", "rag_enhanced"))
        return _get_template(section, key)


# ════════════════════════════════════════════════════════════════════
#  ReAct Prompt 构建（动态注入工具描述，不再硬编码工具列表）
# ════════════════════════════════════════════════════════════════════

def build_react_prompt(user_message: str, history: str = "") -> str:
    """构建 ReAct 对话 Prompt。

    【改进 vs 旧版】
      旧版：工具描述硬写在这个函数里，加工具必须修改这里
      新版：从 ToolRegistry 动态生成工具描述，加工具只改 tool_registry.py

    【ReAct 原理】
      LLM 读取工具描述后，在每一步自主决定：
        a) 调用哪个工具获取数据，或
        b) 已有足够信息，直接回答用户
      这就是 ReAct（Reason + Act）的核心思想。
    """
    # 从注册表动态获取工具描述（新工具自动出现在 Prompt 里）
    from src.tools.tool_registry import get_tool_registry
    registry = get_tool_registry()
    tool_desc = registry.build_react_tool_description()

    # 加载 ReAct 系统提示（从 YAML）
    try:
        header_tpl = _get_template("react", "system_header")
        system_part = header_tpl.format(tool_descriptions=tool_desc)
    except Exception:
        system_part = f"你是具有工具调用能力的BMS研发专家智能体。\n\n{tool_desc}"

    rules = _get_template("react", "tool_call_rules")

    return (
        system_part
        + "\n\n" + rules
        + (f"\n\n## 对话历史\n{history}" if history else "")
        + f"\n\n用户问题：{user_message}"
        + "\n\n请决定：需要调用工具获取实时数据，还是直接基于已有知识回答？"
    )


def parse_react_tool_call(text: str) -> dict | None:
    """从 LLM 输出的文本中解析工具调用标签。

    支持格式：
      <tool name="get_current_time"/>            （无参数）
      <tool name="get_city">city=深圳</tool>     （有参数）

    返回：
      {"name": "get_city", "args": {"city": "深圳"}} 或 None（未找到）
    """
    m = re.search(r'<tool\s+name="([^"]+)"(?:\s*/>|>(.*?)</tool>)', text, re.DOTALL)
    if not m:
        return None

    name = m.group(1)
    args_str = (m.group(2) or "").strip()
    args: dict[str, str] = {}

    if args_str:
        for part in args_str.split():
            if "=" in part:
                k, _, v = part.partition("=")
                args[k.strip()] = v.strip().strip("'\"")

    return {"name": name, "args": args}


# ── 全局单例 ─────────────────────────────────────────────────────

_chain: LLMRagChain | None = None


def get_chain() -> LLMRagChain:
    """获取 LLMRagChain 单例。"""
    global _chain
    if _chain is None:
        _chain = LLMRagChain()
    return _chain
