"""Arama akışı: soru → embedding → belge filtresiyle vektör araması."""

from app.core.exceptions import InvalidQueryError
from app.core.models import RetrievedChunk
from app.interfaces.embedding_provider import EmbeddingProvider
from app.interfaces.vector_store import VectorStore
from app.services.embedding_validation import validate_embeddings


class RetrievalService:
    def __init__(self, embedder: EmbeddingProvider, store: VectorStore, default_top_k: int = 5) -> None:
        self._embedder = embedder
        self._store = store
        self._default_top_k = default_top_k

    def search(
        self, query: str, document_ids: list[str], top_k: int | None = None
    ) -> list[RetrievedChunk]:
        """Yalnızca verilen belgeler içinde, alakaya göre sıralı sonuç döndürür.

        `document_ids` zorunludur: "tüm belgelerde ara" varsayılanı bilinçli
        olarak yoktur, belge izolasyonu bir varsayılana bırakılmaz.
        Benzerlik eşiği uygulanmaz; mesafeler olduğu gibi döner.
        """
        if not query or not query.strip():
            raise InvalidQueryError("Sorgu boş olamaz.")
        ids = list(dict.fromkeys(document_ids))
        if not ids:
            raise InvalidQueryError("Aranacak en az bir belge seçilmeli.")
        k = self._default_top_k if top_k is None else top_k
        if k < 1:
            raise InvalidQueryError("top_k en az 1 olmalı.")

        embedding = self._embedder.embed_query(query.strip())
        validate_embeddings([embedding], 1, self._embedder.dimension)
        results = self._store.query(embedding, ids, k)
        return sorted(results, key=lambda item: item.distance)
