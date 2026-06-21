"""向量嵌入管理器"""
import os
from typing import List, Optional
import numpy as np


class EmbeddingManager:
    """基于 Sentence Transformers 的向量嵌入管理器"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._dimension = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, device=self.device)
                self._dimension = self._model.get_sentence_embedding_dimension()
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers 未安装。请运行: pip install sentence-transformers"
                )
        return self._model

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load_model()
        return self._dimension

    def encode(self, texts: List[str], batch_size: int = 32,
                show_progress: bool = False) -> np.ndarray:
        if not texts:
            return np.array([])
        model = self._load_model()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings

    def encode_single(self, text: str) -> np.ndarray:
        result = self.encode([text])
        return result[0] if len(result) > 0 else np.array([])
