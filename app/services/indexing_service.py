"""İndeksleme akışı: IngestedDocument → chunk → embedding → vektör deposu."""

import logging

from app.core.models import IndexingResult, IndexingStatus, IngestedDocument
from app.interfaces.embedding_provider import EmbeddingProvider
from app.interfaces.text_chunker import TextChunker
from app.interfaces.vector_store import VectorStore
from app.services.embedding_validation import validate_embeddings

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(
        self,
        chunker: TextChunker,
        embedder: EmbeddingProvider,
        store: VectorStore,
        batch_size: int = 32,
    ) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._batch_size = batch_size

    def index_document(self, document: IngestedDocument, reindex: bool = False) -> IndexingResult:
        """Belgeyi indeksler.

        Belge zaten indeksliyse atlanır: `document_id` içeriğin özeti olduğu ve
        indeks ayarları açılışta doğrulandığı için aynı belge aynı chunk'ları
        üretir. `reindex=True` eski chunk'ları silip yeniden oluşturur.
        """
        existing = self._store.count_document_chunks(document.document_id)
        if existing and not reindex:
            return self._result(document, IndexingStatus.SKIPPED, existing)
        if existing:
            self._store.delete_document(document.document_id)

        chunks = self._chunker.chunk(document)
        if not chunks:
            logger.warning("'%s' içinde indekslenecek metin yok.", document.file_name)
            return self._result(document, IndexingStatus.EMPTY, 0)

        try:
            for start in range(0, len(chunks), self._batch_size):
                batch = chunks[start : start + self._batch_size]
                embeddings = self._embedder.embed_documents([chunk.text for chunk in batch])
                validate_embeddings(embeddings, len(batch), self._embedder.dimension)
                self._store.add(batch, embeddings)
        except Exception:
            # Yarım kalmış belge "indeksli" görünüp sonraki denemede atlanmasın.
            self._store.delete_document(document.document_id)
            raise
        return self._result(document, IndexingStatus.INDEXED, len(chunks))

    def indexed_chunk_count(self, document_id: str) -> int:
        """Belgenin indeksteki chunk sayısı; 0 ise belge indeksli değildir."""
        return self._store.count_document_chunks(document_id)

    def remove_document(self, document_id: str) -> int:
        return self._store.delete_document(document_id)

    @staticmethod
    def _result(document: IngestedDocument, status: IndexingStatus, count: int) -> IndexingResult:
        return IndexingResult(document.document_id, document.file_name, status, count)
