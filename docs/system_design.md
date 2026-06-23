# 系统设计文档

## 一、总体架构

```
用户层
├── Streamlit Demo 页面 (app.py)
└── FastAPI 服务入口 (main.py → src/api/)

API 服务层 (src/api/)
├── /health          — 健康检查
├── /chat            — 智能问答（Agentic RAG）
├── /upload          — 文档上传与入库
├── /knowledge_base  — 知识库管理与查询
├── /memory          — 长期记忆管理
├── /feedback        — 用户反馈记录
└── /report          — 报告生成

Agent 服务层 (src/agents/)
├── QueryRouter        — 问题类型分类
├── TaskPlanner        — 任务规划
├── ToolSelector       — 工具选择
├── AnswerVerifier     — 答案校验
└── AgenticRagAgent    — 主流程编排

知识库层 (src/rag/)
├── DocumentLoader     — 文档解析
├── MultimodalParser   — 多模态解析
├── TextSplitter       — 文本切分
├── EmbeddingService   — 向量化（Mock/真实）
├── VectorStore        — 向量存储（本地/ChromaDB）
├── Retriever          — 检索
├── Reranker           — 重排序
└── RagPipeline        — 完整RAG流程

数据存储层 (src/database/)
├── SQLiteManager      — 数据库管理
├── schema.sql         — 完整表结构
└── models.py          — 数据模型

记忆层 (src/memory/)
├── MemoryStore        — 记忆持久化
├── MemoryExtractor    — 记忆抽取
├── MemoryRetriever    — 记忆检索
└── MemoryManager      — 记忆管理

工具层 (src/tools/)
├── TableAnalysisTool       — 表格分析
├── ImageUnderstandingTool  — 图片理解
├── ChartAnalysisTool       — 图表分析
├── FormulaExplainTool      — 公式解释
├── DocumentSummaryTool     — 文档总结
├── ReportGenerationTool    — 报告生成
└── BatteryDataAnalysisTool — 电池数据分析

评估层 (src/evaluation/)
├── RagEvaluator        — RAG质量评估
├── HallucinationChecker — 幻觉检测
└── LatencyAnalyzer     — 延迟分析
```

## 二、Agentic RAG 流程

```
用户问题
  ↓
Query Router (问题分类: general_chat/knowledge_qa/table_analysis/...)
  ↓
Task Planner (任务分解: 检索→过滤→生成→校验)
  ↓
Tool Selector (工具选择: rag_search/table_analysis/...)
  ↓
RAG Pipeline (检索→重排序→证据过滤→生成答案)
  ↓
Answer Verifier (证据数量检查、分数检查、拒答判断)
  ↓
Memory Manager (长期记忆抽取与保存)
  ↓
最终响应 (answer + sources + confidence + latency)
```

## 三、低幻觉机制

1. **Evidence Filter**: 相似度分数低于阈值(0.10)的证据被过滤
2. **Citation Builder**: 回答返回引用来源(filename, chunk_id, score, preview)
3. **Answer Verifier**: 检查证据数量、最高分数、是否通过校验
4. **No Evidence Refusal**: max_score < 0.05 时拒答
5. **Confidence Score**: high(≥0.20) / medium(0.10-0.20) / low(<0.10)
6. **Hallucination Checker**: 检测未引用来源的数字声明、过度自信等

## 四、长期记忆机制

- **类型**: user_preference, project_context, task_history, feedback_memory, tool_preference
- **抽取规则**: 基于关键词触发，只保存高重要性信息
- **存储**: SQLite memories 表
- **检索**: 关键词匹配 + 重要性排序
- **管理**: 支持启用/禁用/删除

## 五、多模态解析

- **表格**: CSV → Markdown + JSON; Excel → Markdown (需openpyxl)
- **图片**: 元数据提取 + 文件名模式匹配 (mock描述)
- **图表**: 文件名识别 + 关联CSV数据分析
- **公式**: 已知公式模板匹配 + 通用解释

## 六、部署架构

- **开发**: `uvicorn main:app --reload` + `streamlit run app.py`
- **Docker**: Dockerfile (Python 3.11-slim) + docker-compose.yml
- **生产**: FastAPI + Nginx + PostgreSQL(可选) + ChromaDB(可选)
