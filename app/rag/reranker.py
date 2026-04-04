"""BGE Reranker — Phase 4 enhancement for post-retrieval re-scoring."""

from langchain_core.documents import Document
from loguru import logger


class BGEReranker:
    """Wraps BAAI/bge-reranker-v2-m3 for cross-encoder re-scoring."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", top_k: int = 3):
        self.top_k = top_k
        self._model = None
        self._model_name = model_name

    def _load_model(self):
        if self._model is None:
            try:
                from FlagEmbedding import FlagReranker
                logger.info(f"Loading reranker: {self._model_name}")
                self._model = FlagReranker(self._model_name, use_fp16=True)
            except ImportError:
                logger.warning("FlagEmbedding not installed — reranker disabled")
                self._model = None

    def rerank(self, query: str, docs: list[Document]) -> list[Document]:
        """Re-score and sort docs by cross-encoder score, return top_k."""
        self._load_model()
        if self._model is None or not docs:
            return docs[: self.top_k]

        pairs = [[query, doc.page_content] for doc in docs]
        scores = self._model.compute_score(pairs, normalize=True)

        scored = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        top = [doc for _, doc in scored[: self.top_k]]
        logger.debug(f"Reranker: {len(docs)} → {len(top)} docs (top score: {scored[0][0]:.3f})")
        return top
