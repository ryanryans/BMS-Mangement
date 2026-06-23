"""统一工具注册表 — Agent 工具系统的核心。

【学习要点】为什么需要工具注册表？

旧做法（坏）：
  工具描述硬写在 ReAct System Prompt 字符串里。
  加一个新工具 → 要改 prompt 字符串 + 改 chat_service.py + 改路由规则 → 容易漏改。

新做法（好）：
  所有工具在这里集中注册，包含：函数引用、描述、参数说明、示例触发词。
  ReAct Prompt 自动从注册表生成工具描述 → 加工具只改这一个文件。

这个模式参考了工业级 Agent 框架（如 claw-code 的 tools_snapshot.json），
核心思想：数据驱动，而不是代码硬编码。

注册新工具的步骤：
  1. 在 src/tools/ 下写好工具函数
  2. 在本文件的 _build_registry() 中加一条 ToolEntry
  3. 完成 —— ReAct Prompt、工具执行、Schema 全部自动更新
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ── 工具定义数据结构 ─────────────────────────────────────────────

@dataclass
class ToolParam:
    """工具参数描述。"""
    name: str          # 参数名
    type: str          # 类型: string / number / boolean
    description: str   # 参数说明
    required: bool = True
    default: Any = None


@dataclass
class ToolEntry:
    """单个工具的完整定义。

    包含运行所需的一切：函数引用、自然语言描述、参数定义、触发关键词。
    """
    name: str                       # 工具名（唯一标识）
    func: Callable                  # Python 函数引用
    description: str                # 给 LLM 看的工具说明（中文，自然语言）
    params: list[ToolParam]         # 参数列表
    trigger_keywords: list[str]     # 关键词兜底匹配（LLM 判断失败时的安全网）
    category: str = "general"       # 工具分类，便于分组展示


# ════════════════════════════════════════════════════════════════════
#  工具注册表实现
# ════════════════════════════════════════════════════════════════════

class ToolRegistry:
    """工具注册表 — 统一管理所有 Agent 工具。

    职责：
      - 存储工具定义（ToolEntry）
      - 生成 ReAct System Prompt 的工具描述文本
      - 生成 OpenAI function calling 的 JSON Schema
      - 提供工具函数执行入口
      - 关键词兜底匹配（LLM 漏调时的安全网）
    """

    def __init__(self):
        self._tools: dict[str, ToolEntry] = {}

    def register(self, entry: ToolEntry) -> None:
        """注册单个工具。"""
        self._tools[entry.name] = entry
        logger.debug("Tool registered: %s", entry.name)

    def get(self, name: str) -> ToolEntry | None:
        """按名称获取工具。"""
        return self._tools.get(name)

    def names(self) -> list[str]:
        """所有工具名列表。"""
        return list(self._tools.keys())

    def execute(self, name: str, args: dict[str, Any]) -> str:
        """执行工具并返回字符串结果。

        【设计原则】工具总返回字符串，方便直接拼入 LLM 对话历史。
        """
        entry = self._tools.get(name)
        if entry is None:
            return f"[ERROR] 工具 '{name}' 不存在。可用工具: {self.names()}"
        try:
            # 只传工具声明的参数，过滤多余字段
            valid_args = {k: v for k, v in args.items()
                          if any(p.name == k for p in entry.params)}
            result = entry.func(**valid_args)
            return str(result)
        except Exception as e:
            logger.error("Tool '%s' failed: %s", name, e)
            return f"[ERROR] 工具 '{name}' 执行失败: {type(e).__name__}: {e}"

    # ── Prompt 生成 ─────────────────────────────────────────────

    def build_react_tool_description(self) -> str:
        """为 ReAct System Prompt 生成工具描述文本。

        生成格式（LLM 友好的自然语言列表）：
          1. get_current_time — 获取当前时间
             触发场景: 现在几点、今天几号 ...
             调用格式: <tool name="get_current_time"/>
             参数: 无
        """
        if not self._tools:
            return "（暂无可用工具）"

        lines = ["可用工具列表（每次只调用一个）：\n"]
        for i, (name, entry) in enumerate(self._tools.items(), 1):
            # 工具标题
            lines.append(f"{i}. **{name}** — {entry.description}")
            # 触发关键词
            kws = "、".join(entry.trigger_keywords[:5]) if entry.trigger_keywords else "（无）"
            lines.append(f"   触发场景: {kws}")
            # 调用格式
            if entry.params:
                param_example = " ".join(f'{p.name}=值' for p in entry.params if p.required)
                lines.append(f'   调用格式: <tool name="{name}">{param_example}</tool>')
            else:
                lines.append(f'   调用格式: <tool name="{name}"/>')
            # 参数说明
            if entry.params:
                for p in entry.params:
                    req = "必填" if p.required else f"可选，默认={p.default}"
                    lines.append(f"   参数: {p.name}（{p.type}，{req}）— {p.description}")
            else:
                lines.append("   参数: 无")
            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def build_openai_schemas(self) -> list[dict]:
        """生成 OpenAI function calling 的 JSON Schema 列表。

        这是工业级 Agent 的标准工具调用格式。
        LLM 在 API 层面直接返回结构化的工具调用决策，
        不需要解析 XML 标签，更可靠、更准确。

        格式参考：https://platform.openai.com/docs/guides/function-calling
        """
        schemas = []
        for name, entry in self._tools.items():
            properties = {}
            required = []
            for p in entry.params:
                properties[p.name] = {
                    "type": p.type,
                    "description": p.description,
                }
                if p.default is not None:
                    properties[p.name]["default"] = p.default
                if p.required:
                    required.append(p.name)

            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": entry.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })
        return schemas

    def keyword_fallback(self, query: str) -> str | None:
        """关键词兜底匹配 — LLM 没有调用工具时的安全网。

        只在第一步且没有任何工具被调用时触发。
        遍历所有工具的 trigger_keywords，返回第一个命中的工具名。
        """
        import re
        query_lower = query.lower()
        for name, entry in self._tools.items():
            for kw in entry.trigger_keywords:
                if re.search(re.escape(kw.lower()), query_lower):
                    logger.info("Keyword fallback matched: query='%s' → tool='%s'", query[:30], name)
                    return name
        return None


# ════════════════════════════════════════════════════════════════════
#  注册所有工具（在这里统一管理）
# ════════════════════════════════════════════════════════════════════

def _build_registry() -> ToolRegistry:
    """构建并返回注册了所有工具的注册表实例。

    【如何添加新工具】
      1. 在 src/tools/ 写好工具函数（返回 str）
      2. 在这里 import 并添加 ToolEntry
      3. 完成，无需修改其他任何文件
    """
    from src.tools.time_tools import get_current_time, get_city
    from src.tools.battery_status_tool import get_battery_temperature

    registry = ToolRegistry()

    # ── 工具1: 获取当前时间 ──────────────────────────────────────
    registry.register(ToolEntry(
        name="get_current_time",
        func=get_current_time,
        description="获取当前的日期、时间和星期信息",
        params=[],  # 无参数
        trigger_keywords=["现在几点", "当前时间", "今天几号", "几点了", "时间是",
                          "今天是几号", "星期几", "what time", "what date", "current time"],
        category="system",
    ))

    # ── 工具2: 获取城市环境信息 ──────────────────────────────────
    registry.register(ToolEntry(
        name="get_city",
        func=get_city,
        description="获取指定城市的环境信息（温度、湿度）及电池使用建议",
        params=[
            ToolParam(
                name="city",
                type="string",
                description="城市名称，如 北京、深圳、哈尔滨。不指定则返回默认城市。",
                required=False,
                default="default",
            )
        ],
        trigger_keywords=["哪个城市", "我在哪", "城市温度", "城市环境",
                          "what city", "where am i", "my location"],
        category="system",
    ))

    # ── 工具3: 获取电池实时数据 ──────────────────────────────────
    registry.register(ToolEntry(
        name="get_battery_temperature",
        func=get_battery_temperature,
        description="获取电池组各电芯的实时温度、电压数据及告警状态",
        params=[],  # 无必填参数
        trigger_keywords=["电池温度", "电池状态", "电芯温度", "电芯电压",
                          "电池多热", "电池健康", "battery temp", "battery status", "battery voltage"],
        category="battery",
    ))

    # ── 添加更多工具时在此处继续 register ────────────────────────

    return registry


# ── 全局单例（整个应用共用一个注册表实例）────────────────────────

_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例。整个应用生命周期只初始化一次。"""
    global _registry
    if _registry is None:
        _registry = _build_registry()
        logger.info("ToolRegistry initialized with %d tools: %s",
                    len(_registry.names()), _registry.names())
    return _registry


def reset_tool_registry() -> None:
    """重置注册表单例（测试场景使用）。"""
    global _registry
    _registry = None
