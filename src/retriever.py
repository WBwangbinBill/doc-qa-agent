"""检索模块 — 内存余弦相似度检索"""
import logging
import math
from dataclasses import dataclass

from src.chunker import Chunk
from src.embedder import Embedder

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """检索结果"""
    content: str
    score: float
    page_num: int
    chunk_type: str


class Retriever:
    """基于内存余弦相似度的检索器"""

    def __init__(self, embedder: Embedder, config: dict):
        self.embedder = embedder
        ret_cfg = config.get("retrieval", {})
        self.top_k = ret_cfg.get("top_k", 5)
        self.score_threshold = ret_cfg.get("score_threshold", 0.3)
        self._chunks: list[Chunk] = []
        self._embeddings: list[list[float]] = []

    def build_index(self, chunks: list[Chunk]):
        """计算所有 chunk 的向量并存储"""
        self._chunks = chunks
        texts = [c.content for c in chunks]

        logger.info(f"向量化 {len(texts)} 个文本块...")
        self._embeddings = self.embedder.embed(texts)
        logger.info(f"索引构建完成，共 {len(chunks)} 条")

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        """余弦相似度检索"""
        if not self._chunks:
            raise RuntimeError("索引未构建")

        query_vec = self.embedder.embed_query(query)

        # 计算余弦相似度
        scores = []
        for i, chunk_vec in enumerate(self._embeddings):
            sim = self._cosine_similarity(query_vec, chunk_vec)
            if sim >= self.score_threshold:
                scores.append((i, sim))

        # 按分数排序，取 top_k
        scores.sort(key=lambda x: x[1], reverse=True)
        top = scores[:self.top_k]

        retrieved = []
        for idx, score in top:
            chunk = self._chunks[idx]
            retrieved.append(RetrievedChunk(
                content=chunk.content,
                score=round(score, 4),
                page_num=chunk.page_num,
                chunk_type=chunk.chunk_type,
            ))

        logger.info(f"检索 '{query[:30]}...' → {len(retrieved)} 条")
        return retrieved

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
