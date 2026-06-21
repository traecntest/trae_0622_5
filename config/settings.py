"""系统全局配置管理"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "pdfs"
CHROMA_DIR = DATA_DIR / "chroma_db"
EXPORT_DIR = DATA_DIR / "exports"
CONFIG_FILE = DATA_DIR / "config.json"

for d in [DATA_DIR, PDF_DIR, CHROMA_DIR, EXPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class LLMConfig:
    """LLM API 配置"""
    provider: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.3


@dataclass
class EmbeddingConfig:
    """向量嵌入配置"""
    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"
    chunk_size: int = 500
    chunk_overlap: int = 50


@dataclass
class AppConfig:
    """应用全局配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    pdf_dir: str = str(PDF_DIR)
    chroma_dir: str = str(CHROMA_DIR)
    export_dir: str = str(EXPORT_DIR)
    max_threads: int = 4
    collection_name: str = "research_papers"

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls) -> "AppConfig":
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                llm = LLMConfig(**data.get("llm", {}))
                embedding = EmbeddingConfig(**data.get("embedding", {}))
                return cls(
                    llm=llm,
                    embedding=embedding,
                    pdf_dir=data.get("pdf_dir", str(PDF_DIR)),
                    chroma_dir=data.get("chroma_dir", str(CHROMA_DIR)),
                    export_dir=data.get("export_dir", str(EXPORT_DIR)),
                    max_threads=data.get("max_threads", 4),
                    collection_name=data.get("collection_name", "research_papers"),
                )
            except Exception:
                pass
        return cls()
