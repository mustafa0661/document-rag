"""Vektör deposu sözleşmesi."""

from abc import ABC, abstractmethod

from app.core.models import Chunk, RetrievedChunk


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Chunk'ları vektörleriyle kaydeder. Aynı `chunk_id` tekrar gelirse güncellenir."""

    @abstractmethod
    def count_document_chunks(self, document_id: str) -> int:
        """Belgeye ait kayıtlı chunk sayısı; belge indeksli değilse 0."""

    @abstractmethod
    def document_file_name(self, document_id: str) -> str | None:
        """Belgenin indekste kayıtlı dosya adı; belge indeksli değilse None.

        Aynı içerik (aynı document_id) farklı adla yeniden yüklendiğinde
        kaynak gösteriminin tutarlı kalması için ilk kayıttaki ad kullanılır.
        """

    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        """Belgenin tüm chunk'larını siler ve silinen sayıyı döndürür."""

    @abstractmethod
    def query(
        self, embedding: list[float], document_ids: list[str], top_k: int
    ) -> list[RetrievedChunk]:
        """Yalnızca verilen belgeler içinde arar; sonuçlar mesafeye göre artan sıradadır."""
