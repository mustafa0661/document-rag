"""Ingestion katmanının ürettiği veri modelleri.

Modeller bilinçli olarak sade ve değiştirilemez (frozen) tutuldu: ingestion
çıktısı sonraki aşamalara (chunking, embedding) yalnızca okunmak üzere aktarılır.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PageContent:
    """Bir belgenin tek bir sayfası ve o sayfaya ait metadata.

    Her sayfa kendi `document_id`, `file_name` ve `page_number` bilgisini
    taşır; böylece sayfa, belgeden ayrılsa bile kaynağı izlenebilir kalır.
    `page_number` 1'den başlar ve kaynak belgedeki sayfa numarasıyla aynıdır.
    """

    document_id: str
    file_name: str
    page_number: int
    text: str

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass(frozen=True, slots=True)
class IngestedDocument:
    """İşlenmiş bir belge: kimlik bilgileri ve sayfa sırasına göre içerik."""

    document_id: str
    file_name: str
    source_path: Path
    pages: tuple[PageContent, ...]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def has_text(self) -> bool:
        return any(not page.is_empty for page in self.pages)


# --- Chunking, indeksleme ve retrieval modelleri ---------------------------


@dataclass(frozen=True, slots=True)
class Chunk:
    """Embedding'e gönderilen ve vektör veritabanında saklanan metin parçası.

    Bir chunk asla sayfa sınırını aşmaz; `page_number` chunk'ın tamamının
    bulunduğu sayfadır. `chunk_index` sayfa içindeki sırasıdır (0'dan başlar).
    """

    chunk_id: str
    document_id: str
    file_name: str
    page_number: int
    chunk_index: int
    text: str
    token_count: int

    @staticmethod
    def make_id(document_id: str, page_number: int, chunk_index: int) -> str:
        """Deterministik ve benzersiz kimlik: aynı içerik + ayar → aynı kimlik."""
        return f"{document_id}:p{page_number:04d}:c{chunk_index:03d}"


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Arama sonucu: chunk ve sorguya kosinüs mesafesi.

    `distance` ChromaDB'nin döndürdüğü kosinüs mesafesidir: 1 - kosinüs benzerliği.
    Aralığı [0, 2]'dir ve KÜÇÜK olan daha alakalıdır. Embedding'ler normalize
    edildiği için `similarity = 1 - distance` birebir kosinüs benzerliğidir.
    """

    chunk: Chunk
    distance: float

    @property
    def similarity(self) -> float:
        return 1.0 - self.distance


@dataclass(frozen=True, slots=True)
class IndexConfig:
    """Bir vektör indeksini oluşturan ayarlar.

    Koleksiyonun metadata'sına yazılır ve her açılışta mevcut ayarlarla
    karşılaştırılır. Farklı bir modelle veya chunk ayarıyla üretilmiş bir
    indeksin yanlışlıkla kullanılması bu sayede engellenir.
    """

    embedding_model: str
    embedding_dimension: int
    chunk_size: int
    chunk_overlap: int
    chunker_version: str

    def to_metadata(self) -> dict[str, str | int]:
        return {
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "chunker_version": self.chunker_version,
        }


class IndexingStatus(str, Enum):
    INDEXED = "indexed"     # chunk'lar üretildi ve kaydedildi
    SKIPPED = "skipped"     # belge zaten indeksli (aynı içerik + aynı ayarlar)
    EMPTY = "empty"         # belgede indekslenecek metin yok


@dataclass(frozen=True, slots=True)
class IndexingResult:
    document_id: str
    file_name: str
    status: IndexingStatus
    chunk_count: int


# --- Soru-cevap modelleri ---------------------------------------------------


class AnswerStatus(str, Enum):
    ANSWERED = "answered"                          # cevap var ve geçerli kaynaklara dayanıyor
    NO_RELEVANT_CONTEXT = "no_relevant_context"    # retrieval boş; LLM çağrılmadı
    INSUFFICIENT_INFORMATION = "insufficient_information"  # LLM: belgelerde cevap yok
    UNVERIFIED = "unverified"                      # LLM cevap verdi ama geçerli kaynak göstermedi; cevap gösterilmez


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Cevabın dayandığı kaynak. Alanların tamamı retrieval sonucundan gelir;
    LLM'in yazdığı dosya/sayfa bilgisi hiçbir zaman kullanılmaz."""

    source_id: str        # LLM'e gösterilen kimlik: S1, S2, ...
    document_id: str
    file_name: str
    page_number: int
    chunk_id: str
    text: str
    distance: float


@dataclass(frozen=True, slots=True)
class QuestionAnswer:
    question: str
    status: AnswerStatus
    answer: str
    sources: tuple[SourceReference, ...] = ()
    rejected_source_ids: tuple[str, ...] = ()   # LLM'in verdiği ama izin verilmeyen kimlikler (tanı için)

    @property
    def is_answered(self) -> bool:
        return self.status is AnswerStatus.ANSWERED
