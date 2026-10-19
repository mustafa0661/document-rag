"""Bileşenlerin somut sınıflarla birbirine bağlandığı tek yer (composition root).

Servisler yalnızca arayüzleri tanır; hangi parser, chunker, embedding modeli ve
vektör deposunun kullanılacağına burada karar verilir. Betikler ve ileride
arayüz aynı fonksiyonu kullanır.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import RagSettings
from app.core.models import IndexConfig
from app.services.indexing_service import IndexingService
from app.services.ingestion_service import IngestionService
from app.services.question_answer_service import QuestionAnswerService
from app.services.retrieval_service import RetrievalService


@dataclass(frozen=True)
class RagPipeline:
    ingestion: IngestionService
    indexing: IndexingService
    retrieval: RetrievalService
    question_answering: QuestionAnswerService


def build_pipeline(settings: RagSettings, chroma_path: Path | None = None) -> RagPipeline:
    """Tüm bileşenleri kurar ve modelleri yükler.

    Ağır kütüphaneler (Docling, torch, ChromaDB) burada import edilir: bu modülü
    import etmek ucuzdur, arayüz ilk ekranı modeller yüklenmeden çizebilir ve
    testler sahte bir pipeline'ı kolayca enjekte edebilir.

    Raises:
        IndexConfigMismatchError: Mevcut indeks farklı ayarlarla oluşturulmuşsa.
    """
    from app.infrastructure.bge_embedding import BgeM3EmbeddingProvider
    from app.infrastructure.chroma_store import ChromaVectorStore
    from app.infrastructure.docling_parser import DoclingParser
    from app.infrastructure.markdown_chunker import MarkdownChunker
    from app.infrastructure.ollama_llm import OllamaLlmProvider

    embedder = BgeM3EmbeddingProvider(
        settings.embedding_model,
        settings.embedding_dimension,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )
    chunker = MarkdownChunker(embedder.count_tokens, settings.chunk_size, settings.chunk_overlap)
    config = IndexConfig(
        embedder.model_name,
        embedder.dimension,
        settings.chunk_size,
        settings.chunk_overlap,
        chunker.version,
    )
    store = ChromaVectorStore(chroma_path or settings.chroma_path, settings.collection_name, config)
    retrieval = RetrievalService(embedder, store, settings.top_k)
    llm = OllamaLlmProvider(
        model=settings.llm_model,
        host=settings.ollama_host,
        temperature=settings.llm_temperature,
        num_ctx=settings.llm_num_ctx,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return RagPipeline(
        ingestion=IngestionService(DoclingParser()),
        indexing=IndexingService(chunker, embedder, store, batch_size=settings.embedding_batch_size),
        retrieval=retrieval,
        question_answering=QuestionAnswerService(
            retrieval,
            llm,
            embedder.count_tokens,
            max_context_tokens=settings.max_context_tokens,
            top_k=settings.top_k,
            max_distance=settings.max_distance,
        ),
    )
