"""DoclingParser entegrasyon testleri: gerçek Docling ve EasyOCR modelleriyle çalışır.

İlk çalıştırmada modeller indirilir (internet gerekir). Hızlı geri bildirim için:
    pytest -m "not integration"

OCR çıktısı birebir sabit olmadığından testler tam eşleşme yerine anahtar
kelimelerin varlığını kontrol eder. Türkçe karakterlerin (ğ, ş, ı, ü, ç)
korunması ise ayrıca doğrulanır: dil yapılandırmasının işe yaradığının kanıtı budur.
"""

import pytest

# Docling kurulu değilse bu modül atlanır; birim testleri yine çalışır.
pytest.importorskip("docling")

from app.core.exceptions import DocumentParseError  # noqa: E402
from app.infrastructure.docling_parser import DoclingParser  # noqa: E402
from app.services.ingestion_service import IngestionService  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def parser() -> DoclingParser:
    # Modül başına bir kez: model yükleme pahalı.
    return DoclingParser()


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def test_text_pdf_keeps_page_boundaries(parser, text_pdf):
    pages = parser.parse(text_pdf)

    assert [number for number, _ in pages] == [1, 2]
    first, second = _normalize(pages[0][1]), _normalize(pages[1][1])
    assert "laboratuvar sonuçları" in first
    assert "discharge" not in first
    assert "discharge summary" in second
    assert "laboratuvar" not in second


def test_turkish_png_is_read_with_turkish_characters(parser, turkish_png):
    pages = parser.parse(turkish_png)

    assert [number for number, _ in pages] == [1]
    text = _normalize(pages[0][1])
    for word in ("şikayeti", "göğüs", "ağrısı", "muayene", "üç", "açıklanacak"):
        assert word in text, f"'{word}' bulunamadı. OCR çıktısı: {text!r}"


def test_english_jpg_is_read(parser, english_jpg):
    pages = parser.parse(english_jpg)

    assert [number for number, _ in pages] == [1]
    text = _normalize(pages[0][1])
    for word in ("invoice", "total", "amount", "payment"):
        assert word in text, f"'{word}' bulunamadı. OCR çıktısı: {text!r}"


def test_scanned_pdf_is_ocred_page_by_page(parser, scanned_pdf):
    pages = parser.parse(scanned_pdf)

    assert [number for number, _ in pages] == [1, 2]
    first, second = _normalize(pages[0][1]), _normalize(pages[1][1])
    assert "göğüs" in first, first
    assert "invoice" in second, second
    assert "invoice" not in first


def _markdown_table_rows(markdown: str) -> list[list[str]]:
    """Markdown tablo satırlarını hücre listelerine çevirir; ayraç satırını (|---|) atlar."""
    rows = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def test_pdf_table_is_exported_with_rows_and_columns(parser, table_pdf):
    pages = parser.parse(table_pdf)

    assert [number for number, _ in pages] == [1]
    markdown = pages[0][1]
    rows = _markdown_table_rows(markdown)

    assert rows[0] == ["Tetkik", "Sonuç", "Birim", "Referans Aralığı"], markdown
    # Hücre değerlerinin doğru satır ve sütunda kalması: RAG'de "Glukoz kaç?"
    # sorusunun cevabı ancak böyle doğru eşleşir.
    assert ["Glukoz", "98", "mg/dL", "70 - 100"] in rows, markdown
    assert len(rows) == 4, markdown
    # Tablo dışındaki metin kaybolmamalı.
    assert "kan tahlili" in markdown


def test_scanned_table_is_ocred_into_table_structure(parser, scanned_table_png):
    pages = parser.parse(scanned_table_png)

    markdown = pages[0][1]
    rows = _markdown_table_rows(markdown)

    assert len(rows) == 4, f"Tablo yapısı bulunamadı. Çıktı:\n{markdown}"
    glukoz_rows = [row for row in rows if row and row[0].lower() == "glukoz"]
    assert glukoz_rows, f"'Glukoz' satırı bulunamadı. Çıktı:\n{markdown}"
    assert glukoz_rows[0][1] == "98", f"Değer yanlış sütunda. Çıktı:\n{markdown}"


def test_warm_up_initializes_pipelines(parser):
    # Kurulum betiğinin (scripts/download_models.py) kullandığı yol.
    parser.warm_up()


def test_corrupted_pdf_raises_parse_error(parser, corrupted_pdf):
    with pytest.raises(DocumentParseError, match="bozuk.pdf"):
        parser.parse(corrupted_pdf)


def test_service_end_to_end_with_docling(parser, text_pdf):
    doc = IngestionService(parser).ingest(text_pdf)

    assert doc.file_name == "metinli.pdf"
    assert doc.page_count == 2
    assert doc.has_text
    assert [p.page_number for p in doc.pages] == [1, 2]
    assert {p.document_id for p in doc.pages} == {doc.document_id}
