"""[已废弃] 答案验证器。

此模块的防幻觉功能已以更轻量的方式内置：
  - RAG 模式的证据标注  →  prompt_templates.yaml 的 strict_rag 模板
  - 向量相似度过滤      →  knowledge_base_service.py 的 min_score 阈值
  - LLM-as-judge        →  TODO: Phase 3 将在 answer_verifier.py 重建此功能（更强）

保留此文件仅为兼容旧测试的 import 语句，不包含任何业务逻辑。
"""


class AnswerVerifier:
    """占位符，防止旧测试 import 报错。"""
    def verify(self, *args, **kwargs):
        return {"verified": True, "confidence": "medium"}


class HallucinationChecker:
    """占位符，防止旧测试 import 报错。"""
    def check(self, *args, **kwargs):
        return {"has_hallucination": False}
