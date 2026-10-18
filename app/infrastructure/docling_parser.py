"""Docling tabanlı `DocumentParser` implementasyonu.

OCR notları:
- OCR motoru bilinçli olarak EasyOCR seçildi. Docling'in varsayılanı olan
  `OcrAutoOptions` motoru ortama göre seçer; seçilebilecek motorlardan
  RapidOCR çalıştırma başına yalnızca tek dil kullanır. Türkçe + İngilizce
  gereksinimini garanti etmek için motor ve diller açıkça veriliyor.
- `OcrMode.DEFAULT`, PDF'in metin katmanı olan bölgelerini OCR'a göndermez;
  metin katmanı olmayan (taranmış) bölgeleri OCR'lar. Böylece metinli,
  taranmış ve karma PDF'ler aynı ayarla işlenir. Görsellerde metin katmanı
  olmadığından tamamı OCR'dan geçer.
"""

import logging
from collections.abc import Sequence
from pathlib import Path

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    OcrMode,
    PdfPipelineOptions,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)

from app.core.exceptions import DocumentParseError
from app.interfaces.document_parser import DocumentParser

logger = logging.getLogger(__name__)

# EasyOCR dil kodları. İkisi de Latin alfabesi kullandığı için EasyOCR
# bunları aynı tanıma modelinde birlikte çalıştırabilir.
DEFAULT_OCR_LANGUAGES: tuple[str, ...] = ("tr", "en")


class DoclingParser(DocumentParser):
    _SUPPORTED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})

    def __init__(
        self,
        ocr_languages: Sequence[str] = DEFAULT_OCR_LANGUAGES,
        force_full_page_ocr: bool = False,
    ) -> None:
        """
        Args:
            ocr_languages: EasyOCR dil kodları. Desteklenmeyen bir dil
                Docling tarafından hata olarak bildirilir.
            force_full_page_ocr: True ise PDF'in metin katmanı yok sayılır ve
                her sayfa baştan sona OCR'lanır. Metin katmanı bozuk/yanlış
                kodlanmış PDF'ler için kullanılır; daha yavaştır.
        """
        ocr_options = EasyOcrOptions(
            lang=list(ocr_languages),
            mode=OcrMode.FULL_PAGE if force_full_page_ocr else OcrMode.DEFAULT,
        )
        pipeline_options = PdfPipelineOptions(
            do_ocr=True,
            ocr_options=ocr_options,
            # Varsayılanı zaten True; tablolar RAG için önemli olduğundan açıkça yazıldı.
            # Tablolar Markdown tablosu olarak dışa aktarılır, satır/sütun yapısı korunur.
            do_table_structure=True,
        )

        # Converter bir kez kurulur; modeller ilk dönüşümde yüklenir ve
        # sonraki belgelerde yeniden kullanılır.
        self._converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
            },
        )

    @property
    def supported_extensions(self) -> frozenset[str]:
        return self._SUPPORTED_EXTENSIONS

    def warm_up(self) -> None:
        """Modelleri önceden yükler; ilk çalıştırmada indirir.

        Normalde modeller ilk belgede yüklenir. Bu metot aynı işi önceden yapar:
        layout ve tablo modelleri Hugging Face önbelleğine, EasyOCR'ın tr/en
        modelleri EasyOCR'ın model klasörüne iner. Çalışma anında da aynı
        önbellekler kullanılır, ek yapılandırma gerekmez.

        Kurulum adımında (`python -m app.scripts.download_models`) ve ileride
        uygulama açılışında çağrılır; böylece ağ sorunları ilk belgede değil
        burada, anlaşılır biçimde ortaya çıkar.
        """
        for input_format in (InputFormat.PDF, InputFormat.IMAGE):
            self._converter.initialize_pipeline(input_format)

    def parse(self, file_path: Path) -> list[tuple[int, str]]:
        try:
            result = self._converter.convert(file_path, raises_on_error=False)
        except Exception as exc:
            # Üçüncü parti kütüphane sınırı: Docling'e özgü hatalar servis
            # katmanına sızmasın diye tek tip hataya çevriliyor. Asıl hata
            # `__cause__` olarak korunur.
            raise DocumentParseError(
                f"'{file_path.name}' işlenemedi: {exc}"
            ) from exc

        if result.status in (ConversionStatus.FAILURE, ConversionStatus.SKIPPED):
            details = "; ".join(err.error_message for err in result.errors)
            raise DocumentParseError(
                f"'{file_path.name}' işlenemedi; dosya bozuk veya içeriği "
                f"uzantısıyla uyumsuz olabilir. Ayrıntı: {details or result.status.value}"
            )
        if result.status == ConversionStatus.PARTIAL_SUCCESS:
            logger.warning(
                "'%s' kısmen işlendi; bazı sayfalar eksik olabilir: %s",
                file_path.name,
                [err.error_message for err in result.errors],
            )

        document = result.document
        if not document.pages:
            raise DocumentParseError(f"'{file_path.name}' içinde sayfa bulunamadı.")

        # Sayfa numaraları Docling'in `pages` sözlüğünün anahtarlarından
        # (1'den başlayan gerçek sayfa numaraları) alınır, sayaçla üretilmez.
        # `export_to_markdown(page_no=...)` yalnızca o sayfaya ait öğeleri
        # (provenance kaydındaki page_no'ya göre) dışa aktarır.
        # Bilinen sınırlama: Docling sayfa sınırını aşan bir paragrafı tek öğede
        # birleştirir ve serializer öğeyi ilk sayfasına (`prov[0]`) yazar. Metin
        # kaybolmaz, ancak devam eden kısım bir önceki sayfaya atanmış olur.
        return [
            (
                page_no,
                document.export_to_markdown(
                    page_no=page_no, image_placeholder=""
                ).strip(),
            )
            for page_no in sorted(document.pages)
        ]
