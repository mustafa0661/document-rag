"""Chunker sözleşmesi: işlenmiş belgeyi embedding'e uygun parçalara böler."""

from abc import ABC, abstractmethod

from app.core.models import Chunk, IngestedDocument


class TextChunker(ABC):
    @property
    @abstractmethod
    def version(self) -> str:
        """Chunk üretme mantığının sürümü. Mantık değişirse artırılır;
        böylece eski mantıkla oluşturulmuş indeks yeniden kullanılmaz."""

    @abstractmethod
    def chunk(self, document: IngestedDocument) -> list[Chunk]:
        """Belgeyi chunk'lara böler.

        Chunk'lar sayfa sınırını aşmaz, boş sayfalar için chunk üretilmez ve
        aynı girdi + aynı ayarlar her zaman aynı chunk'ları üretir.
        """
