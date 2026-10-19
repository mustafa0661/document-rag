"""ChromaVectorStore + IndexingService + RetrievalService birim testleri.

Gerçek (geçici klasörde) ChromaDB ve sahte, kelime tabanlı embedding kullanılır.
Anlamsal ve diller arası arama gerçek modelle test_bge_retrieval.py içinde sınanır.
"""

import pytest
from chromadb.api.client import SharedSystemClient

from app.core.exceptions import EmbeddingDimensionError, IndexConfigMismatchError, InvalidQueryError
from app.core.models import IndexConfig, IndexingStatus
from app.infrastructure.chroma_store import ChromaVectorStore, delete_collection
from app.infrastructure.markdown_chunker import MarkdownChunker
from app.services.indexing_service import IndexingService
from app.services.retrieval_service import RetrievalService
from tests.fakes import FailingProvider, HashingEmbeddingProvider, WrongDimensionProvider, make_document

COLLECTION = "test_chunks"

TURKISH_PAGES = [
    "Hastanın kan tahlili sonuçları normaldir. Glukoz değeri 98 mg/dL olarak ölçüldü.",
    "Kontrol randevusu bir ay sonra kardiyoloji polikliniğinde yapılacaktır.",
    "Hasta günde iki kez tok karnına ilacını almalıdır.",
]
ENGLISH_PAGES = [
    "The invoice total amount is 450 dollars including tax.",
    "Payment is due next Friday by bank transfer.",
    "Shipping takes five business days to Ankara.",
]


def _config(**overrides) -> IndexConfig:
    values = dict(
        embedding_model="fake-hashing",
        embedding_dimension=256,
        chunk_size=60,
        chunk_overlap=10,
        chunker_version=MarkdownChunker.VERSION,
    )
    values.update(overrides)
    return IndexConfig(**values)


@pytest.fixture
def db_path(tmp_path):
    yield tmp_path / "chroma"
    # Aynı süreçte yeniden açma testinin gerçekten diskten okuması için önbelleği temizle.
    SharedSystemClient.clear_system_cache()


@pytest.fixture
def embedder():
    return HashingEmbeddingProvider(dimension=256)


@pytest.fixture
def store(db_path):
    return ChromaVectorStore(db_path, COLLECTION, _config())


def _services(store, embedder, batch_size=32):
    chunker = MarkdownChunker(embedder.count_tokens, chunk_size=60, chunk_overlap=10)
    return IndexingService(chunker, embedder, store, batch_size=batch_size), RetrievalService(embedder, store)


@pytest.fixture
def indexed(store, embedder):
    indexing, retrieval = _services(store, embedder)
    tr = make_document(TURKISH_PAGES, document_id="doc-tr", file_name="rapor.pdf")
    en = make_document(ENGLISH_PAGES, document_id="doc-en", file_name="invoice.pdf")
    indexing.index_document(tr)
    indexing.index_document(en)
    return indexing, retrieval


# --- Doğru chunk, sayfa ve kaynak bilgisi ----------------------------------


def test_turkish_query_finds_correct_chunk_with_source_and_page(indexed):
    _, retrieval = indexed

    results = retrieval.search("kontrol randevusu ne zaman", ["doc-tr"])

    top = results[0]
    assert "randevusu" in top.chunk.text
    assert top.chunk.page_number == 2
    assert top.chunk.file_name == "rapor.pdf"
    assert top.chunk.chunk_id == "doc-tr:p0002:c000"


def test_english_query_finds_correct_chunk(indexed):
    _, retrieval = indexed

    top = retrieval.search("when is the payment due", ["doc-en"])[0]

    assert "Payment is due" in top.chunk.text
    assert top.chunk.page_number == 2


def test_results_are_sorted_by_distance_and_limited_by_top_k(indexed):
    _, retrieval = indexed

    results = retrieval.search("glukoz değeri", ["doc-tr", "doc-en"], top_k=4)

    assert len(results) == 4
    distances = [r.distance for r in results]
    assert distances == sorted(distances)
    for result in results:
        assert result.similarity == pytest.approx(1 - result.distance)
        assert 0.0 <= result.distance <= 2.0


def test_default_top_k_is_five(indexed):
    _, retrieval = indexed
    assert len(retrieval.search("hasta", ["doc-tr", "doc-en"])) == 5


# --- Belge izolasyonu -------------------------------------------------------


def test_search_never_returns_chunks_from_other_documents(indexed):
    _, retrieval = indexed

    # Soru İngilizce belgeye ait, ama yalnızca Türkçe belgede aranıyor.
    results = retrieval.search("invoice total amount payment", ["doc-tr"], top_k=10)

    assert results
    assert {r.chunk.document_id for r in results} == {"doc-tr"}


def test_document_ids_are_required(indexed):
    _, retrieval = indexed
    with pytest.raises(InvalidQueryError):
        retrieval.search("glukoz", [])


def test_unknown_document_returns_no_results(indexed):
    _, retrieval = indexed
    assert retrieval.search("glukoz", ["doc-yok"]) == []


# --- Tekrar indeksleme, silme, boş içerik ---------------------------------


def test_reindexing_same_document_is_skipped_without_duplicates(store, embedder):
    indexing, _ = _services(store, embedder)
    document = make_document(TURKISH_PAGES, document_id="doc-tr")

    first = indexing.index_document(document)
    second = indexing.index_document(document)

    assert first.status is IndexingStatus.INDEXED
    assert second.status is IndexingStatus.SKIPPED
    assert second.chunk_count == first.chunk_count == store.count() == 3
    assert len(embedder.embedded_batches) == 1  # ikinci seferde embedding hesaplanmadı


