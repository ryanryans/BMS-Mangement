"""[已废弃] 任务规划器。

此模块的功能已整合到以下位置：
  - 意图路由  →  src/agents/query_router.py（QueryRouter + LLM 语义兜底）
  - 工具分发  →  src/services/chat_service.py（_dispatch 函数）
  - 工具注册  →  src/tools/tool_registry.py（ToolRegistry）

保留此文件仅为兼容旧测试的 import 语句，不包含任何业务逻辑。
"""
