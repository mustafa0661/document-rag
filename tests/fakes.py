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
