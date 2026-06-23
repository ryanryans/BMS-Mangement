"""[已废弃] 工具选择器。

此模块的功能已整合到以下位置：
  - 工具注册与分发  →  src/tools/tool_registry.py（ToolRegistry）
  - 路由-工具映射  →  src/agents/query_router.py（ROUTING_RULES 中的 tools 字段）
  - ReAct 工具调用  →  src/services/chat_service.py（_handle_react）

保留此文件仅为兼容旧测试的 import 语句，不包含任何业务逻辑。
"""
