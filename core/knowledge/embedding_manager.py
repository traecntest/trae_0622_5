"""向量嵌入管理器"""
import os
import logging
from typing import List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """基于 Sentence Transformers 的向量嵌入管理器"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._dimension = None
        self._model_loading_failed = False

    def preload_model(self) -> bool:
        """预加载模型（建议在主线程调用）"""
        try:
            self._load_model()
            return self._model is not None
        except Exception as e:
            logger.error(f"预加载模型失败: {e}")
            self._model_loading_failed = True
            return False

    def is_model_ready(self) -> bool:
        return self._model is not None

    def _load_model(self):
        if self._model is not None:
            return self._model
        if self._model_loading_failed:
            raise RuntimeError(
                f"模型加载已失败过，跳过重试。请检查网络连接后重启程序，"
                f"或手动下载模型: {self.model_name}"
            )
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"正在加载模型: {self.model_name} (设备: {self.device})")
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"模型加载完成，维度: {self._dimension}")
        except ImportError:
            raise RuntimeError(
                "sentence-transformers 未安装。请运行: pip install sentence-transformers"
            )
        except Exception as e:
            self._model_loading_failed = True
            logger.error(f"模型加载失败: {e}")
            raise RuntimeError(
                f"加载模型 '{self.model_name}' 失败: {e}\n"
                f"请检查:\n"
                f"1. 网络连接是否正常（首次运行需要下载模型）\n"
                f"2. 是否有足够的磁盘空间\n"
                f"3. 设备设置是否正确 (cpu/cuda)"
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
        try:
            model = self._load_model()
            logger.info(f"正在编码 {len(texts)} 个文本块...")
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            logger.info(f"编码完成，形状: {embeddings.shape}")
            return embeddings
        except Exception as e:
            logger.error(f"向量编码失败: {e}")
            raise RuntimeError(f"生成向量嵌入失败: {e}")

    def encode_single(self, text: str) -> np.ndarray:
        result = self.encode([text])
        return result[0] if len(result) > 0 else np.array([])
