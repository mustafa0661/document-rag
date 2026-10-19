"""Birim testlerinde gerçek model yerine kullanılan sahte bileşenler."""

import hashlib
import math
import re
from pathlib import Path

from app.core.models import IngestedDocument, PageContent
from app.interfaces.embedding_provider import EmbeddingProvider


class HashingEmbeddingProvider(EmbeddingProvider):
    """Kelimeleri sabit bir hash ile boyutlara dağıtan, normalize vektör üreten provider.

    Deterministiktir ve kelime örtüşmesine duyarlıdır: ortak kelimesi çok olan
    metinler birbirine yakın düşer. Anlamsal veya diller arası benzerlik
    YOKTUR; onlar gerçek modelle entegrasyon testlerinde sınanır.
    Token sayımı kelime sayısıdır.
    """

    def __init__(self, dimension: int = 256, model_name: str = "fake-hashing") -> None:
        self._dimension = dimension
        self._model_name = model_name
        self.embedded_batches: list[list[str]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embedded_batches.append(list(texts))
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in re.findall(r"\w+", text.casefold()):
            bucket = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self._dimension
            vector[bucket] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return [1.0 / math.sqrt(self._dimension)] * self._dimension
        return [value / norm for value in vector]


class WrongDimensionProvider(HashingEmbeddingProvider):
    """Bildirdiğinden farklı boyutta vektör üreten hatalı provider."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector + [0.0] for vector in super().embed_documents(texts)]

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(text) + [0.0]


class FailingProvider(HashingEmbeddingProvider):
    """Belirli sayıda başarılı çağrıdan sonra hata veren provider (yarım indeksleme testi)."""

    def __init__(self, fail_on_call: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._fail_on_call = fail_on_call
        self._calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._calls += 1
        if self._calls >= self._fail_on_call:
            raise RuntimeError("embedding servisi yanıt vermedi")
        return super().embed_documents(texts)


def word_count(text: str) -> int:
    return len(text.split())


def make_document(pages: list[str], document_id: str = "doc-a", file_name: str = "a.pdf") -> IngestedDocument:
    return IngestedDocument(
        document_id=document_id,
        file_name=file_name,
        source_path=Path(file_name),
        pages=tuple(
            PageContent(document_id, file_name, number, text)
            for number, text in enumerate(pages, start=1)
        ),
    )


# --- Arayüz testleri için sahte pipeline bileşenleri ---------------------------


class FakeIngestion:
    """Dosyayı okumadan, içerik özetiyle kimliklendirilmiş sahte bir belge döndürür."""

    def __init__(self, pages=("Glukoz 98 mg/dL.",), error: Exception | None = None) -> None:
        self.pages, self.error, self.calls = list(pages), error, []

    def ingest(self, path):
        from app.services.ingestion_service import IngestionService

        self.calls.append(path)
        if self.error:
            raise self.error
        return make_document(self.pages, IngestionService.compute_document_id(path), path.name)


class FakeIndexing:
    def __init__(self, error: Exception | None = None) -> None:
        self.documents: dict[str, tuple[str, int]] = {}
        self.error = error

    def indexed_chunk_count(self, document_id):
        return self.documents.get(document_id, ("", 0))[1]

    def indexed_file_name(self, document_id):
        return self.documents.get(document_id, (None, 0))[0]

    def index_document(self, document, reindex=False):
        from app.core.models import IndexingResult, IndexingStatus

        if self.error:
            raise self.error
        count = sum(not page.is_empty for page in document.pages)
        if not count:
            return IndexingResult(document.document_id, document.file_name, IndexingStatus.EMPTY, 0)
        self.documents[document.document_id] = (document.file_name, count)
        return IndexingResult(document.document_id, document.file_name, IndexingStatus.INDEXED, count)


class FakeQuestionAnswering:
    def __init__(self, error: Exception | None = None) -> None:
        self.error, self.calls = error, []

    def answer(self, question, document_ids):
        from app.core.models import AnswerStatus, QuestionAnswer, SourceReference

        self.calls.append((question, list(document_ids)))
        if self.error:
            raise self.error
        source = SourceReference("S1", document_ids[0], "rapor.pdf", 2, "c", "Glukoz 98 mg/dL.", 0.3)
        return QuestionAnswer(question, AnswerStatus.ANSWERED, "Açlık glukozu 98 mg/dL.", (source,))


def fake_pipeline(**overrides):
    from types import SimpleNamespace

    parts = {
        "ingestion": FakeIngestion(),
        "indexing": FakeIndexing(),
        "question_answering": FakeQuestionAnswering(),
    }
    parts.update(overrides)
    return SimpleNamespace(**parts)
