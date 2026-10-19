"""RAG bileşenlerinin ayarları: tek yerde, varsayılanlarıyla.

Ortam değişkenleriyle değiştirilebilen ayarlar yalnızca makineye göre
değişenlerdir (veritabanı yolu, embedding cihazı, Ollama adresi ve modeli). Model ve chunk ayarları
indeksin kimliğinin parçası olduğu için kodda sabit tutulur; değiştirilirse
mevcut indeks `IndexConfigMismatchError` ile reddedilir.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RagSettings:
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024
    embedding_device: str = "cpu"
    embedding_batch_size: int = 16
    chunk_size: int = 500        # embedding modelinin tokenlarıyla, başlık ve overlap dahil
    chunk_overlap: int = 75
    chroma_path: Path = field(default_factory=lambda: Path("data/chroma"))
    collection_name: str = "document_chunks"
    top_k: int = 5
    # Soru-cevap (LLM)
    llm_model: str = "qwen3:4b-instruct"
    ollama_host: str = "http://localhost:11434"
    llm_temperature: float = 0.1
    llm_num_ctx: int = 8192          # bağlam (~3000) + prompt + cevap için geniş pay
    llm_timeout_seconds: float = 120.0
    max_context_tokens: int = 3000   # LLM'e verilen kaynak metinlerinin toplam bütçesi
    max_distance: float | None = None  # gerçek veriyle ölçülene kadar eşik yok
    # Arayüz
    upload_dir: Path = field(default_factory=lambda: Path("data/uploads"))
    max_upload_mb: int = 25

    @classmethod
    def from_env(cls) -> "RagSettings":
        defaults = cls()
        return cls(
            chroma_path=Path(os.getenv("RAG_CHROMA_PATH", str(defaults.chroma_path))),
            embedding_device=os.getenv("RAG_EMBEDDING_DEVICE", defaults.embedding_device),
            ollama_host=os.getenv("RAG_OLLAMA_HOST", defaults.ollama_host),
            llm_model=os.getenv("RAG_LLM_MODEL", defaults.llm_model),
            upload_dir=Path(os.getenv("RAG_UPLOAD_DIR", str(defaults.upload_dir))),
        )
