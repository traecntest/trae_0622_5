"""ChromaDB 向量数据库管理器"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np


@dataclass
class SearchResult:
    """语义检索结果"""
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    paper_title: str
    section: Optional[str] = None


class VectorDatabase:
    """ChromaDB 向量数据库封装"""

    def __init__(self, persist_directory: str, collection_name: str = "research_papers"):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
                Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=Settings(anonymized_telemetry=False),
                )
            except ImportError:
                raise RuntimeError(
                    "chromadb 未安装。请运行: pip install chromadb"
                )
        return self._client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_client()
            try:
                self._collection = client.get_collection(self.collection_name)
            except Exception:
                self._collection = client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
        return self._collection

    def count(self) -> int:
        return self._get_collection().count()

    def add_chunks(self, chunks: List[Any], embeddings: np.ndarray,
                    paper_metadata: Dict[str, Any], embedding_dim: int):
        if not chunks:
            return

        collection = self._get_collection()
        ids = []
        documents = []
        metadatas = []
        embeddings_list = []

        for i, chunk in enumerate(chunks):
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            meta = {
                **paper_metadata,
                "chunk_id": chunk.chunk_id,
                "section": chunk.section or "",
                "page": chunk.page,
            }
            metadatas.append(meta)
            if i < len(embeddings):
                emb_list = embeddings[i].tolist()
                if len(emb_list) != embedding_dim:
                    emb_list = emb_list + [0.0] * (embedding_dim - len(emb_list))
                embeddings_list.append(emb_list)

        if embeddings_list:
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings_list,
            )
        else:
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

    def search(self, query_embedding: np.ndarray, top_k: int = 5,
                filter_metadata: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        collection = self._get_collection()
        query_list = query_embedding.tolist()

        if filter_metadata:
            results = collection.query(
                query_embeddings=[query_list],
                n_results=min(top_k, max(1, self.count())),
                where=filter_metadata,
                include=["documents", "metadatas", "distances"],
            )
        else:
            results = collection.query(
                query_embeddings=[query_list],
                n_results=min(top_k, max(1, self.count())),
                include=["documents", "metadatas", "distances"],
            )

        search_results = []
        if results and results.get("ids"):
            for i in range(len(results["ids"][0])):
                score = 1.0 - (results["distances"][0][i] if results.get("distances") else 0.0)
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                search_results.append(SearchResult(
                    chunk_id=results["ids"][0][i],
                    text=results["documents"][0][i] if results.get("documents") else "",
                    score=score,
                    metadata=meta,
                    paper_title=meta.get("title", ""),
                    section=meta.get("section") or None,
                ))
        return search_results

    def delete_by_filename(self, filename: str):
        collection = self._get_collection()
        try:
            results = collection.get(
                where={"filename": filename},
                include=[],
            )
            if results and results.get("ids"):
                collection.delete(ids=results["ids"])
        except Exception:
            pass

    def list_papers(self) -> List[Dict[str, Any]]:
        collection = self._get_collection()
        try:
            all_data = collection.get(include=["metadatas"])
            seen = {}
            if all_data and all_data.get("metadatas"):
                for meta in all_data["metadatas"]:
                    fn = meta.get("filename", "")
                    if fn and fn not in seen:
                        seen[fn] = {
                            "filename": fn,
                            "title": meta.get("title", fn),
                            "authors": meta.get("authors", ""),
                            "year": meta.get("year", ""),
                            "file_path": meta.get("file_path", ""),
                        }
            return list(seen.values())
        except Exception:
            return []

    def clear(self):
        client = self._get_client()
        try:
            client.delete_collection(self.collection_name)
            self._collection = None
        except Exception:
            pass
