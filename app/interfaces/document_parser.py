"""Belge parser sözleşmesi.

Parser'ın tek sorumluluğu bir dosyadan sayfa bazında metin çıkarmaktır.
Doğrulama (uzantı, boş dosya) ve metadata üretimi (document_id, dosya adı)
`IngestionService`in işidir; yeni bir parser yazan kişi bunlarla uğraşmaz.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class DocumentParser(ABC):
    @property
    @abstractmethod
    def supported_extensions(self) -> frozenset[str]:
        """Desteklenen uzantılar; küçük harf ve noktalı (ör. ``".pdf"``)."""

    @abstractmethod
    def parse(self, file_path: Path) -> list[tuple[int, str]]:
        """Dosyayı sayfa bazında metne dönüştürür.

        Returns:
            ``(sayfa_numarası, metin)`` çiftleri, sayfa sırasına göre.
            Sayfa numaraları 1'den başlar ve kaynak belgedekiyle aynıdır.
            Metin içermeyen sayfalar boş metinle listede yer alır.

        Raises:
            DocumentParseError: Dosya okunamaz veya dönüştürülemezse.
        """
