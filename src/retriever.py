"""检索模块 — Embedding + BM25 混合检索"""
import logging
import math
import pickle
import hashlib
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass

import jieba

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


class BM25:
    """轻量 BM25 实现（jieba 分词）"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: list[list[str]] = []
        self._doc_len: list[int] = []
        self._avgdl: float = 0.0
        self._df: dict[str, int] = defaultdict(int)  # doc frequency
        self._idf: dict[str, float] = {}

    def index(self, texts: list[str]):
        """构建 BM25 索引"""
        self._docs = [jieba.lcut(t) for t in texts]
        self._doc_len = [len(d) for d in self._docs]
        self._avgdl = sum(self._doc_len) / max(len(self._docs), 1)

        # 统计文档频率
        for doc in self._docs:
            for term in set(doc):
                self._df[term] += 1

        # 预计算 IDF
        N = len(self._docs)
        for term, df in self._df.items():
            self._idf[term] = math.log((N - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query: str) -> list[float]:
        """计算 query 与每篇文档的 BM25 分数"""
        query_terms = jieba.lcut(query)
        scores = []
        for doc, doc_len in zip(self._docs, self._doc_len):
            s = 0.0
            tf = defaultdict(int)
            for t in doc:
                tf[t] += 1
            for term in query_terms:
                if term not in self._idf:
                    continue
                idf = self._idf[term]
                term_tf = tf.get(term, 0)
                numerator = term_tf * (self.k1 + 1)
                denominator = term_tf + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl)
                s += idf * numerator / max(denominator, 0.001)
            scores.append(s)
        return scores


class Retriever:
    """Embedding + BM25 混合检索器"""

    EMBED_WEIGHT = 0.7
    BM25_WEIGHT = 0.3
    HYBRID_TRIGGER = 0.45  # 当 max embedding 低于此值时启用 BM25 混合

    def __init__(self, embedder: Embedder, config: dict):
        self.embedder = embedder
        ret_cfg = config.get("retrieval", {})
        self.top_k = ret_cfg.get("top_k", 5)
        self.score_threshold = ret_cfg.get("score_threshold", 0.38)
        self._chunks: list[Chunk] = []
        self._embeddings: list[list[float]] = []
        self._bm25: BM25 | None = None

    def build_index(self, chunks: list[Chunk]):
        """构建 Embedding + BM25 索引"""
        self._chunks = chunks
        texts = [c.content for c in chunks]

        logger.info(f"向量化 {len(texts)} 个文本块...")
        self._embeddings = self.embedder.embed(texts)

        logger.info("构建 BM25 关键词索引...")
        self._bm25 = BM25()
        self._bm25.index(texts)

        logger.info(f"混合索引构建完成，共 {len(chunks)} 条")

    def save(self, cache_dir: str, pdf_path: str):
        """持久化索引到磁盘"""
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)
        pdf_hash = hashlib.md5(pdf_path.encode()).hexdigest()[:8]
        cache_file = cache_path / f"index_{pdf_hash}.pkl"
        data = {
            "chunks": self._chunks,
            "embeddings": self._embeddings,
            "bm25": self._bm25,
        }
        with open(cache_file, "wb") as f:
            pickle.dump(data, f)
        logger.info(f"索引已保存到 {cache_file}")

    def load(self, cache_dir: str, pdf_path: str) -> bool:
        """从磁盘加载索引"""
        cache_path = Path(cache_dir)
        pdf_hash = hashlib.md5(pdf_path.encode()).hexdigest()[:8]
        cache_file = cache_path / f"index_{pdf_hash}.pkl"
        if cache_file.exists():
            with open(cache_file, "rb") as f:
                data = pickle.load(f)
            self._chunks = data["chunks"]
            self._embeddings = data["embeddings"]
            self._bm25 = data.get("bm25")
            logger.info(f"索引从缓存加载: {cache_file}，共 {len(self._chunks)} 块")
            return True
        return False

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        """条件混合检索：语义为主，低分时 BM25 兜底"""
        if not self._chunks:
            raise RuntimeError("索引未构建")

        # Embedding 分数
        query_vec = self.embedder.embed_query(query)
        emb_scores = []
        for chunk_vec in self._embeddings:
            sim = self._cosine_similarity(query_vec, chunk_vec)
            emb_scores.append(sim)

        max_emb = max(emb_scores) if emb_scores else 0.0

        # 判断是否需要 BM25 兜底
        if max_emb >= self.HYBRID_TRIGGER:
            # 语义足够强，纯 embedding 排名
            combined = []
            for i, emb in enumerate(emb_scores):
                if emb >= self.score_threshold:
                    combined.append((i, emb))
            mode = "embedding"
        else:
            # 语义弱，启用 BM25 混合
            bm25_scores = self._bm25.score(query) if self._bm25 else [0.0] * len(self._chunks)
            bm25_max = max(bm25_scores) if bm25_scores else 1.0

            combined = []
            for i in range(len(self._chunks)):
                emb_norm = emb_scores[i] / max(max_emb, 0.001)
                bm25_norm = bm25_scores[i] / max(bm25_max, 0.001)
                hybrid = self.EMBED_WEIGHT * emb_norm + self.BM25_WEIGHT * bm25_norm
                if hybrid >= self.score_threshold * 0.5:
                    combined.append((i, hybrid))
            mode = "hybrid"

        combined.sort(key=lambda x: x[1], reverse=True)
        top = combined[:self.top_k]

        retrieved = []
        for idx, score in top:
            chunk = self._chunks[idx]
            retrieved.append(RetrievedChunk(
                content=chunk.content,
                score=round(score, 4),
                page_num=chunk.page_num,
                chunk_type=chunk.chunk_type,
            ))

        logger.info(
            f"检索[{mode}] '{query[:30]}...' → {len(retrieved)} 条 (max_emb={max_emb:.3f})"
        )
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