def test_forced_reindex_replaces_chunks(store, embedder):
    indexing, _ = _services(store, embedder)
    document = make_document(TURKISH_PAGES, document_id="doc-tr")
    indexing.index_document(document)

    result = indexing.index_document(document, reindex=True)

    assert result.status is IndexingStatus.INDEXED
    assert store.count() == 3


def test_delete_document_removes_only_its_chunks(indexed, store):
    indexing, retrieval = indexed

    assert indexing.remove_document("doc-tr") == 3

    assert store.count_document_chunks("doc-tr") == 0
    assert store.count_document_chunks("doc-en") == 3
    assert retrieval.search("glukoz", ["doc-tr"]) == []


def test_empty_document_indexes_nothing(store, embedder):
    indexing, _ = _services(store, embedder)

    result = indexing.index_document(make_document(["", "  "], document_id="doc-bos"))

    assert result.status is IndexingStatus.EMPTY
    assert result.chunk_count == 0
    assert store.count() == 0


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_empty_query_is_rejected(indexed, query):
    _, retrieval = indexed
    with pytest.raises(InvalidQueryError):
        retrieval.search(query, ["doc-tr"])


def test_invalid_top_k_is_rejected(indexed):
    _, retrieval = indexed
    with pytest.raises(InvalidQueryError):
        retrieval.search("glukoz", ["doc-tr"], top_k=0)


# --- Tablo yapısı -----------------------------------------------------------


def test_markdown_table_survives_storage_roundtrip(store, embedder):
    indexing, retrieval = _services(store, embedder)
    table = "| Tetkik | Sonuç | Birim |\n|---|---|---|\n| Glukoz | 98 | mg/dL |\n| Kreatinin | 0.9 | mg/dL |"
    indexing.index_document(make_document([f"Kan tahlili sonuçları:\n\n{table}"], document_id="doc-tablo"))

    top = retrieval.search("Glukoz sonuç", ["doc-tablo"])[0]

    assert table in top.chunk.text


# --- Kalıcılık ve indeks yapılandırması -----------------------------------


def test_persistent_index_is_usable_after_reopening(db_path, embedder):
    indexing, _ = _services(ChromaVectorStore(db_path, COLLECTION, _config()), embedder)
    indexing.index_document(make_document(TURKISH_PAGES, document_id="doc-tr"))
    SharedSystemClient.clear_system_cache()  # istemciyi gerçekten kapat

    reopened = ChromaVectorStore(db_path, COLLECTION, _config())
    results = RetrievalService(embedder, reopened).search("kontrol randevusu", ["doc-tr"])

    assert reopened.count() == 3
    assert results[0].chunk.page_number == 2


@pytest.mark.parametrize(
    "changed",
    [
        {"embedding_model": "baska-model"},
        {"embedding_dimension": 384},
        {"chunk_size": 500},
        {"chunk_overlap": 0},
        {"chunker_version": "999"},
    ],
)
def test_opening_index_with_different_config_is_rejected(db_path, changed):
    ChromaVectorStore(db_path, COLLECTION, _config())
    SharedSystemClient.clear_system_cache()

    with pytest.raises(IndexConfigMismatchError) as error:
        ChromaVectorStore(db_path, COLLECTION, _config(**changed))

    assert next(iter(changed)) in str(error.value)


def test_index_can_be_rebuilt_after_explicit_reset(db_path):
    ChromaVectorStore(db_path, COLLECTION, _config())
    SharedSystemClient.clear_system_cache()

    assert delete_collection(db_path, COLLECTION) is True
    SharedSystemClient.clear_system_cache()
    rebuilt = ChromaVectorStore(db_path, COLLECTION, _config(embedding_model="baska-model"))

    assert rebuilt.count() == 0


def test_wrong_embedding_dimension_is_rejected_and_nothing_is_stored(store):
    provider = WrongDimensionProvider(dimension=256)
    indexing, retrieval = _services(store, provider)

    with pytest.raises(EmbeddingDimensionError):
        indexing.index_document(make_document(TURKISH_PAGES, document_id="doc-tr"))
    assert store.count() == 0

    with pytest.raises(EmbeddingDimensionError):
        retrieval.search("glukoz", ["doc-tr"])


def test_failure_midway_rolls_back_partial_document(store):
    provider = FailingProvider(fail_on_call=2, dimension=256)
    indexing, _ = _services(store, provider, batch_size=1)  # her chunk ayrı çağrı

    with pytest.raises(RuntimeError):
        indexing.index_document(make_document(TURKISH_PAGES, document_id="doc-tr"))

    # İlk chunk yazılmıştı; geri alındı ki belge "indeksli" görünüp sonraki denemede atlanmasın.
    assert store.count_document_chunks("doc-tr") == 0


def test_same_content_uploaded_with_new_name_reports_original_name(store, embedder):
    indexing, _ = _services(store, embedder)
    indexing.index_document(make_document(TURKISH_PAGES, document_id="doc-tr", file_name="ilk.pdf"))

    result = indexing.index_document(make_document(TURKISH_PAGES, document_id="doc-tr", file_name="kopya.pdf"))

    # Aynı içerik (aynı document_id): yeniden indekslenmez ve kaynaklarda görünecek
    # ad (ilk.pdf) ile arayüzde gösterilecek ad aynı olur.
    assert result.status is IndexingStatus.SKIPPED
    assert result.file_name == "ilk.pdf"
    assert store.document_file_name("doc-tr") == "ilk.pdf"
    assert store.document_file_name("doc-yok") is None
