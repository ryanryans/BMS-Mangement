"""Document summary tool — generates structured summaries from text content."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DocumentSummaryTool:
    """Generates key-point summaries from document text.

    Uses extractive summarization (sentence scoring) in absence of an LLM.
    """

    def summarize(self, content: str, max_points: int = 5) -> dict[str, Any]:
        """Generate a structured summary of document content."""
        if not content or not content.strip():
            return {
                "success": False,
                "message": "Empty document content",
                "summary": "",
                "key_points": [],
            }

        # Extract key sentences by position (intro/outro bias) and keyword density
        sentences = self._split_sentences(content)
        if not sentences:
            return {
                "success": False,
                "message": "No sentences found",
                "summary": "",
                "key_points": [],
            }

        # Score sentences
        scored = self._score_sentences(sentences, content)
        top_sentences = scored[:max_points]

        # Build summary
        summary = " ".join(s[0] for s in top_sentences)
        key_points = [s[0] for s in top_sentences]

        # Detect topic
        topic = self._detect_topic(content)

        return {
            "success": True,
            "message": f"Generated summary with {len(key_points)} key points",
            "topic": topic,
            "summary": summary[:1000],
            "key_points": key_points,
            "sentence_count": len(sentences),
            "selected_count": len(key_points),
        }

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re
        # Split on Chinese and English sentence delimiters
        parts = re.split(r'(?<=[。！？.!?\n])\s*', text)
        return [p.strip() for p in parts if len(p.strip()) >= 5]

    def _score_sentences(self, sentences: list[str], full_text: str) -> list[tuple[str, float]]:
        """Score sentences for importance."""
        # TF-based keyword extraction
        import re
        tokens = re.findall(r'[\w一-鿿]{2,}', full_text.lower())

        # Count token frequency
        from collections import Counter
        tf = Counter(tokens)

        # Score each sentence by sum of keyword TF
        scored = []
        for i, sent in enumerate(sentences):
            sent_tokens = re.findall(r'[\w一-鿿]{2,}', sent.lower())
            if not sent_tokens:
                continue
            # TF sum
            tf_score = sum(tf.get(t, 0) for t in sent_tokens) / len(sent_tokens)
            # Position bonus: first and last sentences are often important
            position_bonus = 1.0
            if i == 0 or i == len(sentences) - 1:
                position_bonus = 1.5
            elif i < 3:
                position_bonus = 1.2
            total_score = tf_score * position_bonus
            scored.append((sent, total_score))

        scored.sort(key=lambda x: -x[1])
        return scored

    def _detect_topic(self, text: str) -> str:
        """Simple topic detection from first lines."""
        first_line = text.strip().split("\n")[0][:100]
        return first_line if first_line else "未识别主题"
