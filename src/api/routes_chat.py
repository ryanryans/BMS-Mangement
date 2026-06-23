"""Chat 端点 —— 普通问答 + 流式问答（SSE）。

【学习要点】Server-Sent Events (SSE) 是什么？
  浏览器/客户端发起一次 HTTP 请求，服务器持续推送数据流，
  直到服务器主动关闭连接。适合 LLM 流式输出这种"一问多答"场景。

  与 WebSocket 的区别：
    SSE：单向（服务器→客户端），更简单，适合只需要推送的场景
    WebSocket：双向，适合需要双向通信的场景（如实时聊天室）

  前端使用方式（JavaScript）：
    const es = new EventSource('/chat/stream?message=你好');
    es.onmessage = (e) => { console.log(e.data); };  // 逐块接收

  Python 客户端（httpx）：
    import httpx
    with httpx.stream("POST", "/chat/stream", json={"message": "..."}) as r:
        for chunk in r.iter_text():
            print(chunk, end="", flush=True)
"""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.api.responses import success_response
from src.api.schemas import ApiResponse, ChatData, ChatRequest
from src.services.chat_service import handle_chat

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ApiResponse)
def chat(request: ChatRequest) -> dict:
    """普通问答接口（阻塞模式，等待完整结果）。"""
    result = handle_chat(request.message, request.conversation_id)
    data = ChatData(
        answer=result["answer"],
        conversation_id=request.conversation_id,
        question_type=result["question_type"],
        sources=result["sources"],
        confidence=result["confidence"],
        tools_used=result["tools_used"],
        latency_ms=result["latency_ms"],
        evidence_count=result["evidence_count"],
        needs_refusal=result["needs_refusal"],
        model_type=result["model_type"],
        llm_called=result.get("llm_called", False),
        prompt_preview=result.get("prompt_preview", ""),
    )
    return success_response("Chat completed.", data.model_dump())


@router.post("/chat/stream")
def chat_stream(request: ChatRequest):
    """流式问答接口 —— 逐 token 实时推送，用户不需要等待完整答案。

    响应格式（Server-Sent Events）：
      data: {"type": "token", "content": "你"}
      data: {"type": "token", "content": "好"}
      data: {"type": "done", "question_type": "general_chat", "latency_ms": 123}

    【设计说明】
      先做 RAG 检索（快，通常 <100ms）获取 context，
      再用流式模式调用 LLM（慢，逐 token 推送）。
      这样用户几乎感受不到等待，就开始看到回答了。
    """
    import time
    from src.agents.query_router import QueryRouter
    from src.rag.knowledge_base_service import get_kb_service
    from src.models.llm_service import get_llm
    from src.utils.config_handler import get_prompt_templates

    def event_stream():
        t0 = time.time()
        message = request.message

        # Step 1: 路由（快速，正则匹配）
        route = QueryRouter().route(message)

        # Step 2: RAG 检索（比 LLM 快很多）
        context = ""
        if route.needs_rag:
            try:
                retrieval = get_kb_service().retrieve_context(message)
                context = retrieval.get("context", "")
            except Exception:
                pass

        # Step 3: 构建 Prompt
        try:
            tpl = get_prompt_templates()
            template = tpl["chat"]["rag_enhanced"]["content"]
            system = tpl["system"]["bms_expert"]["content"]
            prompt = template.format(
                user_prompt=message,
                context=context if context else "（当前知识库暂无相关资料）",
            )
        except Exception:
            prompt = message
            system = ""

        # Step 4: 流式生成 + SSE 推送
        llm = get_llm()
        if hasattr(llm, "stream_generate"):
            # 真实 LLM：逐 token 流式推送
            for token in llm.stream_generate(prompt, system_prompt=system):
                # SSE 格式：每行以 "data: " 开头，以 "\n\n" 结束
                payload = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        else:
            # Mock LLM：一次性生成后模拟流式推送
            full = llm.generate(prompt)
            for char in full:
                payload = json.dumps({"type": "token", "content": char}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

        # 推送完成事件（携带元数据）
        done_payload = json.dumps({
            "type": "done",
            "question_type": route.question_type,
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }, ensure_ascii=False)
        yield f"data: {done_payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲，确保实时推送
        },
    )
