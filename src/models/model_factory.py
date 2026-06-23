"""模型工厂 — Agent 系统中"模型选择"的核心。

学习要点：
  1. 工厂模式：根据环境变量动态选择 LLM 实现
  2. OpenAI 兼容协议：DeepSeekAdapter 通过 OpenAI SDK 调用任何兼容 API
  3. 错误处理：LLMCallError 自定义异常 + last_error 追踪
  4. 安全：get_model_status() 只返回状态，不泄露 API Key
"""
from __future__ import annotations

import logging
import os
from typing import Any

from src.core.settings import get_settings, has_deepseek_api_key

logger = logging.getLogger(__name__)


class LLMCallError(Exception):
    """真实 LLM API 调用失败时抛出的异常（不包含 API Key）。"""


class DeepSeekAdapter:
    """DeepSeek API 适配器 — 通过 OpenAI 兼容协议调用。

    为什么叫"适配器"（Adapter）？
    — 它把 DeepSeek 的 API 适配成项目内部的 LLMProvider 接口
    — 未来换其他模型（Qwen、GPT-4、Claude），只需写新的 Adapter
    — 业务代码完全不用改

    状态追踪：
    — last_error: 最后一次错误信息
    — last_call_succeeded: 最后一次调用是否成功
    — 这些字段让上层能区分"调用了Mock"和"调用了真实API但失败"
    """

    def __init__(self):
        settings = get_settings()
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is not set")

        self.last_error: str = ""
        self.last_call_succeeded: bool = False
        self._model = settings.chat_model_name
        self._available = False

        try:
            # OpenAI SDK 可以调用任何兼容 OpenAI 协议的服务
            # (DeepSeek, SiliconFlow, 智谱, 通义千问...)
            from openai import OpenAI
            self._client = OpenAI(
                api_key=api_key,
                base_url=settings.deepseek_base_url,
            )
            self._available = True
            logger.info("DeepSeekAdapter ready: model=%s", self._model)
        except ImportError:
            self.last_error = "openai package not installed"
        except Exception as e:
            self.last_error = f"Init failed: {type(e).__name__}"

    @property
    def provider_name(self) -> str:
        return "DeepSeekAdapter"

    @property
    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        """调用 DeepSeek API 生成回复（阻塞模式，等待完整结果）。

        失败时返回空字符串，让上层能区分正常输出和错误。
        """
        self.last_call_succeeded = False
        self.last_error = ""

        if not self._available:
            self.last_error = "DeepSeekAdapter not available"
            return ""

        system = system_prompt or "你是一个严谨的企业级知识库助手。"

        try:
            # OpenAI Chat Completions API 标准调用
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},   # 系统身份
                    {"role": "user", "content": prompt},      # 用户 prompt
                ],
                temperature=kwargs.get("temperature", 0.3),   # 0=确定性高, 1=创意高
                max_tokens=kwargs.get("max_tokens", 2048),
            )
            content = response.choices[0].message.content or ""
            self.last_call_succeeded = True
            return content
        except Exception as e:
            self.last_error = f"API call failed: {type(e).__name__}"
            logger.error("DeepSeek API call failed: %s", type(e).__name__)
            return ""

    def stream_generate(self, prompt: str, system_prompt: str = "", **kwargs):
        """流式生成 —— 逐 token 输出，用户不需要等待完整答案。

        【学习要点】什么是流式输出？
          普通模式：等 LLM 生成完全部内容后一次性返回（可能等 10-30 秒）
          流式模式：LLM 每生成一个 token（约1-2个字）就立即推送给前端
          用户体验：像打字机一样逐字出现，感觉快很多

        【技术实现】
          使用 Python 生成器（generator），调用方用 for chunk in stream_generate(...) 接收
          配合 FastAPI 的 StreamingResponse + Server-Sent Events (SSE) 推送到前端

        Yields:
            str: 每次 yield 一个文本片段（通常是1-4个字符）
        """
        if not self._available:
            yield "[ERROR] DeepSeekAdapter not available"
            return

        system = system_prompt or "你是一个严谨的企业级知识库助手。"

        try:
            # stream=True 开启流式模式
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=kwargs.get("temperature", 0.3),
                max_tokens=kwargs.get("max_tokens", 2048),
                stream=True,   # 关键：开启流式
            )
            for chunk in stream:
                # 每个 chunk 可能包含 delta（增量文本）
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
            self.last_call_succeeded = True
        except Exception as e:
            self.last_error = f"Stream failed: {type(e).__name__}"
            logger.error("DeepSeek stream failed: %s", type(e).__name__)
            yield f"[ERROR] 流式生成失败: {type(e).__name__}"

    def generate_with_tools(self, messages: list[dict], tools: list[dict],
                            system_prompt: str = "", **kwargs) -> dict:
        """OpenAI function calling. Falls back to plain generate() on any error."""
        import json
        self.last_call_succeeded = False; self.last_error = ""
        if not self._available:
            return {"answer": "", "tool_calls": [], "finish_reason": "error"}

        # First try without tools (safer, always works)
        if not tools:
            try:
                answer = self.generate(
                    prompt=messages[-1].get("content", "") if messages else "",
                    system_prompt=system_prompt)
                return {"answer": answer, "tool_calls": [], "finish_reason": "stop"}
            except Exception:
                return {"answer": "", "tool_calls": [], "finish_reason": "error"}

        system = system_prompt or "You are a BMS expert."
        full_msgs = [{"role": "system", "content": system}] + messages
        try:
            resp = self._client.chat.completions.create(model=self._model, messages=full_msgs,
                tools=tools, tool_choice="auto",
                temperature=kwargs.get("temperature", 0.3), max_tokens=kwargs.get("max_tokens", 2048))
            msg = resp.choices[0].message; self.last_call_succeeded = True
            tcs = []
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    args = {}
                    try: args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError: pass
                    tcs.append({"id": tc.id, "name": tc.function.name, "args": args})
            return {"answer": msg.content or "", "tool_calls": tcs, "finish_reason": resp.choices[0].finish_reason or "stop"}
        except Exception as e:
            # Function calling failed -> fall back to plain generate()
            self.last_error = f"Function calling failed ({type(e).__name__}), falling back to plain LLM"
            logger.warning(self.last_error)
            try:
                answer = self.generate(
                    prompt=messages[-1].get("content", "") if messages else "",
                    system_prompt=system_prompt)
                return {"answer": answer, "tool_calls": [], "finish_reason": "stop_fallback"}
            except Exception:
                return {"answer": f"API调用失败: {type(e).__name__}", "tool_calls": [], "finish_reason": "error"}


