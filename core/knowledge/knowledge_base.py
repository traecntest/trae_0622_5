"""文献知识库 - 整合 PDF 解析、向量嵌入与语义检索"""
import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .pdf_parser import PDFParser, ParsedPaper, PaperChunk
from .embedding_manager import EmbeddingManager
from .vector_db import VectorDatabase, SearchResult


class KnowledgeBase:
    """文献知识库核心类"""

    def __init__(self, config):
        self.config = config
        self.parser = PDFParser()
        self.embedder = EmbeddingManager(
            model_name=config.embedding.model_name,
            device=config.embedding.device,
        )
        self.vector_db = VectorDatabase(
            persist_directory=config.chroma_dir,
            collection_name=config.collection_name,
        )
        self.chunk_size = config.embedding.chunk_size
        self.chunk_overlap = config.embedding.chunk_overlap
        self._parsed_cache: Dict[str, ParsedPaper] = {}

    def parse_pdf(self, pdf_path: str) -> Optional[ParsedPaper]:
        if pdf_path in self._parsed_cache:
            return self._parsed_cache[pdf_path]
        try:
            paper = self.parser.parse(pdf_path)
            self._parsed_cache[pdf_path] = paper
            return paper
        except Exception as e:
            print(f"解析 PDF 失败 {pdf_path}: {e}")
            return None

    def add_paper(self, pdf_path: str,
                    progress_cb: Optional[Callable] = None) -> bool:
        if not os.path.exists(pdf_path):
            return False

        if progress_cb:
            progress_cb(0.1, "正在解析 PDF...")

        paper = self.parse_pdf(pdf_path)
        if not paper:
            return False

        filename = Path(pdf_path).name
        self.vector_db.delete_by_filename(filename)

        if progress_cb:
            progress_cb(0.3, "正在分块处理...")

        chunks = self.parser.chunk_text(
            paper, self.chunk_size, self.chunk_overlap
        )

        if not chunks:
            return False

        if progress_cb:
            progress_cb(0.5, "正在生成向量嵌入...")

        texts = [c.text for c in chunks]
        embeddings = self.embedder.encode(texts)

        if progress_cb:
            progress_cb(0.8, "正在写入向量数据库...")

        metadata = paper.get_metadata()
        self.vector_db.add_chunks(
            chunks, embeddings, metadata, self.embedder.dimension
        )

        if progress_cb:
            progress_cb(1.0, "完成")

        return True

    def add_papers_batch(self, pdf_paths: List[str],
                            progress_cb: Optional[Callable] = None) -> Dict[str, bool]:
        results = {}
        total = len(pdf_paths)
        for i, path in enumerate(pdf_paths):
            def make_cb(idx):
                def cb(pct, msg=""):
                    if progress_cb:
                        overall = (idx + pct) / total if total > 0 else 0
                        progress_cb(overall, f"[{idx + 1}/{total}] {msg}")
                return cb

            results[path] = self.add_paper(path, make_cb(i))
        return results

    def semantic_search(self, query: str, top_k: int = 5,
                          filter_metadata: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        if not query:
            return []
        query_emb = self.embedder.encode_single(query)
        if len(query_emb) == 0:
            return []
        return self.vector_db.search(query_emb, top_k, filter_metadata)

    def list_papers(self) -> List[Dict[str, Any]]:
        return self.vector_db.list_papers()

    def count_chunks(self) -> int:
        return self.vector_db.count()

    def remove_paper(self, filename: str):
        self.vector_db.delete_by_filename(filename)
        cache_key = None
        for k in self._parsed_cache:
            if Path(k).name == filename:
                cache_key = k
                break
        if cache_key:
            del self._parsed_cache[cache_key]

    def clear_all(self):
        self.vector_db.clear()
        self._parsed_cache.clear()

    def get_parsed_paper(self, pdf_path: str) -> Optional[ParsedPaper]:
        return self._parsed_cache.get(pdf_path) or self.parse_pdf(pdf_path)

    def scan_pdf_directory(self, pdf_dir: str) -> List[str]:
        pdf_files = []
        for root, _, files in os.walk(pdf_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))
        return pdf_files
