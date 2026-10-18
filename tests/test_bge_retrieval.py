"""Gerçek BAAI/bge-m3 ile embedding ve retrieval entegrasyon testleri.

İlk çalıştırmada model (~2.3 GB) indirilir. Ölçümleri görmek için:
    pytest tests/test_bge_retrieval.py -m integration -v -s

Sorgular chunk'lardaki kelimeleri bilinçli olarak tekrar etmez ("şeker" ↔
"glukoz"): kelime eşleşmesi değil, anlamsal arama ölçülür.
`[ölçüm]` ve `[mesafe]` satırları TESTING.md'ye aktarılmak içindir.
"""

import math
import statistics
import time

import pytest

pytest.importorskip("sentence_transformers")

from chromadb.api.client import SharedSystemClient  # noqa: E402

from app.core.models import IndexConfig  # noqa: E402
from app.infrastructure.bge_embedding import BgeM3EmbeddingProvider  # noqa: E402
from app.infrastructure.chroma_store import ChromaVectorStore  # noqa: E402
from app.infrastructure.markdown_chunker import MarkdownChunker  # noqa: E402
from app.services.indexing_service import IndexingService  # noqa: E402
from app.services.retrieval_service import RetrievalService  # noqa: E402
from tests.fakes import make_document  # noqa: E402

pytestmark = pytest.mark.integration

TURKISH_PAGES = [
    "Hastanın açlık kan glukozu 98 mg/dL olarak ölçülmüştür ve normal sınırlar içindedir.",
    "Kardiyoloji kontrol muayenesi için hastaya bir ay sonrasına randevu verilmiştir.",
    "Hastanın kullandığı tansiyon ilacı günde bir kez sabah aç karnına alınmalıdır.",
    "Ameliyat sonrası yara bakımı için pansuman iki günde bir yapılmalıdır.",
]
ENGLISH_PAGES = [
    "The total amount of the invoice is 450 US dollars, including value added tax.",
    "Payment must be completed by bank transfer no later than next Friday.",
    "Delivery to the Ankara warehouse takes approximately five business days.",
    "The product comes with a two-year manufacturer warranty against defects.",
]

# (soru, aranacak belge, beklenen sayfa)
RELEVANT_QUERIES = [
    ("Şeker değeri kaç çıktı?", "doc-tr", 1),
    ("Doktora tekrar ne zaman gideceğim?", "doc-tr", 2),
    ("İlacı nasıl kullanmalıyım?", "doc-tr", 3),
    ("How much do I have to pay in total?", "doc-en", 1),
    ("How long does shipping take?", "doc-en", 3),
]
CROSS_LINGUAL_QUERIES = [  # Türkçe soru → İngilizce belge
    ("Ödemenin son günü ne zaman?", "doc-en", 2),
    ("Ürünün garanti süresi ne kadar?", "doc-en", 4),
]
IRRELEVANT_QUERIES = [
    ("Dünya Kupası finalini hangi takım kazandı?", "doc-tr"),
    ("What is the capital of Australia?", "doc-en"),
]


@pytest.fixture(scope="module")
def embedder():
    started = time.perf_counter()
    provider = BgeM3EmbeddingProvider()
    print(f"\n[ölçüm] BGE-M3 yükleme süresi: {time.perf_counter() - started:.1f} sn")
    return provider


@pytest.fixture(scope="module")
def services(embedder, tmp_path_factory):
    chunker = MarkdownChunker(embedder.count_tokens, chunk_size=500, chunk_overlap=75)
    config = IndexConfig(embedder.model_name, embedder.dimension, 500, 75, chunker.version)
    store = ChromaVectorStore(tmp_path_factory.mktemp("chroma"), "bge_test", config)
    indexing = IndexingService(chunker, embedder, store)
    indexing.index_document(make_document(TURKISH_PAGES, "doc-tr", "rapor.pdf"))
    indexing.index_document(make_document(ENGLISH_PAGES, "doc-en", "invoice.pdf"))
    yield RetrievalService(embedder, store)
    SharedSystemClient.clear_system_cache()


