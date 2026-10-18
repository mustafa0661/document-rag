"""RAG bileşenlerinin ayarları: tek yerde, varsayılanlarıyla.

Ortam değişkenleriyle değiştirilebilen ayarlar yalnızca makineye göre
değişenlerdir (veritabanı yolu, embedding cihazı). Model ve chunk ayarları
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

    @classmethod
    def from_env(cls) -> "RagSettings":
        defaults = cls()
        return cls(
            chroma_path=Path(os.getenv("RAG_CHROMA_PATH", str(defaults.chroma_path))),
            embedding_device=os.getenv("RAG_EMBEDDING_DEVICE", defaults.embedding_device),
        )
