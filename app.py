"""Streamlit Demo — 企业级智能研发助手（仅展示层，核心逻辑在 src/）。"""
import streamlit as st

st.set_page_config(
    page_title="企业级智能研发助手",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 全局 CSS 样式
# ============================================================
st.markdown("""
<style>
    /* 整体 */
    .main .block-container { max-width: 1200px; padding-top: 1rem; }
    .stApp { background: linear-gradient(135deg, #0f1117 0%, #1a1d27 100%); }

    /* 标题 */
    h1 { color: #e8eaed; font-size: 1.8rem; font-weight: 700; }
    h2 { color: #d0d4db; font-size: 1.3rem; font-weight: 600; margin-top: 1.5rem; }
    h3 { color: #c0c4cc; font-size: 1.1rem; }

    /* 卡片 */
    .card {
        background: #1e2130; border: 1px solid #2d3143; border-radius: 10px;
        padding: 1.2rem; margin: 0.5rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .card-header { font-size: 0.85rem; color: #8890a4; margin-bottom: 0.3rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .card-value { font-size: 1.6rem; font-weight: 700; color: #60a5fa; }
    .card-value.green { color: #34d399; }
    .card-value.yellow { color: #fbbf24; }
    .card-value.red { color: #f87171; }

    /* 指标卡片网格 */
    .metric-grid { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
    .metric-card {
        flex: 1; min-width: 140px; background: #1e2130; border: 1px solid #2d3143;
        border-radius: 10px; padding: 1rem; text-align: center;
    }

    /* 按钮 */
    .stButton > button {
        border-radius: 8px; font-weight: 500; transition: all 0.2s;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

    /* 聊天 */
    .chat-answer {
        background: #1e2130; border-left: 3px solid #60a5fa; border-radius: 8px;
        padding: 1rem 1.2rem; margin: 0.5rem 0;
    }
    .chat-meta {
        font-size: 0.78rem; color: #6b7280; margin-top: 0.5rem;
        display: flex; gap: 1rem; flex-wrap: wrap;
    }
    .chat-meta span { background: #252836; padding: 2px 8px; border-radius: 4px; }

    /* 来源卡片 */
    .source-item {
        background: #252836; border-radius: 6px; padding: 0.6rem 0.8rem;
        margin: 0.3rem 0; font-size: 0.85rem;
    }
    .source-item .filename { color: #60a5fa; font-weight: 500; }
    .source-item .score { color: #fbbf24; }

    /* 上传状态 */
    .upload-success { color: #34d399; }
    .upload-skip { color: #fbbf24; }
    .upload-fail { color: #f87171; }

    /* 展开器 */
    .streamlit-expanderHeader { background: #1e2130; border-radius: 8px; }

    /* sidebar */
    [data-testid="stSidebar"] { background: #13151c; }
    [data-testid="stSidebar"] .stRadio label { color: #c0c4cc; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 模型状态（不缓存）
# ============================================================
def get_model_status():
    from src.models.model_factory import get_model_status as _gs
    return _gs()

def get_kb_status_summary():
    try:
        from src.rag.knowledge_base_service import get_kb_service
        kb = get_kb_service()
        return kb.get_status()
    except Exception:
        return None

if "model_status" not in st.session_state:
    st.session_state.model_status = get_model_status()

model_status = st.session_state.model_status
kb_status = get_kb_status_summary()

# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.markdown("### 🏭 企业级智能研发助手")
    st.caption("基于 Agentic RAG 的多模态知识库系统")

    # 模型状态
    st.divider()
    st.markdown("#### 🤖 模型状态")
    provider = model_status.get("llm_provider", "RuleBasedLLM")
    is_mock = model_status.get("is_mock", True)

    if is_mock:
        st.warning(f"当前模型：**MockLLM**\n\n本地规则模式，未连接大模型")
    else:
        st.success(f"当前模型：**{provider}**\n\n真实大模型已连接")

    if not model_status.get("deepseek_key_present"):
        st.caption("💡 配置 DEEPSEEK_API_KEY 到 .env 可启用真实大模型")

    # 知识库状态
    st.divider()
    st.markdown("#### 📚 知识库状态")
    if kb_status:
        st.metric("文档数", kb_status.document_count)
        st.metric("Chunk 数", kb_status.chunk_count)
        st.metric("向量数", kb_status.vector_count)
        st.caption(f"状态：{'就绪' if kb_status.status == 'ready' else '空'}")
    else:
        st.caption("知识库未初始化")

    # 版本
    st.divider()
    st.caption("Demo v1.0 | 核心逻辑在 src/")

    # 操作按钮
    col1, col2 = st.columns(2)
    if col1.button("🔄 刷新状态"):
        from src.models.llm_service import reset_llm
        reset_llm()
        st.session_state.model_status = get_model_status()
        st.rerun()
    if col2.button("🔌 测试连接"):
        from src.models.llm_service import reset_llm, get_llm, get_llm_provider_name
        reset_llm()
        st.session_state.model_status = get_model_status()
        ms = st.session_state.model_status
        if ms.get("deepseek_key_present"):
            llm = get_llm()
            if get_llm_provider_name(llm) == "DeepSeekAdapter":
                answer = llm.generate("用一句话回答：RAG 的核心流程是什么？")
                if hasattr(llm, 'last_call_succeeded') and llm.last_call_succeeded:
                    st.success("✅ 真实 API 连接成功")
                else:
                    st.error(f"❌ 连接失败：{getattr(llm, 'last_error', '未知错误')}")
            else:
                st.info("当前为 MockLLM 模式")
        else:
            st.info("未配置 API Key")

    # 页面导航
    st.divider()
    st.markdown("#### 📋 功能导航")
    page = st.radio(
        "选择功能",
        ["项目介绍", "智能问答", "文档上传", "知识库管理", "长期记忆", "表格分析", "报告生成"],
        label_visibility="collapsed",
    )

# ============================================================
# 页面：项目介绍
# ============================================================
if page == "项目介绍":
    st.title("🏭 企业级智能研发助手")
    st.caption("基于 Agentic RAG 的企业级多模态知识库 Agent 系统 · Demo 展示")

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(
        '<div class="metric-card">'
        '<div class="card-header">当前模型</div>'
        f'<div class="card-value {"green" if not is_mock else "yellow"}">{provider}</div>'
        '</div>', unsafe_allow_html=True)
    col2.markdown(
        '<div class="metric-card">'
        '<div class="card-header">知识库文档</div>'
        f'<div class="card-value">{kb_status.document_count if kb_status else 0}</div>'
        '</div>', unsafe_allow_html=True)
    col3.markdown(
        '<div class="metric-card">'
        '<div class="card-header">Chunk 数</div>'
        f'<div class="card-value">{kb_status.chunk_count if kb_status else 0}</div>'
        '</div>', unsafe_allow_html=True)
    col4.markdown(
        '<div class="metric-card">'
        '<div class="card-header">系统状态</div>'
        f'<div class="card-value green">{"真实LLM" if not is_mock else "Mock模式"}</div>'
        '</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    ### 核心能力

    | 能力 | 说明 |
    |------|------|
    | 🔍 **知识库问答** | 上传企业文档 → 自动解析入库 → Agentic RAG 检索 → 大模型总结回答 |
    | 📊 **表格分析** | CSV/Excel 自动识别 → 数值列统计 → 趋势分析 → Markdown 报表 |
    | 📝 **报告生成** | 检索知识库 → 构造 Prompt → LLM 生成 → 结构化项目报告 |
    | 🛡️ **低幻觉机制** | 证据过滤 + 引用溯源 + 置信度评分 + 无依据拒答 |
    | 💾 **长期记忆** | 自动抽取用户偏好、项目背景、任务历史 |
    | 🔋 **电池数据分析** | 面向制造业：电压/电流/温度/容量异常检测 |

    ### 技术架构

    **FastAPI** 服务入口 → **QueryRouter** 问题分流 → **RAG Pipeline** 检索 → **LLM** 总结 → 返回答案

    Streamlit 仅作 Demo 展示层，核心逻辑在 `src/` 中。
    """)

# ============================================================
# 页面：智能问答
# ============================================================
elif page == "智能问答":
    st.header("💬 智能问答")
    st.caption("Agentic RAG 自动分流：知识问答 · 表格分析 · 报告生成")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(f'<div class="chat-answer">{msg["content"]}</div>', unsafe_allow_html=True)
                meta = msg.get("meta", {})
                if meta:
                    parts = []
                    if meta.get("route"):
                        parts.append(f'<span>🔀 {meta["route"]}</span>')
                    if meta.get("model"):
                        parts.append(f'<span>🤖 {meta["model"]}</span>')
                    if meta.get("confidence"):
                        parts.append(f'<span>📊 置信度：{meta["confidence"]}</span>')
                    if meta.get("sources_count", 0) > 0:
                        parts.append(f'<span>📎 {meta["sources_count"]} 条来源</span>')
                    if meta.get("latency"):
                        parts.append(f'<span>⏱️ {meta["latency"]}ms</span>')
                    st.markdown(f'<div class="chat-meta">{"".join(parts)}</div>', unsafe_allow_html=True)
                if msg.get("sources"):
                    with st.expander(f"📎 参考来源（{len(msg['sources'])} 条）"):
                        for s in msg["sources"]:
                            st.markdown(
                                f'<div class="source-item">'
                                f'<span class="filename">📄 {s.get("filename", "?")}</span> '
                                f'<span class="score">分数：{s.get("score", 0):.3f}</span><br>'
                                f'<small>{s.get("preview", "")[:200]}</small>'
                                f'</div>', unsafe_allow_html=True)
            else:
                st.write(msg["content"])

    # 输入框
    if prompt := st.chat_input("请输入问题，例如：低温快充可能带来什么风险？"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            try:
                from src.services.chat_service import handle_chat
                with st.spinner("正在处理..."):
                    r = handle_chat(prompt)

                st.markdown(f'<div class="chat-answer">{r["answer"]}</div>', unsafe_allow_html=True)

                # 元数据标签
                route_label = {
                    "knowledge_qa": "知识库问答", "table_analysis": "表格分析",
                    "report_generation": "报告生成", "general_chat": "通用对话",
                    "image_understanding": "图片理解", "memory_query": "记忆查询",
                    "document_summary": "文档总结"
                }.get(r["question_type"], r["question_type"])

                # RAG 模式标签
                retrieval_status = r.get("retrieval_status", "unknown")
                rag_label_map = {
                    "used": "🔗 RAG增强", "empty": "💬 通用LLM",
                    "low_relevance": "⚠️ 低相关未使用", "off": "💬 纯LLM",
                    "not_attempted": "🔧 工具调用",
                }
                react_steps = r.get("react_steps", 0)
                if retrieval_status == "react_loop" and react_steps:
                    rag_label = f"ReAct ({react_steps} steps)"
                else:
                    rag_label = rag_label_map.get(retrieval_status, retrieval_status)

                conf_color = {"high": "#34d399", "medium": "#fbbf24", "low": "#f87171"}
                parts = [
                    f'<span>🔀 {route_label}</span>',
                    f'<span>{rag_label}</span>',
                    f'<span>🤖 {r.get("llm_provider", r["model_type"])}</span>',
                    f'<span>⏱️ {r["latency_ms"]}ms</span>',
                ]
                if r.get("real_llm_called"):
                    parts.append('<span style="color:#34d399">✅ 真实LLM</span>')
                elif r.get("llm_called"):
                    parts.append('<span style="color:#fbbf24">⚠️ MockLLM</span>')
                if retrieval_status == "used":
                    parts.append(f'<span>📎 {r["evidence_count"]} 条来源</span>')
                st.markdown(f'<div class="chat-meta">{"".join(parts)}</div>', unsafe_allow_html=True)

                # 来源
                if r["sources"]:
                    with st.expander(f"📎 参考来源（{len(r['sources'])} 条）"):
                        for s in r["sources"]:
                            st.markdown(
                                f'<div class="source-item">'
                                f'<span class="filename">📄 {s.get("filename", "?")}</span> '
                                f'<span class="score">分数：{s.get("score", 0):.3f}</span><br>'
                                f'<small>{s.get("preview", "")[:200]}</small>'
                                f'</div>', unsafe_allow_html=True)

                st.session_state.messages.append({
                    "role": "assistant", "content": r["answer"], "sources": r["sources"],
                    "meta": {
                        "route": route_label, "model": r.get("llm_provider", ""),
                        "confidence": r["confidence"], "sources_count": r["evidence_count"],
                        "latency": r["latency_ms"],
                    }
                })
            except Exception as e:
                st.error(f"处理失败：{e}")

# ============================================================
# 页面：文档上传
# ============================================================
elif page == "文档上传":
    st.header("📤 文档上传")
    st.caption("支持批量上传 TXT / MD / CSV，自动去重和内容分类")

    uploaded_files = st.file_uploader(
        "选择文件（支持多选）",
        type=["txt", "md", "csv", "pdf", "docx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.markdown(f"已选择 **{len(uploaded_files)}** 个文件")

        if st.button("🚀 开始入库", type="primary", use_container_width=True):
            from src.core.settings import get_settings
            settings = get_settings()
            from src.rag.knowledge_base_service import get_kb_service
            kb = get_kb_service()

            results = []
            progress = st.progress(0, "正在处理...")
            status_text = st.empty()

            for i, f in enumerate(uploaded_files):
                progress.progress((i + 1) / len(uploaded_files))
                status_text.text(f"处理中：{f.name} ({i+1}/{len(uploaded_files)})")
                try:
                    dest = settings.raw_documents_dir / f.name
                    dest.write_bytes(f.read())
                    if kb and f.name.endswith((".txt", ".md", ".csv")):
                        r = kb.ingest_file(dest)
                        results.append({
                            "name": f.name, "size": f.size, "ok": r.success,
                            "skipped": r.skipped_duplicate, "chunks": r.chunk_count,
                            "content_type": r.content_type, "error": r.error,
                        })
                    else:
                        results.append({
                            "name": f.name, "size": f.size, "ok": True,
                            "skipped": False, "chunks": 0, "content_type": f.name.split(".")[-1], "error": "",
                        })
                except Exception as e:
                    results.append({
                        "name": f.name, "size": f.size, "ok": False,
                        "skipped": False, "chunks": 0, "content_type": "", "error": str(e),
                    })

            progress.empty()
            status_text.empty()

            # 汇总卡片
            new_count = sum(1 for r in results if r["ok"] and not r["skipped"])
            skip_count = sum(1 for r in results if r["skipped"])
            fail_count = sum(1 for r in results if not r["ok"])
            total_chunks = sum(r["chunks"] for r in results)

            st.markdown("### 📊 入库汇总")
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("总文件数", len(uploaded_files))
            col2.metric("✅ 成功入库", new_count)
            col3.metric("⏭️ 跳过重复", skip_count)
            col4.metric("❌ 失败", fail_count, delta=None if fail_count == 0 else f"-{fail_count}")
            col5.metric("📦 新增 Chunk", total_chunks)

            # 逐个文件
            st.markdown("### 📋 文件详情")
            for r in results:
                type_label = {"text_knowledge": "文本", "table_knowledge": "表格", "image_knowledge": "图片"}.get(r.get("content_type", ""), r.get("content_type", "?"))
                if r["skipped"]:
                    st.info(f"⏭️ **{r['name']}** | {r['size']} bytes — 文件已存在，跳过重复入库")
                elif r["ok"]:
                    st.success(f"✅ **{r['name']}** ({type_label}) | {r['size']} bytes | {r['chunks']} chunks — 入库成功")
                else:
                    st.error(f"❌ **{r['name']}** — {r['error']}")

    # 已上传文件列表
    with st.expander("📂 已上传文件列表"):
        from src.core.settings import get_settings
        settings = get_settings()
        if settings.raw_documents_dir.exists():
            files = sorted(settings.raw_documents_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
            if files:
                for f in files[:30]:
                    st.text(f"📄 {f.name}  ({f.stat().st_size} bytes)")
            else:
                st.text("暂无文件")

# ============================================================
# 页面：知识库管理
# ============================================================
elif page == "知识库管理":
    st.header("📚 知识库管理")

    from src.rag.knowledge_base_service import get_kb_service
    kb = get_kb_service()
    if not kb:
        st.warning("知识库服务未初始化")
        st.stop()

    status = kb.get_status()

    # 指标卡片
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(
        f'<div class="metric-card"><div class="card-header">文档数</div>'
        f'<div class="card-value">{status.document_count}</div></div>', unsafe_allow_html=True)
    col2.markdown(
        f'<div class="metric-card"><div class="card-header">Chunk 数</div>'
        f'<div class="card-value">{status.chunk_count}</div></div>', unsafe_allow_html=True)
    col3.markdown(
        f'<div class="metric-card"><div class="card-header">向量数</div>'
        f'<div class="card-value">{status.vector_count}</div></div>', unsafe_allow_html=True)
    col4.markdown(
        f'<div class="metric-card"><div class="card-header">状态</div>'
        f'<div class="card-value {"green" if status.status=="ready" else "red"}">{status.status}</div></div>',
        unsafe_allow_html=True)

    st.markdown("---")

    # 操作按钮
    c1, c2, c3 = st.columns([1, 1, 2])
    if c1.button("🗑️ 清空知识库", use_container_width=True):
        confirm = st.checkbox("确认清空？此操作不可恢复", key="confirm_clear")
        if confirm:
            kb.clear()
            from src.rag.knowledge_base_service import reset_kb_service
            reset_kb_service()
            st.cache_resource.clear()
            st.success("知识库已清空")
            st.rerun()

    if c2.button("🔄 重建索引", use_container_width=True):
        from src.rag.knowledge_base_service import reset_kb_service
        reset_kb_service()
        st.cache_resource.clear()
        kb2 = get_kb_service()
        result = kb2.rebuild_index()
        st.success(result["message"])
        st.rerun()

    if c3.button("🔄 刷新状态", use_container_width=True):
        st.rerun()

    st.markdown("---")

    # 文档列表
    st.subheader(f"📋 已入库文档（{status.document_count} 个）")
    docs = kb.list_documents()
    if docs:
        for doc in docs[:50]:
            file_hash = doc.get("file_hash", "")[:10] or "N/A"
            ct = doc.get("content_type", "text_knowledge")
            ct_label = {"text_knowledge": "📝 文本知识", "table_knowledge": "📊 表格知识", "image_knowledge": "🖼️ 图片知识"}.get(ct, ct)
            with st.expander(f"{ct_label} | {doc.get('doc_name', 'N/A')} | Chunk: {doc.get('chunk_count', 0)} | Hash: {file_hash}"):
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.json({k: str(v)[:200] for k, v in doc.items()})
                with col_b:
                    if st.button(f"🗑️ 删除", key=f"del_{doc['doc_id']}"):
                        kb.delete_document(doc["doc_id"])
                        st.success(f"已删除 {doc['doc_name']}")
                        st.rerun()
    else:
        st.info("暂无文档，请先到「文档上传」页面上传文件。")

# ============================================================
# 页面：长期记忆
# ============================================================
elif page == "长期记忆":
    st.header("💾 长期记忆")
    st.caption("系统自动抽取用户偏好、项目背景、任务历史等信息")

    from src.memory.memory_manager import get_memory_manager
    mm = get_memory_manager()
    if mm:
        items = mm.list_memories()
        type_labels = {
            "user_preference": "👤 用户偏好", "project_context": "📋 项目背景",
            "task_history": "📝 任务历史", "feedback_memory": "💬 反馈记忆",
            "tool_preference": "🔧 工具偏好",
        }

        col1, col2 = st.columns(2)
        with col1:
            st.metric("总记忆条目", len(items))
        with col2:
            types = {}
            for item in items:
                t = item["memory_type"]
                types[t] = types.get(t, 0) + 1
            st.caption(" | ".join(f"{type_labels.get(k, k)}：{v}" for k, v in types.items()))

        st.markdown("---")
        for item in items[:30]:
            label = type_labels.get(item["memory_type"], item["memory_type"])
            imp = item.get("importance", 3)
            with st.expander(f"{label} | 重要性：{'⭐' * imp} | {item.get('created_at', '')[:16]}"):
                st.text(item["content"][:500])
    else:
        st.warning("记忆服务未初始化")

# ============================================================
# 页面：表格分析
# ============================================================
elif page == "表格分析":
    st.header("📊 表格分析")
    st.caption("上传 CSV 文件，自动统计数值列并生成分析报告")

    csv_file = st.file_uploader("选择 CSV 文件", type=["csv"], label_visibility="collapsed")

    if csv_file:
        from src.core.settings import get_settings
        dest = get_settings().raw_documents_dir / csv_file.name
        dest.write_bytes(csv_file.read())

        st.success(f"✅ 文件已保存：{csv_file.name}（{csv_file.size} bytes）")

        from src.tools.table_analysis_tool import TableAnalysisTool
        with st.spinner("正在分析表格..."):
            result = TableAnalysisTool().analyze("分析此表格", str(dest))

        # 渲染分析结果
        st.markdown("### 📈 分析结果")
        st.markdown(
            f'<div class="card" style="max-height:600px;overflow-y:auto;">{result}</div>',
            unsafe_allow_html=True,
        )

        # 如果包含电池相关列，提示可以走电池分析
        import csv
        with open(dest, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if rows:
            cols = [c.lower() for c in rows[0].keys()]
            battery_cols = [c for c in cols if any(k in c for k in ["temperature", "temp", "温度", "voltage", "电压", "current", "电流", "capacity", "容量"])]
            if battery_cols:
                st.info(f"💡 检测到电池相关列：{', '.join(battery_cols)}，可以在智能问答中提问电池分析相关问题。")

# ============================================================
# 页面：报告生成
# ============================================================
elif page == "报告生成":
    st.header("📝 报告生成")
    st.caption(f"当前模型：**{provider}**{'（真实大模型）' if not is_mock else '（本地规则模式）'}")

    with st.form("report_form"):
        topic = st.text_input("报告主题", "低温快充测试数据分析", help="例如：BMS 项目周报、电池循环测试报告")
        report_type = st.selectbox(
            "报告类型",
            ["standard", "weekly", "battery_test"],
            format_func=lambda x: {"standard": "标准报告", "weekly": "项目周报", "battery_test": "电池测试报告"}.get(x, x),
        )
        submitted = st.form_submit_button("🚀 生成报告", type="primary", use_container_width=True)

    if submitted:
        from src.services.report_service import generate_report
        with st.spinner("正在生成报告..."):
            r = generate_report(topic, report_type)

        # 结果展示
        st.markdown("### 📄 生成结果")

        if not r["from_llm"]:
            if is_mock:
                st.warning("⚠️ 当前为 MockLLM 模式，报告使用模板生成。配置 DEEPSEEK_API_KEY 可获得真实 AI 生成的报告。")
            else:
                st.error(f"❌ 大模型调用失败：{r.get('fallback_reason', '未知')}")

        st.markdown(
            f'<div class="card" style="max-height:600px;overflow-y:auto;">{r["content"]}</div>',
            unsafe_allow_html=True,
        )

        # 元数据
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("生成模型", r["llm_provider"])
        col2.metric("是否真实 LLM", "是" if r["from_llm"] else "否")
        col3.metric("来源数", r["sources_used"])
        col4.metric("模式", "真实" if not r["is_mock"] else "Mock")

        with st.expander("🔍 诊断信息"):
            st.code(r.get("prompt_preview", "")[:800], language="text")

        # 下载
        st.download_button(
            "📥 下载报告",
            r["content"],
            file_name=f"report_{topic}.md",
            mime="text/markdown",
            use_container_width=True,
        )

# ============================================================
# 页脚
# ============================================================
st.divider()
st.caption("🏭 企业级智能研发助手 · Demo v1.0 · 基于 Agentic RAG | 核心逻辑在 src/")
