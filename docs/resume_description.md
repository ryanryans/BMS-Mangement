# 简历项目描述

## 短版（100字以内）

基于 Agentic RAG 的企业级多模态知识库系统。采用 FastAPI + Agentic RAG 架构，支持文档解析、向量检索、长期记忆、多模态分析。实现问题路由、任务规划、证据约束、答案校验等低幻觉机制。内置电池数据分析等制造业场景工具。支持 Mock 模式无 API Key 运行，Docker 化部署。

## 长版（简历详细描述）

### 项目名称
**基于 Agentic RAG 的企业级多模态知识库 Agent 系统**

### 项目描述
面向车企和制造业的企业级智能研发助手系统。不同于普通 Chatbot，本系统实现了完整的 Agentic RAG 架构：问题路由（Query Router）→ 任务规划（Task Planner）→ 工具选择（Tool Selector）→ 多步检索 → 答案校验（Answer Verifier）→ 长期记忆。支持多模态知识解析（表格、图片、图表、公式）和领域专用工具（电池数据分析）。实现证据约束、引用溯源、无依据拒答等低幻觉机制。

### 技术栈
- **后端**: Python 3.10, FastAPI, Pydantic, Uvicorn
- **Demo**: Streamlit
- **数据库**: SQLite (开发), PostgreSQL (生产预留)
- **向量检索**: SimpleVectorStore (本地), ChromaDB (可选)
- **Embedding**: MockEmbedding / HashEmbedding (开发), 真实模型 (生产)
- **工程化**: pytest, Docker, Docker Compose, YAML配置, .env管理
- **日志**: Python logging + 文件轮转

### 核心亮点
1. **Agentic RAG 完整流程**: 从问题分类到答案校验的7步Agent流水线
2. **低幻觉保障**: 证据过滤 + 引用溯源 + 置信度评分 + 无依据拒答
3. **多模态解析**: CSV/Excel表格分析、图片元数据提取、公式解释、图表趋势分析
4. **长期记忆**: 用户偏好、项目背景、任务历史的抽取和检索
5. **领域工具**: 电池数据分析（电压/电流/温度/容量异常检测）
6. **Mock 优先**: 无任何 API Key 也能完整运行演示，配置 .env 即可接入真实 LLM
7. **工程完整**: 58个测试用例、Docker化、完整文档、统一API格式

### 职责
- 独立完成系统架构设计和全部代码实现
- 设计 Agentic RAG 流程（Router → Planner → Selector → RAG → Verifier）
- 实现本地向量存储（SimpleVectorStore + 持久化）
- 实现低幻觉机制（证据约束、答案校验、拒答策略）
- 实现多模态解析（表格分析、图片理解mock、公式解释）
- 实现电池数据分析工具（制造业差异化亮点）
- 编写完整测试套件、API文档、部署文档

### 量化成果
- 58个测试用例全部通过
- 支持10个API接口（chat, upload, knowledge_base, memory, feedback, report等）
- 7种问题类型自动路由
- 5种长期记忆类型
- 8个领域分析工具
- 7张数据库表设计