def create_chat_model() -> Any:
    """工厂函数：根据环境变量选择 LLM 实现。

    有真实 key → DeepSeekAdapter
    无 key  → RuleBasedLLM（本地规则引擎）
    """
    from src.models.llm_service import RuleBasedLLM

    if has_deepseek_api_key():
        try:
            adapter = DeepSeekAdapter()
            if adapter.is_available:
                return adapter
        except Exception as e:
            logger.info("Falling back to RuleBasedLLM: %s", e)

    return RuleBasedLLM()


def get_model_status() -> dict:
    """获取模型状态（安全：不泄露 API Key 内容）。

    返回字典供前端展示和诊断使用。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    key_exists = bool(api_key)
    is_placeholder = "your_deepseek_api_key_here" in api_key
    has_real = has_deepseek_api_key()

    status = {
        "model_type": "MockLLM",
        "model_name": "RuleBasedLLM",
        "llm_provider": "RuleBasedLLM",
        "is_mock": True,
        "deepseek_key_present": has_real,
        "deepseek_key_exists": key_exists,
        "deepseek_key_placeholder": is_placeholder,
        "status": "MockLLM mode - configure DEEPSEEK_API_KEY in .env for real model",
    }

    if has_real:
        try:
            from openai import OpenAI
            status["model_type"] = "DeepSeekAdapter"
            status["llm_provider"] = "DeepSeekAdapter"
            status["is_mock"] = False
            status["model_name"] = os.getenv("CHAT_MODEL_NAME", "deepseek-chat")
            status["status"] = "Real LLM mode (DeepSeekAdapter ready)"
        except ImportError:
            status["model_type"] = "MockLLM (openai not installed)"
            status["status"] = "Real key set but openai package not installed"

    return status
