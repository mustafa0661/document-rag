"""Test dosyaları depoya eklenmez, her test oturumunda üretilir.

Böylece testin neyi doğruladığı (hangi metin, hangi sayfada) kodda görünür.
"""

from pathlib import Path

import pytest

# Türkçe karakterleri (ç ğ ı ö ş ü) içeren yaygın fontlar; işletim sistemine göre ilk bulunan kullanılır.
_FONT_CANDIDATES = (
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

TURKISH_LINES = ("Hastanın şikayeti göğüs ağrısıdır.", "Muayene sonucu üç gün içinde açıklanacak.")
ENGLISH_LINES = ("Invoice total amount is 450 dollars.", "Payment due date is next Friday.")


@pytest.fixture(scope="session")
def font_path() -> str:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    pytest.skip("Türkçe karakter destekli bir TTF font bulunamadı.")


def _render_text_image(lines, font_path: str):
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(font_path, 48)
    image = Image.new("RGB", (1700, 140 + 90 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((80, 70 + index * 90), line, fill="black", font=font)
    return image


@pytest.fixture(scope="session")
def files_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("ingestion_files")


@pytest.fixture(scope="session")
def turkish_png(files_dir, font_path) -> Path:
    path = files_dir / "turkce.png"
    _render_text_image(TURKISH_LINES, font_path).save(path)
    return path


@pytest.fixture(scope="session")
def english_jpg(files_dir, font_path) -> Path:
    path = files_dir / "english.jpg"
    _render_text_image(ENGLISH_LINES, font_path).save(path, quality=95)
    return path


@pytest.fixture(scope="session")
def scanned_pdf(files_dir, font_path) -> Path:
    """Metin katmanı olmayan, yalnızca görüntüden oluşan 2 sayfalık PDF."""
    path = files_dir / "taranmis.pdf"
    page1 = _render_text_image(TURKISH_LINES, font_path)
    page2 = _render_text_image(ENGLISH_LINES, font_path)
    page1.save(path, "PDF", resolution=150, save_all=True, append_images=[page2])
    return path


@pytest.fixture(scope="session")
def text_pdf(files_dir, font_path) -> Path:
    """Metin katmanı olan 2 sayfalık PDF; her sayfada farklı metin."""
    from fpdf import FPDF

    path = files_dir / "metinli.pdf"
    pdf = FPDF()
    pdf.add_font("TestFont", fname=font_path)
    pdf.set_font("TestFont", size=14)
    pdf.add_page()
    pdf.multi_cell(0, 10, "Birinci sayfa: laboratuvar sonuçları normal sınırlarda.")
    pdf.add_page()
    pdf.multi_cell(0, 10, "Second page: discharge summary for the patient.")
    pdf.output(str(path))
    return path


LAB_TABLE = (
    ("Tetkik", "Sonuç", "Birim", "Referans Aralığı"),
    ("Hemoglobin", "13.5", "g/dL", "12.0 - 16.0"),
    ("Glukoz", "98", "mg/dL", "70 - 100"),
    ("Kreatinin", "0.9", "mg/dL", "0.6 - 1.2"),
)


@pytest.fixture(scope="session")
def table_pdf(files_dir, font_path) -> Path:
    """Başlık, açıklama paragrafı ve kenarlıklı bir tablo içeren tek sayfalık PDF."""
    from fpdf import FPDF, FontFace

    path = files_dir / "tablolu.pdf"
    pdf = FPDF()
    pdf.add_font("TestFont", fname=font_path)
    pdf.set_font("TestFont", size=12)
    pdf.add_page()
    pdf.multi_cell(0, 10, "Laboratuvar Sonuç Raporu", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(
        0, 8, "Aşağıdaki tabloda hastanın kan tahlili sonuçları yer almaktadır.",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(4)
    # Başlık satırı kalın yazılmaz: kalın font dosyasının adı işletim sistemine göre değişir.
    with pdf.table(headings_style=FontFace(emphasis="")) as table:
        for row_values in LAB_TABLE:
            row = table.row()
            for value in row_values:
                row.cell(value)
    pdf.output(str(path))
    return path


@pytest.fixture(scope="session")
def scanned_table_png(files_dir, table_pdf) -> Path:
    """Tablolu PDF'in görüntüye çevrilmiş hâli: metin katmanı yok, tablo OCR ile okunmalı."""
    import pypdfium2 as pdfium  # Docling'in bağımlılığı olarak kurulu gelir

    path = files_dir / "taranmis_tablo.png"
    pdf = pdfium.PdfDocument(table_pdf)
    try:
        pdf[0].render(scale=2).to_pil().save(path)
    finally:
        pdf.close()  # Windows'ta dosya kilidi kalmasın
    return path


@pytest.fixture(scope="session")
def corrupted_pdf(files_dir) -> Path:
    path = files_dir / "bozuk.pdf"
    path.write_bytes(b"%PDF-1.7\n" + bytes(range(256)) * 20)
    return path
