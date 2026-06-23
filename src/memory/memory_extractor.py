"""Memory Extractor — 从对话中抽取出值得长期记忆的信息（M3抽取层）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MemoryCandidate:
    """一条记忆候选（待过滤后入库）。"""
    memory_type: str      # 记忆类型
    content: str          # 记忆内容
    importance: int       # 重要性 1-5
    source: str           # 来源（对话ID）


class MemoryExtractor:
    """基于关键词规则从对话中抽取长期记忆候选。

    不保存所有对话——只有高信号信息才会成为候选。
    抽取规则按记忆类型分组：
    - user_preference: "我喜欢"/"我习惯"/"我需要" 等
    - project_context: "项目"/"电池"/"测试"/"版本" 等
    - task_history:    "上次"/"之前"/"完成了" 等
    """

    PREFERENCE_KEYWORDS = [
        "我喜欢", "我习惯", "我偏好", "我常用", "我希望", "我需要",
        "prefer", "like", "want", "need",
        "我的工作是", "我的部门", "我负责",
    ]

    PROJECT_KEYWORDS = [
        "项目", "project", "版本", "version", "发布", "release",
        "里程碑", "milestone", "截止", "deadline", "优先级", "priority",
        "电池", "battery", "测试", "test", "规格", "spec",
    ]

    TASK_KEYWORDS = [
        "上次", "之前", "上次问了", "你之前说", "任务", "task",
        "完成了", "done", "处理了", "handled",
    ]

    def extract_candidates(self, question: str, answer: str,
                           conversation_id: str = "") -> list[MemoryCandidate]:
        """从一轮Q&A中提取所有类型的记忆候选。"""
        candidates: list[MemoryCandidate] = []

        # 用户偏好检测
        pref_candidates = self._extract_preferences(question, conversation_id)
        candidates.extend(pref_candidates)

        # 项目背景检测
        proj_candidates = self._extract_project_context(question, answer, conversation_id)
        candidates.extend(proj_candidates)

        # 任务历史检测
        task_candidates = self._extract_task_history(question, conversation_id)
        candidates.extend(task_candidates)

        return candidates

    def _extract_preferences(self, question: str, source: str) -> list[MemoryCandidate]:
        """从问题中检测用户偏好关键词。"""
        candidates = []
        for kw in self.PREFERENCE_KEYWORDS:
            if kw.lower() in question.lower():
                candidates.append(MemoryCandidate(
                    memory_type="user_preference",
                    content=question[:500],                          # 截取前500字
                    importance=4,                                    # 偏好重要性默认4
                    source=source,
                ))
                break                                                # 命中一个关键词即可
        return candidates

    def _extract_project_context(self, question: str, answer: str,
                                  source: str) -> list[MemoryCandidate]:
        """从问题中检测项目背景关键词，重要性随内容长度递增。"""
        candidates = []
        for kw in self.PROJECT_KEYWORDS:
            if kw.lower() in question.lower():
                importance = min(5, 3 + (len(question) // 100))      # 内容越详细越重要
                candidates.append(MemoryCandidate(
                    memory_type="project_context",
                    content=f"Q: {question[:300]}\nA: {answer[:300]}",
                    importance=importance,
                    source=source,
                ))
                break
        return candidates

    def _extract_task_history(self, question: str, source: str) -> list[MemoryCandidate]:
        """从问题中检测任务历史关键词。"""
        candidates = []
        for kw in self.TASK_KEYWORDS:
            if kw.lower() in question.lower():
                candidates.append(MemoryCandidate(
                    memory_type="task_history",
                    content=question[:300],
                    importance=3,                                    # 任务历史重要性默认3
                    source=source,
                ))
                break
        return candidates
