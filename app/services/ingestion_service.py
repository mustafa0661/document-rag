"""Belge işleme akışı: doğrulama -> kimlik üretimi -> parse -> metadata."""

import hashlib
import logging
from pathlib import Path

from app.core.exceptions import EmptyFileError, UnsupportedFileTypeError
from app.core.models import IngestedDocument, PageContent
from app.interfaces.document_parser import DocumentParser

logger = logging.getLogger(__name__)

_HASH_CHUNK_SIZE = 1024 * 1024


class IngestionService:
    def __init__(self, parser: DocumentParser) -> None:
        self._parser = parser

    def ingest(self, file_path: str | Path) -> IngestedDocument:
        """Bir dosyayı doğrular, parse eder ve sayfa bazlı belge döndürür.

        Raises:
            FileNotFoundError: Dosya yoksa.
            UnsupportedFileTypeError: Uzantı parser tarafından desteklenmiyorsa.
            EmptyFileError: Dosya 0 bayt ise.
            DocumentParseError: Dosya okunamaz veya dönüştürülemezse.
        """
        path = Path(file_path)
        self._validate(path)

        document_id = self.compute_document_id(path)
        parsed_pages = self._parser.parse(path)

        pages = tuple(
            PageContent(
                document_id=document_id,
                file_name=path.name,
                page_number=page_number,
                text=text,
            )
            for page_number, text in parsed_pages
        )
        document = IngestedDocument(
            document_id=document_id,
            file_name=path.name,
            source_path=path,
            pages=pages,
        )

        if not document.has_text:
            # Hata değil: belge geçerli ama metin çıkmadı (ör. boş sayfa,
            # yalnızca görsel). Karar üst katmana bırakılıyor.
            logger.warning("'%s' içinden metin çıkarılamadı.", path.name)
        return document

    def _validate(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"Dosya bulunamadı: {path}")

        supported = self._parser.supported_extensions
        if path.suffix.lower() not in supported:
            raise UnsupportedFileTypeError(
                f"'{path.name}' desteklenmiyor. "
                f"Desteklenen uzantılar: {', '.join(sorted(supported))}"
            )

        if path.stat().st_size == 0:
            raise EmptyFileError(f"'{path.name}' boş (0 bayt).")

    @staticmethod
    def compute_document_id(path: str | Path) -> str:
        """İçeriğin SHA-256 özeti: aynı dosya her zaman aynı kimliği alır.

        Belgeyi okumadan (parse etmeden) kimliğini bilmek için de kullanılır;
        örneğin zaten indeksli bir belgenin pahalı OCR adımını atlamak için.
        """
        path = Path(path)
        digest = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(_HASH_CHUNK_SIZE):
                digest.update(chunk)
        return digest.hexdigest()
