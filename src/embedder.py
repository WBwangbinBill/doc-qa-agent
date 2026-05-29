"""向量化模块 — sentence-transformers 独立运行"""
import logging

logger = logging.getLogger(__name__)


class Embedder:
    """文本向量化器。使用 sentence-transformers 本地模型。"""

    def __init__(self, config: dict):
        emb_cfg = config.get("embedding", {})
        self.dimension = emb_cfg.get("dimension", 1024)
        self._model = None
        self._init_model(emb_cfg)

    def _init_model(self, cfg: dict):
        """初始化 sentence-transformers 模型"""
        model_name = cfg.get("model", "paraphrase-multilingual-MiniLM-L12-v2")
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"加载模型: {model_name}")
            self._model = SentenceTransformer(model_name, local_files_only=True)
            # 更新实际维度
            self.dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"模型加载完成, 维度: {self.dimension}")
        except ImportError:
            raise ImportError("sentence-transformers 未安装。pip install sentence-transformers")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化"""
        if not texts:
            return []
        embeddings = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """单条查询向量化"""
        return self.embed([text])[0]
