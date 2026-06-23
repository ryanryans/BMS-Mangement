"""Embedding 服务 — 将文本转换为语义向量的核心组件。

【学习要点】什么是 Embedding？
  文本 embedding 就是把一段文字变成一串数字（向量），
  让语义相似的文字在向量空间中距离更近。
  例如："电池过热" 和 "电芯高温" 语义相似 → 向量距离小 → 可以被检索命中。

三种实现（由低到高）：
  1. MockEmbedding    — 字符哈希，零依赖，仅用于测试，没有语义能力
  2. HashEmbedding    — TF-IDF 加权，有词频语义，需先 fit() 语料库
  3. SentenceTransformerEmbedding — 真正的语义向量，生产推荐

如何切换：修改 get_embedding_service() 底部的返回值即可。
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from collections import Counter
from typing import Protocol

logger = logging.getLogger(__name__)


# ── 接口协议（Protocol = Python 的鸭子类型接口）────────────────────
# 只要实现了 encode / encode_batch 方法，就可以作为 EmbeddingProvider 使用。
# 这让三种实现可以无缝替换，调用方不需要知道用的是哪种。

class EmbeddingProvider(Protocol):
    """Embedding 提供者接口 — 所有实现必须满足此协议。"""
    def encode(self, text: str) -> list[float]: ...
    def encode_batch(self, texts: list[str]) -> list[list[float]]: ...


# ════════════════════════════════════════════════════════════════════
#  实现 1: MockEmbedding（字符三元组哈希，零依赖，仅用于测试）
# ════════════════════════════════════════════════════════════════════

class MockEmbedding:
    """基于字符三元组 MD5 哈希的 Mock Embedding。

    原理: 对文本中每3个连续字符（trigram）计算 MD5 → 映射到128维向量 → L2归一化。
    优点: 确定性、零依赖、毫秒级，测试和 CI 环境友好。
    局限: 没有真正的语义理解 —— "电池"和"battery"向量距离极远，跨词匹配失效。
    适用: 单元测试、离线 Demo、验证流水线正确性（不验证检索质量）。
    """

    DIM = 128  # 向量维度

    def encode(self, text: str) -> list[float]:
        """单条文本 → 128维向量。"""
        if not text or not text.strip():
            return [0.0] * self.DIM

        vec = [0.0] * self.DIM
        text_lower = text.lower()
        for i in range(len(text_lower) - 2):
            trigram = text_lower[i:i + 3]                          # 滑动窗口取三元组
            h = int(hashlib.md5(trigram.encode()).hexdigest(), 16)  # MD5 → 大整数
            idx = h % self.DIM                                      # 取模映射到向量维度
            vec[idx] += 1.0                                         # 累加计数

        return _l2_normalize(vec)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.encode(t) for t in texts]

    def similarity(self, vec1: list[float], vec2: list[float]) -> float:
        return _cosine_similarity(vec1, vec2)


# ════════════════════════════════════════════════════════════════════
#  实现 2: HashEmbedding（TF-IDF 加权，有词频语义，需 fit() 语料库）
# ════════════════════════════════════════════════════════════════════

class HashEmbedding:
    """基于词级 TF-IDF 的轻量 Embedding。

    比 MockEmbedding 更好：同一个词在不同文档中的权重不同（IDF），
    常见词（"的"、"是"）权重低，专业词（"析锂"、"SOC"）权重高。
    局限: 仍然是词汇层面匹配，"battery"和"电池"不会识别为相近。
    适用: 没有 GPU/网络，但想要比 Mock 更好效果的场景。
    使用: 必须先调用 fit(corpus) 计算 IDF，再调用 encode()。
    """

    TOKEN_PATTERN = re.compile(r"[\w一-鿿]+", re.UNICODE)

    def __init__(self, dim: int = 256):
        self.dim = dim
        self._idf: dict[str, float] = {}
        self._fitted = False

    def fit(self, corpus: list[str]) -> None:
        """在语料库上计算 IDF（逆文档频率）。必须在 encode() 之前调用。"""
        doc_count = len(corpus)
        if doc_count == 0:
            return
        df: dict[str, int] = {}
        for text in corpus:
            for token in set(self._tokenize(text)):
                df[token] = df.get(token, 0) + 1
        # 平滑 IDF：log((N+1)/(df+1)) + 1，防止分母为0
        self._idf = {t: math.log((doc_count + 1) / (freq + 1)) + 1 for t, freq in df.items()}
        self._fitted = True

    def _tokenize(self, text: str) -> list[str]:
        return [t.lower() for t in self.TOKEN_PATTERN.findall(text)]

    def encode(self, text: str) -> list[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dim
        tf = Counter(tokens)
        max_tf = max(tf.values())
        vec = [0.0] * self.dim
        for token, count in tf.items():
            idx = int(hashlib.sha256(token.encode()).hexdigest(), 16) % self.dim
            tf_norm = count / max_tf
            idf = self._idf.get(token, 1.0) if self._fitted else 1.0
            vec[idx] += tf_norm * idf
        return _l2_normalize(vec)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.encode(t) for t in texts]

    def similarity(self, vec1: list[float], vec2: list[float]) -> float:
        return _cosine_similarity(vec1, vec2)


# ════════════════════════════════════════════════════════════════════
#  实现 3: SentenceTransformerEmbedding（真正的语义向量，生产推荐）
# ════════════════════════════════════════════════════════════════════

class SentenceTransformerEmbedding:
    """基于预训练语言模型的语义 Embedding —— 生产环境推荐使用。

    【核心优势 vs Mock/Hash】
      - 真正理解语义："电池过热" ≈ "电芯高温" ≈ "battery overheating"
      - 支持中英文混合
      - 首次加载模型需要下载（~400MB），之后本地缓存，离线可用

    推荐模型：
      - paraphrase-multilingual-MiniLM-L12-v2（中英双语，均衡速度/效果）
      - all-MiniLM-L6-v2（英文，更快）
      - shibing624/text2vec-base-chinese（纯中文，效果更好）

    依赖安装：
      pip install sentence-transformers
      （requirements.txt 中已包含）
    """

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self._model_name = model_name
        self._model = None
        self._dim: int | None = None
        self._load_model()

    def _load_model(self) -> None:
        """懒加载模型 —— 首次调用时下载并缓存到本地。"""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s ...", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            # 用空字符串探测向量维度
            probe = self._model.encode(["test"], convert_to_numpy=True)
            self._dim = probe.shape[1]
            logger.info("Embedding model ready: dim=%d", self._dim)
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error("Failed to load embedding model '%s': %s", self._model_name, e)
            raise

    @property
    def dimension(self) -> int:
        """返回向量维度（由模型决定，通常是 384 或 768）。"""
        return self._dim or 384

    def encode(self, text: str) -> list[float]:
        """单条文本 → 语义向量（float list）。"""
        if not text or not text.strip():
            return [0.0] * self.dimension
        vec = self._model.encode(text, convert_to_numpy=True)
        return vec.tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """批量编码 —— 比逐条 encode 快 3-5x（GPU 效果更明显）。"""
        if not texts:
            return []
        # batch_size=32 是经验值，显存/内存充足可调大
        vecs = self._model.encode(texts, batch_size=32, convert_to_numpy=True, show_progress_bar=False)
        return vecs.tolist()

    def similarity(self, vec1: list[float], vec2: list[float]) -> float:
        return _cosine_similarity(vec1, vec2)


# ════════════════════════════════════════════════════════════════════
#  公共辅助函数
# ════════════════════════════════════════════════════════════════════

def _l2_normalize(vec: list[float]) -> list[float]:
    """L2 归一化：将向量缩放到单位长度，使余弦相似度等价于点积。"""
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """余弦相似度 = 两向量夹角的余弦值，范围 [-1, 1]，越大越相似。"""
    if len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    n1 = math.sqrt(sum(a * a for a in vec1))
    n2 = math.sqrt(sum(b * b for b in vec2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


# ════════════════════════════════════════════════════════════════════
#  全局单例工厂
# ════════════════════════════════════════════════════════════════════

_default_embedding: EmbeddingProvider | None = None


def get_embedding_service() -> EmbeddingProvider:
    """获取 Embedding 服务单例。

    切换策略：
      - 环境变量 EMBEDDING_MODE=mock  → MockEmbedding（测试用）
      - 环境变量 EMBEDDING_MODE=hash  → HashEmbedding（轻量）
      - 默认                          → SentenceTransformerEmbedding（生产推荐）

    设置方法（.env 文件或命令行）：
      EMBEDDING_MODE=mock  python -m uvicorn main:app
    """
    global _default_embedding
    if _default_embedding is not None:
        return _default_embedding

    mode = os.getenv("EMBEDDING_MODE", "sentence_transformer").lower()

    if mode == "mock":
        logger.info("Embedding mode: MockEmbedding (no semantic understanding, test-only)")
        _default_embedding = MockEmbedding()
    elif mode == "hash":
        logger.info("Embedding mode: HashEmbedding (TF-IDF, no cross-language)")
        _default_embedding = HashEmbedding()
    else:
        # 默认：真实语义 Embedding，生产环境推荐
        model_name = os.getenv("EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
        try:
            logger.info("Embedding mode: SentenceTransformer (%s)", model_name)
            _default_embedding = SentenceTransformerEmbedding(model_name)
        except Exception as e:
            # 模型加载失败时自动降级，避免服务启动失败
            logger.warning("SentenceTransformer failed (%s), falling back to MockEmbedding", e)
            _default_embedding = MockEmbedding()

    return _default_embedding


def reset_embedding_service() -> None:
    """重置单例（测试场景或切换模型时使用）。"""
    global _default_embedding
    _default_embedding = None
