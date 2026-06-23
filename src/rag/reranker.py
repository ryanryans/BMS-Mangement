"""Reranker — 使用关键词重叠度对检索结果进行重排序（M2检索优化）。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.rag.retriever import Evidence


@dataclass
class RerankedEvidence:
    """重排序后的证据（保留原始分数+新分数+关键词重叠度）。"""
    evidence: Evidence              # 原始证据
    original_score: float           # 原始向量相似度分数
    reranked_score: float           # 重排序后的综合分数
    keyword_overlap: float = 0.0    # 关键词重叠度（Jaccard相似度）


class SimpleReranker:
    """轻量级重排序器：向量相似度 + 关键词重叠度加权融合。

    公式: new_score = vector_score × (1 - w) + keyword_overlap × w
    其中 w = keyword_bonus_weight（默认0.3）

    不需要外部模型，纯统计方法，适合开发阶段。
    """

    def __init__(self, keyword_bonus_weight: float = 0.3):
        self._keyword_weight = keyword_bonus_weight                  # 关键词权重（0~1）

    def rerank(
        self,
        query: str,
        evidences: list[Evidence],
        top_k: int | None = None,
    ) -> list[RerankedEvidence]:
        """对证据列表重排序，返回top_k条。"""
        if not evidences:
            return []

        query_tokens = self._tokenize(query)                         # 查询词集合

        reranked = []
        for ev in evidences:
            content_tokens = self._tokenize(ev.content)              # 证据词集合
            overlap = self._keyword_overlap(query_tokens, content_tokens)  # 计算Jaccard相似度
            # 向量分数 + 关键词分数加权融合
            new_score = ev.score * (1 - self._keyword_weight) + overlap * self._keyword_weight
            reranked.append(RerankedEvidence(
                evidence=ev,
                original_score=ev.score,
                reranked_score=round(new_score, 4),
                keyword_overlap=round(overlap, 4),
            ))

        reranked.sort(key=lambda r: (-r.reranked_score, r.evidence.doc_id))  # 按新分数降序
        return reranked[:top_k] if top_k else reranked

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """提取有意义的token（长度≥2的中英文单词）。"""
        tokens = re.findall(r"[\w一-鿿]+", text.lower())
        return {t for t in tokens if len(t) >= 2}                    # 过滤单字符

    @staticmethod
    def _keyword_overlap(query_tokens: set[str], content_tokens: set[str]) -> float:
        """计算Jaccard相似度 = |交集| / |并集|。"""
        if not query_tokens or not content_tokens:
            return 0.0
        intersection = query_tokens & content_tokens
        union = query_tokens | content_tokens
        return len(intersection) / len(union) if union else 0.0