def _top(services, query, document_id):
    return services.search(query, [document_id])[0]


def test_embedding_dimension_and_normalization(embedder):
    vectors = embedder.embed_documents(["Merhaba dünya.", "Hello world."])
    query = embedder.embed_query("Selam")

    assert embedder.dimension == 1024
    for vector in vectors + [query]:
        assert len(vector) == 1024
        assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-3)
    assert embedder.embed_documents([]) == []


def test_real_tokenizer_keeps_chunks_within_limit(embedder):
    paragraph = (
        "Hastanın şikâyetlerinin değerlendirilmesi sonucunda kardiyolojik incelemelerin "
        "tamamlanmasına ve tedavinin düzenlenmesine karar verilmiştir. "
    )
    document = make_document([paragraph * 60])
    chunker = MarkdownChunker(embedder.count_tokens, chunk_size=500, chunk_overlap=75)

    chunks = chunker.chunk(document)

    words, tokens = len(paragraph.split()), embedder.count_tokens(paragraph)
    print(f"\n[ölçüm] Türkçe örnek: {words} kelime = {tokens} token ({tokens / words:.2f} token/kelime)")
    assert len(chunks) > 1
    assert all(chunk.token_count <= 500 for chunk in chunks)


@pytest.mark.parametrize("query, document_id, expected_page", RELEVANT_QUERIES)
def test_semantic_query_finds_correct_page(services, query, document_id, expected_page):
    top = _top(services, query, document_id)
    print(f"\n[mesafe] alakalı     | {query!r:45} → s.{top.chunk.page_number} d={top.distance:.4f}")
    assert top.chunk.page_number == expected_page, top.chunk.text


@pytest.mark.parametrize("query, document_id, expected_page", CROSS_LINGUAL_QUERIES)
def test_turkish_query_finds_english_content(services, query, document_id, expected_page):
    top = _top(services, query, document_id)
    print(f"\n[mesafe] diller arası | {query!r:45} → s.{top.chunk.page_number} d={top.distance:.4f}")
    assert top.chunk.page_number == expected_page, top.chunk.text


def test_irrelevant_queries_are_farther_than_relevant_ones(services):
    relevant = [_top(services, q, d).distance for q, d, _ in RELEVANT_QUERIES + CROSS_LINGUAL_QUERIES]
    irrelevant = [_top(services, q, d).distance for q, d in IRRELEVANT_QUERIES]
    for (query, _), distance in zip(IRRELEVANT_QUERIES, irrelevant):
        print(f"\n[mesafe] alakasız    | {query!r:45} → en yakın d={distance:.4f}")
    print(
        f"\n[mesafe] özet: alakalı en iyi sonuç d ∈ [{min(relevant):.4f}, {max(relevant):.4f}], "
        f"ort. {statistics.mean(relevant):.4f}; alakasız en iyi sonuç d ∈ "
        f"[{min(irrelevant):.4f}, {max(irrelevant):.4f}]"
    )
    # Mutlak eşik yok; yalnızca alakasız soruların ortalamada daha uzak olduğu kontrol edilir.
    # Ayrışmanın ne kadar net olduğu (aralıkların çakışıp çakışmadığı) TESTING.md'de raporlanır.
    assert statistics.mean(irrelevant) > statistics.mean(relevant)


def test_embedding_throughput_on_cpu(embedder):
    texts = ["Hastanın kan tahlili sonuçları değerlendirilmiştir. " * 40] * 16  # ~16 chunk, ~400 token
    started = time.perf_counter()
    embedder.embed_documents(texts)
    elapsed = time.perf_counter() - started
    print(f"\n[ölçüm] 16 chunk (~{embedder.count_tokens(texts[0])} token) embedding: "
          f"{elapsed:.1f} sn → {16 / elapsed:.2f} chunk/sn")
