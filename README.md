# BMS-Mangement

基于LangChain与FastAPI的智能BMS管理助手

## 基于 Agentic RAG 的企业级多模态知识库 Agent 系统

面向车企、制造业、研发部门的企业级智能研发助手系统。

## 项目亮点

- 🔍 **Agentic RAG** — 问题路由 → 任务规划 → 工具选择 → 多步检索 → 答案校验
- 🛡️ **低幻觉机制** — 证据约束、引用溯源、答案自检、无依据拒答
- 📊 **多模态解析** — 表格(CSV/Excel)、图片、图表、公式
- 💾 **长期记忆** — 用户偏好、项目背景、任务历史
- 🔋 **电池数据分析** — 面向制造业的差异化亮点工具
- 🚀 **Mock优先** — 无需任何 API Key 即可完整运行演示
- 🐳 **Docker化** — 开箱即用的容器部署

## 系统架构

```
用户层 → API服务层(FastAPI) → Agent服务层 → 知识库层 → 数据存储层
                              ↓
                        Streamlit Demo
```

## 目录结构

```
├── main.py              # FastAPI 入口
├── app.py               # Streamlit Demo 入口
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── config/              # 配置文件
│   ├── config.yaml
│   ├── prompt_templates.yaml
│   └── tool_config.yaml
├── src/                 # 核心源码
│   ├── api/             # FastAPI 路由
│   ├── core/            # 配置、响应、异常
│   ├── agents/          # Agentic RAG 组件
│   ├── rag/             # RAG 管道
│   ├── memory/          # 长期记忆
│   ├── tools/           # 领域工具
│   ├── models/          # LLM 服务
│   ├── database/        # 数据库
│   ├── evaluation/      # 评估模块
│   └── utils/           # 工具函数
├── data/                # 数据存储
├── logs/                # 日志
├── tests/               # 测试 (58个用例)
└── docs/                # 文档
```

## 环境安装

```powershell
# 1. 创建虚拟环境
python -m venv venv
venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境
Copy-Item .env.example .env
# (可选) 编辑 .env 设置 DEEPSEEK_API_KEY
```

## 启动服务

### FastAPI (正式服务入口)

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

访问:
- Swagger 文档: http://127.0.0.1:8000/docs
- 健康检查: http://127.0.0.1:8000/health

### Streamlit (Demo 展示)

```powershell
streamlit run app.py
```

访问: http://127.0.0.1:8501

### Docker

```powershell
docker-compose up -d
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |
| POST | /chat | 智能问答 |
| POST | /upload | 文档上传 |
| GET | /knowledge_base | 知识库状态 |
| POST | /knowledge_base/query | 知识库检索 |
| DELETE | /knowledge_base/{doc_id} | 删除文档 |
| GET | /memory | 长期记忆列表 |
| DELETE | /memory/{memory_id} | 删除记忆 |
| POST | /feedback | 提交反馈 |
| POST | /report | 生成报告 |

详见 [docs/api_design.md](docs/api_design.md)

## 运行测试

```powershell
python -m pytest -q
```

当前: **58 passed** ✅

## 当前已实现功能

- [x] FastAPI 完整服务入口 + 10个API接口
- [x] Streamlit Demo 页面 (7个功能页)
- [x] Agentic RAG 完整流程 (Router → Planner → Selector → RAG → Verifier)
- [x] 本地向量存储 (SimpleVectorStore + 持久化)
- [x] MockEmbedding (无需外部模型依赖)
- [x] 文档解析 (TXT/MD/CSV，PDF/DOCX可选)
- [x] 证据约束、引用溯源、置信度评分、无依据拒答
- [x] 长期记忆 (5种类型，抽取/存储/检索/管理)
- [x] 表格分析工具 (CSV/Excel → Markdown + 统计)
- [x] 图片理解工具 (元数据 + mock描述)
- [x] 图表分析工具 (趋势推测)
- [x] 公式解释工具 (已知公式匹配)
- [x] 文档总结工具 (抽取式摘要)
- [x] 报告生成工具 (3种模板)
- [x] 电池数据分析工具 (电压/电流/温度/容量)
- [x] 用户反馈记录
- [x] 幻觉检测模块
- [x] RAG评估 + 延迟分析
- [x] SQLite完整表结构 (7张表)
- [x] Docker/Docker Compose
- [x] 58个测试用例全部通过
- [x] 完整文档 (系统设计/API设计/部署/Demo案例/简历描述)

## 后续规划

- [ ] 接入真实 Embedding 模型 (text2vec, BGE, etc.)
- [ ] ChromaDB 向量数据库支持
- [ ] PostgreSQL 生产数据库支持
- [ ] 真实 VLM 图片理解 (GPT-4V / 本地模型)
- [ ] PDF 表格提取 (Camelot / Tabula)
- [ ] 用户认证 (JWT)
- [ ] Web 前端页面 (React/Vue)
- [ ] 企业微信/飞书 Bot 接口
- [ ] RAG 效果自动评估 (RAGAS)
- [ ] A/B 测试框架

## 常见问题

**Q: 没有 API Key 能运行吗？**
A: 可以！项目默认使用 MockModel/RuleBasedLLM，完整流程可运行。配置 .env 中的 DEEPSEEK_API_KEY 即可切换到真实模型。

**Q: ChromaDB 必须安装吗？**
A: 不需要。默认使用本地 SimpleVectorStore (JSON 持久化)。ChromaDB 可作为可选升级。

**Q: 如何添加自定义工具？**
A: 在 src/tools/ 中创建新工具，在 src/agents/tool_selector.py 的 TOOL_ROUTING 中注册路由。

**Q: Streamlit 页面报错？**
A: Streamlit 仅作 Demo 展示。核心逻辑在 src/ 中，可独立通过 FastAPI 调用。

## 简历描述

见 [docs/resume_description.md](docs/resume_description.md)
