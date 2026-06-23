"""问答服务 — Agent 编排层的核心。

这是理解 Agentic RAG 工作流最重要的文件。

【完整执行流程】
  用户输入
  → QueryRouter.route()      —— 意图识别（正则 + LLM 语义兜底）
  → 按类型分流到对应处理函数：
      general_chat       → 直接 LLM（不走检索，省 Token）
      knowledge_qa       → RAG 检索 → context 注入 → LLM 增强回答
      table_analysis     → TableAnalysisTool（不消耗 LLM Token）
      report_generation  → RAG + 报告 Prompt → LLM
      memory_query       → 长期记忆检索 → LLM
      react_tools        → ReAct 工具循环（LLM 主动调用工具获取实时数据）
  → MemoryManager.process()  —— 从对话中抽取长期记忆
  → 返回结构化结果

【ReAct 改进 vs 旧版】
  旧版：工具结果以纯文本拼接到 history 字符串里
  新版：使用 OpenAI function calling 标准格式
    - assistant message 携带 tool_calls 数组
    - tool result 以 role=tool 消息发回
    - LLM 能更精准地理解工具结果，减少幻觉
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from src.agents.query_router import QueryRouter
from src.chains.llm_rag_chain import LLMRagChain, build_react_prompt, parse_react_tool_call
from src.memory.memory_manager import get_memory_manager
from src.models.model_factory import get_model_status
from src.rag.knowledge_base_service import get_kb_service
from src.tools.tool_registry import get_tool_registry

logger = logging.getLogger(__name__)

# ── 不需要知识库检索的问题类型 ──────────────────────────────────
PURE_CHAT_TYPES = {"general_chat", "memory_query"}

# ── 对话历史缓冲区 ────────────────────────────────────────────────
# key=conversation_id, value=最近 N 轮消息列表
# 让 LLM 能理解"那个"、"它"、"刚才"等指代，实现多轮对话
_conversation_buffers: dict[str, list[dict]] = {}
MAX_HISTORY_ROUNDS = 10


def clear_conversation(conversation_id: str = "default") -> None:
    """清空指定对话的上下文缓冲区（新话题开始时调用）。"""
    _conversation_buffers.pop(conversation_id, None)


def handle_chat(
    message: str,
    conversation_id: str | None = None,
    rag_mode: str = "auto",
) -> dict[str, Any]:
    """统一问答入口 —— FastAPI 端点和 Streamlit UI 的唯一调用点。

    Args:
        message: 用户输入的原始文本
        conversation_id: 对话标识，相同 ID 共享上下文历史
        rag_mode: "auto"（默认）/ "strict"（强制RAG）/ "off"（纯LLM）
    """
    t0 = time.time()
    cid = conversation_id or "default"
    buffer = _conversation_buffers.setdefault(cid, [])

    # ── Step 1: 注入对话历史（让 LLM 理解多轮上下文）──────────────
    contextualized = _inject_history(message, buffer)

    # ── Step 2: 意图路由（正则快速通道 + LLM 语义兜底）────────────
    route = QueryRouter().route(message)
    model_info = get_model_status()
    logger.info("Route: type=%s by=%s tools=%s", route.question_type, route.routed_by, route.needs_tools)

    # ── Step 3: 按意图类型分流到对应处理链路 ──────────────────────
    answer, sources, chain_result, retrieval_status, tools_used = _dispatch(
        message=message,
        contextualized=contextualized,
        route_type=route.question_type,
        needs_tools=route.needs_tools,
        rag_mode=rag_mode,
    )

    # ── Step 4: 长期记忆抽取（从本轮对话中学习）────────────────────
    # Agent 的"学习"能力：将有价值的信息保存到长期记忆，下次对话可以回忆
    try:
        get_memory_manager().process_conversation(message, answer, cid)
    except Exception as e:
        logger.warning("Memory extraction failed: %s", e)

    # ── Step 5: 更新对话缓冲区 ────────────────────────────────────
    buffer.append({"role": "user", "content": message})
    buffer.append({"role": "assistant", "content": answer[:500]})
    # 超过最大轮数时，删除最早的消息（滑动窗口）
    if len(buffer) > MAX_HISTORY_ROUNDS * 2:
        _conversation_buffers[cid] = buffer[-(MAX_HISTORY_ROUNDS * 2):]

    # ── Step 6: 持久化到 SQLite ───────────────────────────────────
    try:
        from src.database.sqlite_manager import get_db
        get_db().save_conversation(question=message, answer=answer,
                                   conversation_id=cid, latency_ms=0)
    except Exception:
        pass

    latency_ms = (time.time() - t0) * 1000

    return {
        "answer": answer,
        "sources": sources,
        "confidence": _confidence(retrieval_status, chain_result),
        "question_type": route.question_type,
        "routed_by": route.routed_by,
        "rag_mode": rag_mode,
        "retrieval_status": retrieval_status,
        "tools_used": tools_used,
        "latency_ms": round(latency_ms, 1),
        "evidence_count": len(sources),
        "needs_refusal": False,
        "model_type": model_info["model_type"],
        "llm_provider": chain_result.get("llm_provider", model_info["llm_provider"]),
        "llm_called": chain_result.get("llm_called", False),
        "real_llm_called": chain_result.get("real_llm_called", False),
        "real_llm_success": chain_result.get("real_llm_success", False),
        "prompt_preview": chain_result.get("prompt_preview", "")[:500],
        "react_steps": chain_result.get("react_steps", 0),
        "tool_logs": chain_result.get("tool_logs", []),
    }


def _dispatch(
    message: str,
    contextualized: str,
    route_type: str,
    needs_tools: list[str],
    rag_mode: str,
) -> tuple[str, list, dict, str, list[str]]:
    """按路由类型分发到对应的处理函数。

    返回: (answer, sources, chain_result, retrieval_status, tools_used)
    """
    # ── 表格分析（不消耗 LLM Token，直接调用 Python 工具）────────
    if route_type == "table_analysis":
        answer, sources, chain_result = _handle_table(message)
        return answer, sources, chain_result, "not_attempted", ["table_analysis"]

    # ── 图片理解 ─────────────────────────────────────────────────
    if route_type == "image_understanding":
        answer, sources, chain_result = _handle_image(message)
        return answer, sources, chain_result, "not_attempted", ["image_understanding"]

    # ── 报告生成（RAG + 报告 Prompt）──────────────────────────────
    if route_type == "report_generation":
        answer, sources, chain_result, status = _handle_report(message, rag_mode)
        return answer, sources, chain_result, status, ["report_generation"]

    # ── 记忆查询（从长期记忆检索，不走 RAG）──────────────────────
    if route_type == "memory_query":
        answer, sources, chain_result = _handle_memory(contextualized)
        return answer, sources, chain_result, "off", []

    # ── 闲聊（纯 LLM，不检索，省 Token）──────────────────────────
    if route_type == "general_chat":
        chain = LLMRagChain()
        chain_result = chain.invoke(user_prompt=contextualized, context="", mode="general")
        return chain_result["answer"], [], chain_result, "off", []

    # ── ReAct 工具调用（LLM 主动决定调用哪个工具）────────────────
    if route_type == "knowledge_qa" and "react_tools" in needs_tools:
        answer, sources, chain_result = _handle_react(message)
        return answer, sources, chain_result, "react_loop", ["react_tools"]

    # ── 知识问答 / 文档摘要 → RAG 增强（默认路径）────────────────
    answer, sources, chain_result, status = _handle_rag(contextualized, rag_mode)
    return answer, sources, chain_result, status, ["rag_search"]


# ════════════════════════════════════════════════════════════════════
#  各类型处理函数
# ════════════════════════════════════════════════════════════════════

def _handle_rag(message: str, rag_mode: str):
    """RAG 增强问答 —— 知识问答的核心流程。

    三步走：
      1. 检索：向量库中找到与问题最相关的文档片段（Evidence）
      2. 拼接：将检索结果格式化为 context 文本
      3. 增强：context 注入 LLM Prompt，让回答基于真实资料
    """
    kb = get_kb_service()

    if rag_mode == "off":
        chain_result = LLMRagChain().invoke(user_prompt=message, context="", mode="general")
        return chain_result["answer"], [], chain_result, "off"

    retrieval = kb.retrieve_context(message, prefer_content_type="text_knowledge")
    sources = retrieval["sources"]
    context = retrieval["context"]
    status = retrieval["retrieval_status"]

    if rag_mode == "strict" and not context:
        return (
            "当前知识库中没有找到足够相关的资料。请重新描述问题或上传相关文档。",
            [], {}, "empty",
        )

    mode = "strict" if rag_mode == "strict" else "chat"
    chain_result = LLMRagChain().invoke(user_prompt=message, context=context, mode=mode)
    return chain_result["answer"], sources, chain_result, status


def _handle_report(message: str, rag_mode: str):
    """报告生成：RAG 检索（取更多片段）→ 报告 Prompt → LLM。"""
    kb = get_kb_service()
    retrieval = kb.retrieve_context(message, top_k=8)
    sources = retrieval["sources"]
    context = retrieval["context"]
    status = retrieval["retrieval_status"]

    if rag_mode == "strict" and not context:
        return "知识库中无相关资料，无法生成报告。请上传文档或切换到 auto 模式。", [], {}, "empty"

    chain_result = LLMRagChain().invoke(
        user_prompt=message,
        context=context,
        mode="report",
        extra_vars={"topic": message, "report_type": "标准报告"},
    )
    return chain_result["answer"], sources, chain_result, status


def _handle_memory(message: str):
    """记忆查询：从长期记忆库检索相关记忆，作为 context 注入 LLM。"""
    memory = get_memory_manager()
    ctx = memory.get_context_for_query(message)
    mems = ctx.get("relevant_memories", [])
    mem_context = "\n".join(f"- {m['content'][:300]}" for m in mems[:5]) if mems else ""
    chain_result = LLMRagChain().invoke(user_prompt=message, context=mem_context, mode="memory")
    return chain_result["answer"], [], chain_result


def _handle_table(query: str):
    """表格分析：直接调用 TableAnalysisTool，不走 LLM。"""
    try:
        from src.tools.table_analysis_tool import TableAnalysisTool
        answer = TableAnalysisTool().analyze(query)
        return answer, [], {"llm_provider": "Tool", "llm_called": False}
    except Exception as e:
        return f"表格分析失败: {e}", [], {}


def _handle_image(query: str):
    """图片理解：调用 ImageUnderstandingTool（当前为 Mock 实现）。"""
    try:
        from src.tools.image_understanding_tool import ImageUnderstandingTool
        answer = ImageUnderstandingTool().understand(query)
        return answer, [], {"llm_provider": "Tool", "llm_called": False}
    except Exception as e:
        return f"图片分析失败: {e}", [], {}


# ════════════════════════════════════════════════════════════════════
#  ReAct 工具循环 —— Agent 的核心能力
# ════════════════════════════════════════════════════════════════════

def _handle_react(query: str, max_steps: int = 3):
    """LLM 驱动的 ReAct 工具调用循环。

    【ReAct 原理（Reason + Act）】
      每一步 LLM 都要做两件事：
        Reason（推理）：分析当前已知信息，判断是否需要更多数据
        Act（行动）：如果需要数据，输出 <tool> 标签调用工具；否则直接回答

    【改进 vs 旧版】
      旧版：工具结果拼接为字符串追加到 history
      新版：使用 OpenAI function calling 标准消息格式
        messages = [
          {"role": "user", ...},
          {"role": "assistant", "tool_calls": [...]},  ← LLM 的工具调用决策
          {"role": "tool", "content": "..."},           ← 工具执行结果
          ...
        ]
      DeepSeek 完全支持这个格式，LLM 能更准确地理解工具结果上下文。
    """
    from src.models.llm_service import get_llm
    from src.agents.middleware import wrap_tool_call

    llm = get_llm()
    registry = get_tool_registry()
    tool_logs: list[dict] = []
    called: set[str] = set()

    # ── 尝试 OpenAI function calling 格式（DeepSeek 支持）─────────
    # 如果 LLM 支持 generate_with_tools()，使用标准 function calling
    if hasattr(llm, "generate_with_tools"):
        return _handle_react_function_calling(query, llm, registry)

    # ── 降级：XML 标签格式（Mock LLM 或不支持 function calling 时）─
    history = ""
    final = ""

    for step in range(1, max_steps + 1):
        # 构建包含工具描述的 ReAct Prompt
        prompt = build_react_prompt(query, history)
        response = llm.generate(prompt)

        # 解析 LLM 是否输出了工具调用标签
        tool_call = parse_react_tool_call(response)

        if tool_call is None:
            # LLM 没有调用工具
            if step == 1 and not called:
                # 安全网：第一步且还没调用过任何工具时，用关键词兜底
                fallback_name = registry.keyword_fallback(query)
                if fallback_name:
                    result, lat = wrap_tool_call(fallback_name, registry.get(fallback_name).func)
                    called.add(fallback_name)
                    tool_logs.append({"tool": fallback_name, "args": {}, "latency_ms": lat, "output_preview": result[:200]})
                    history += f"\n[{fallback_name} 结果]:\n{result}\n请基于以上数据回答用户。\n"
                    continue
            # 没有工具调用 → LLM 认为已有足够信息，这就是最终答案
            final = response
            break

        tname = tool_call["name"]
        targs = tool_call.get("args", {})

        # 防止重复调用同一工具（避免 LLM 陷入循环）
        if tname in called:
            history += f"\n⚠️ 工具 '{tname}' 已经调用过，请直接用已有数据回答。\n"
            continue

        tool_entry = registry.get(tname)
        if tool_entry is None:
            history += f"\n⚠️ 工具 '{tname}' 不存在，可用工具: {registry.names()}\n"
            continue

        # 执行工具，记录耗时
        called.add(tname)
        result, lat = wrap_tool_call(tname, tool_entry.func, **targs)
        tool_logs.append({"tool": tname, "args": targs, "latency_ms": lat, "output_preview": result[:200]})

        # 工具结果追加到 history，供下一步 LLM 使用
        history += f"\n[{tname} 结果]:\n{result}\n"
        history += "（如果数据已充足，请直接回答；如需更多数据，输出一个 <tool> 标签。）\n"

    # 超过最大步数，强制生成最终答案
    if not final:
        history += "\n已达到最大工具调用次数，请根据已收集的数据给出最终答案。\n"
        final = llm.generate(build_react_prompt(query, history))

    if not final:
        final = "无法从可用数据中确定答案。"

    sources = [
        {"doc_id": f"tool-{t['tool']}", "filename": f"[Tool] {t['tool']}",
         "chunk_id": f"tool-{i}", "score": 1.0,
         "preview": t["output_preview"], "content": t["output_preview"],
         "content_type": "tool_output"}
        for i, t in enumerate(tool_logs)
    ]
    return final, sources, {
        "llm_provider": type(llm).__name__,
        "llm_called": True,
        "react_steps": len(tool_logs),
        "tool_logs": tool_logs,
    }


def _handle_react_function_calling(query: str, llm, registry):
    """使用 OpenAI function calling 标准格式执行 ReAct 循环。

    【标准格式说明】
      这是工业级 Agent 的标准工具调用方式：
      1. 把工具定义以 JSON Schema 发给 LLM（tools 参数）
      2. LLM 返回 tool_calls（结构化的工具调用决策，不是文本）
      3. 执行工具，把结果以 role=tool 消息追加到 messages
      4. 再次调用 LLM，直到 LLM 不再输出 tool_calls（有了最终答案）

    优点：
      - LLM 不需要生成特定格式的文本（如 <tool> 标签），减少格式错误
      - 工具参数以 JSON 结构返回，不需要解析字符串
      - LLM 理解工具结果更准确（role=tool 有明确的语义标记）
    """
    from src.agents.middleware import wrap_tool_call

    tool_schemas = registry.build_openai_schemas()
    tool_logs: list[dict] = []
    called: set[str] = set()

    # 初始消息列表（OpenAI 标准格式）
    messages = [{"role": "user", "content": query}]
    system_prompt = "你是具有工具调用能力的BMS研发专家智能体。需要实时数据时请调用工具。"

    for step in range(1, 4):  # 最多 3 轮工具调用
        result = llm.generate_with_tools(
            messages=messages,
            tools=tool_schemas,
            system_prompt=system_prompt,
        )

        tool_calls = result.get("tool_calls", [])

        if not tool_calls:
            # LLM 没有调用工具 → 已有最终答案
            final = result.get("answer", "")
            break

        # 把 LLM 的工具调用决策追加到消息历史
        # （assistant 角色，包含 tool_calls 数组）
        messages.append({
            "role": "assistant",
            "content": result.get("answer") or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["args"], ensure_ascii=False)},
                }
                for tc in tool_calls
            ],
        })

        # 执行所有工具，把结果追加到消息历史
        for tc in tool_calls:
            tname = tc["name"]
            targs = tc.get("args", {})
            call_id = tc.get("id", f"call_{tname}")

            if tname in called:
                tool_result = f"⚠️ 工具 '{tname}' 已调用过"
            else:
                entry = registry.get(tname)
                if entry:
                    called.add(tname)
                    tool_result, lat = wrap_tool_call(tname, entry.func, **targs)
                    tool_logs.append({"tool": tname, "args": targs, "latency_ms": lat, "output_preview": tool_result[:200]})
                else:
                    tool_result = f"⚠️ 工具 '{tname}' 不存在"

            # role=tool 消息：将工具结果结构化地反馈给 LLM
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": tool_result,
            })
    else:
        # 循环正常结束（超过最大步数）
        final = result.get("answer", "已完成工具调用，请查看上述结果。")

    sources = [
        {"doc_id": f"tool-{t['tool']}", "filename": f"[Tool] {t['tool']}",
         "chunk_id": f"tool-{i}", "score": 1.0,
         "preview": t["output_preview"], "content": t["output_preview"],
         "content_type": "tool_output"}
        for i, t in enumerate(tool_logs)
    ]
    return final, sources, {
        "llm_provider": type(llm).__name__,
        "llm_called": True,
        "real_llm_called": True,
        "react_steps": len(tool_logs),
        "tool_logs": tool_logs,
    }


# ════════════════════════════════════════════════════════════════════
#  辅助函数
# ════════════════════════════════════════════════════════════════════

def _inject_history(user_message: str, history: list[dict]) -> str:
    """把历史对话注入当前 Prompt，让 LLM 理解多轮上下文。

    例如：
      用户先问："现在几点？" → LLM 回答了时间
      用户再问："那明天呢？" → 没有历史的 LLM 不知道"明天"指什么
      注入历史后 → LLM 知道这是关于时间的追问
    """
    if not history:
        return user_message

    parts = ["[对话上下文（帮助理解「明天」「它」「那个」等指代）]"]
    for msg in history[-8:]:  # 最近 4 轮（8 条消息）
        role = "User" if msg["role"] == "user" else "Assistant"
        parts.append(f"{role}: {msg['content'][:300]}")
    parts.append(f"\n[当前问题]: {user_message}")
    return "\n".join(parts)


def _confidence(retrieval_status: str, chain: dict) -> str:
    """根据检索状态和 LLM 调用结果评估回答置信度。"""
    if retrieval_status == "used" and chain.get("real_llm_success"):
        return "high"
    elif retrieval_status in ("used", "react_loop"):
        return "medium"
    return "medium"
