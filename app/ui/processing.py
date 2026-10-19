"""Tek bir yüklemenin işlenmesi: doğrulama → kayıt → (gerekirse) okuma ve indeksleme.

Streamlit'ten bağımsızdır; arayüz yalnızca sonucu gösterir. Hiçbir hata
dışarı fırlatılmaz: arayüz bir dosyada hata olsa da çalışmaya devam eder.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import RagSettings
from app.core.exceptions import IngestionError
from app.core.models import IndexingStatus
from app.services.ingestion_service import IngestionService
from app.ui.uploads import UploadRejectedError, save_upload, validate_upload

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})


@dataclass(frozen=True)
class DocumentEntry:
    document_id: str
    file_name: str          # indeksteki ad: kaynaklarda görünen adla her zaman aynı
    chunk_count: int
    page_count: int | None = None


@dataclass(frozen=True)
class ProcessOutcome:
    level: str              # "success" | "info" | "warning" | "error"
    message: str
    entry: DocumentEntry | None = None


def process_upload(
    name: str,
    data: bytes,
    pipeline,
    settings: RagSettings,
    lock: threading.Lock,
    progress: Callable[[str], None] = lambda _: None,
) -> ProcessOutcome:
    try:
        validate_upload(name, data, SUPPORTED_EXTENSIONS, settings.max_upload_mb)
        path = save_upload(data, name, settings.upload_dir)
    except UploadRejectedError as exc:
        return ProcessOutcome("error", str(exc))

    try:
        # Docling ve embedding modelleri oturumlar arasında paylaşılıyor: aynı anda tek işlem.
        with lock:
            document_id = IngestionService.compute_document_id(path)
            existing = pipeline.indexing.indexed_chunk_count(document_id)
            if existing:
                stored_name = pipeline.indexing.indexed_file_name(document_id) or path.name
                note = f" ('{stored_name}' adıyla)" if stored_name != path.name else ""
                return ProcessOutcome(
                    "info",
                    f"'{name}' zaten indeksli{note}; yeniden işlenmedi.",
                    DocumentEntry(document_id, stored_name, existing),
                )

            progress("Metin çıkarılıyor (taranmış sayfalarda OCR biraz sürebilir)…")
            document = pipeline.ingestion.ingest(path)
            progress(f"{document.page_count} sayfa okundu; parçalara ayrılıp vektörleştiriliyor…")
            result = pipeline.indexing.index_document(document)
    except IngestionError as exc:
        return ProcessOutcome("error", str(exc))
    except Exception:  # Arayüz çökmemeli; ayrıntı loga yazılır.
        logger.exception("'%s' işlenirken beklenmeyen hata", name)
        return ProcessOutcome("error", f"'{name}' işlenirken beklenmeyen bir hata oluştu. Ayrıntılar logda.")

    if result.status is IndexingStatus.EMPTY:
        return ProcessOutcome("warning", f"'{name}' içinden metin çıkarılamadı; soru sormak için kullanılamaz.")
    entry = DocumentEntry(document_id, result.file_name, result.chunk_count, document.page_count)
    return ProcessOutcome(
        "success", f"'{entry.file_name}' hazır: {document.page_count} sayfa, {result.chunk_count} parça.", entry
    )
