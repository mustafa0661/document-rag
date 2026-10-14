"""Ingestion katmanının ürettiği veri modelleri.

Modeller bilinçli olarak sade ve değiştirilemez (frozen) tutuldu: ingestion
çıktısı sonraki aşamalara (chunking, embedding) yalnızca okunmak üzere aktarılır.
"""

from dataclasses import dataclass
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
