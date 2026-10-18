"""ChromaDB tabanlı kalıcı vektör deposu.

- Koleksiyon kosinüs mesafesiyle oluşturulur.
- `embedding_function=None`: ChromaDB'nin kendi varsayılan modeli hiçbir
  zaman indirilmez veya kullanılmaz; tüm vektörler EmbeddingProvider'dan gelir.
- `IndexConfig` koleksiyon metadata'sına yazılır ve her açılışta AÇIKÇA
  karşılaştırılır. Gerekçe: ChromaDB, mevcut bir koleksiyon farklı metadata
  ile `get_or_create_collection` çağrısıyla açıldığında eski metadata'yı
  sessizce korur (denenerek doğrulandı); model adını da hiç kontrol etmez.
"""

from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError

from app.core.exceptions import EmbeddingDimensionError, IndexConfigMismatchError
from app.core.models import Chunk, IndexConfig, RetrievedChunk
from app.interfaces.vector_store import VectorStore

_WRITE_BATCH_SIZE = 1000  # ChromaDB'nin tek istekteki üst sınırının (5461) altında


class ChromaVectorStore(VectorStore):
    def __init__(self, path: Path, collection_name: str, index_config: IndexConfig) -> None:
        self._index_config = index_config
        self._client = chromadb.PersistentClient(
            path=str(path), settings=Settings(anonymized_telemetry=False)
        )
        try:
            collection = self._client.get_collection(collection_name, embedding_function=None)
        except NotFoundError:
            collection = self._client.create_collection(
                collection_name,
                configuration={"hnsw": {"space": "cosine"}},
                metadata=index_config.to_metadata(),
                embedding_function=None,
            )
        else:
            _ensure_compatible(collection_name, collection.metadata or {}, index_config)
        self._collection = collection

    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise EmbeddingDimensionError(
                f"{len(chunks)} chunk için {len(embeddings)} embedding verildi."
            )
        for start in range(0, len(chunks), _WRITE_BATCH_SIZE):
            batch = chunks[start : start + _WRITE_BATCH_SIZE]
            self._collection.upsert(
                ids=[chunk.chunk_id for chunk in batch],
                embeddings=embeddings[start : start + _WRITE_BATCH_SIZE],
                documents=[chunk.text for chunk in batch],
                metadatas=[_to_metadata(chunk) for chunk in batch],
            )

    def count_document_chunks(self, document_id: str) -> int:
        return len(self._collection.get(where={"document_id": document_id}, include=[])["ids"])

    def delete_document(self, document_id: str) -> int:
        ids = self._collection.get(where={"document_id": document_id}, include=[])["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def query(
        self, embedding: list[float], document_ids: list[str], top_k: int
    ) -> list[RetrievedChunk]:
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"document_id": {"$in": list(document_ids)}},
            include=["documents", "metadatas", "distances"],
        )
        retrieved = [
            RetrievedChunk(chunk=_to_chunk(chunk_id, text, metadata), distance=float(distance))
            for chunk_id, text, metadata, distance in zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            )
        ]
        return sorted(retrieved, key=lambda item: item.distance)

    def count(self) -> int:
        return self._collection.count()


def delete_collection(path: Path, collection_name: str) -> bool:
    """İndeksi tamamen siler (ör. model değişikliğinden sonra yeniden oluşturmak için).

    Bilinçli olarak VectorStore arayüzünün dışında: yalnızca açık bir kullanıcı
    komutuyla çağrılmalı, uygulama akışında otomatik çağrılmamalıdır.
    """
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    try:
        client.delete_collection(collection_name)
    except NotFoundError:
        return False
    return True


def _ensure_compatible(name: str, stored: dict, expected: IndexConfig) -> None:
    expected_metadata = expected.to_metadata()
    differences = [
        f"{key}: indekste={stored.get(key)!r}, ayarlarda={value!r}"
        for key, value in expected_metadata.items()
        if stored.get(key) != value
    ]
    if differences:
        raise IndexConfigMismatchError(
            f"'{name}' indeksi farklı ayarlarla oluşturulmuş; kullanılırsa sonuçlar "
            f"anlamsız olur. Farklar: {'; '.join(differences)}. "
            "İndeksi yeniden oluşturmak için: "
            "python -m app.scripts.search_documents --reset-index ..."
        )


def _to_metadata(chunk: Chunk) -> dict[str, str | int]:
    return {
        "document_id": chunk.document_id,
        "file_name": chunk.file_name,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "token_count": chunk.token_count,
    }


def _to_chunk(chunk_id: str, text: str, metadata: dict) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=str(metadata["document_id"]),
        file_name=str(metadata["file_name"]),
        page_number=int(metadata["page_number"]),
        chunk_index=int(metadata["chunk_index"]),
        text=text,
        token_count=int(metadata["token_count"]),
    )
