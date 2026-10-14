"""IngestionService birim testleri. Docling yüklenmez; saniyeler içinde çalışır."""

from pathlib import Path

import pytest

from app.core.exceptions import (
    DocumentParseError,
    EmptyFileError,
    UnsupportedFileTypeError,
)
from app.interfaces.document_parser import DocumentParser
from app.services.ingestion_service import IngestionService


class FakeParser(DocumentParser):
    def __init__(self, pages=None, error: Exception | None = None):
        self._pages = pages if pages is not None else [(1, "sayfa bir"), (2, "sayfa iki")]
        self._error = error
        self.calls: list[Path] = []

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".pdf", ".png"})

    def parse(self, file_path: Path) -> list[tuple[int, str]]:
        self.calls.append(file_path)
        if self._error:
            raise self._error
        return self._pages


def _write(path: Path, content: bytes = b"icerik") -> Path:
    path.write_bytes(content)
    return path


def test_metadata_is_attached_to_every_page(tmp_path):
    file = _write(tmp_path / "rapor.pdf")

    doc = IngestionService(FakeParser()).ingest(file)

    assert doc.file_name == "rapor.pdf"
    assert doc.page_count == 2
    assert [p.page_number for p in doc.pages] == [1, 2]
    assert [p.text for p in doc.pages] == ["sayfa bir", "sayfa iki"]
    assert all(p.document_id == doc.document_id for p in doc.pages)
    assert all(p.file_name == "rapor.pdf" for p in doc.pages)


def test_page_numbers_come_from_parser_not_renumbered(tmp_path):
    file = _write(tmp_path / "a.pdf")
    parser = FakeParser(pages=[(1, "a"), (3, "c")])

    doc = IngestionService(parser).ingest(file)

    assert [p.page_number for p in doc.pages] == [1, 3]


def test_document_id_depends_on_content_not_name(tmp_path):
    service = IngestionService(FakeParser())
    a = service.ingest(_write(tmp_path / "a.pdf", b"ayni"))
    b = service.ingest(_write(tmp_path / "b.pdf", b"ayni"))
    c = service.ingest(_write(tmp_path / "c.pdf", b"farkli"))

    assert a.document_id == b.document_id
    assert a.document_id != c.document_id
    assert len(a.document_id) == 64  # SHA-256 hex


def test_extension_check_is_case_insensitive(tmp_path):
    doc = IngestionService(FakeParser()).ingest(_write(tmp_path / "TARAMA.PNG"))
    assert doc.file_name == "TARAMA.PNG"


def test_unsupported_extension_is_rejected_before_parsing(tmp_path):
    parser = FakeParser()
    file = _write(tmp_path / "notlar.docx")

    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        IngestionService(parser).ingest(file)

    message = str(exc_info.value)
    assert "notlar.docx" in message
    assert ".pdf" in message and ".png" in message
    assert parser.calls == []


def test_file_without_extension_is_rejected(tmp_path):
    with pytest.raises(UnsupportedFileTypeError):
        IngestionService(FakeParser()).ingest(_write(tmp_path / "dosya"))


def test_empty_file_is_rejected_before_parsing(tmp_path):
    parser = FakeParser()
    file = _write(tmp_path / "bos.pdf", b"")

    with pytest.raises(EmptyFileError, match="bos.pdf"):
        IngestionService(parser).ingest(file)
    assert parser.calls == []


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        IngestionService(FakeParser()).ingest(tmp_path / "yok.pdf")


def test_directory_path_raises_file_not_found(tmp_path):
    folder = tmp_path / "klasor.pdf"
    folder.mkdir()
    with pytest.raises(FileNotFoundError):
        IngestionService(FakeParser()).ingest(folder)


def test_parse_error_propagates(tmp_path):
    parser = FakeParser(error=DocumentParseError("bozuk"))
    with pytest.raises(DocumentParseError, match="bozuk"):
        IngestionService(parser).ingest(_write(tmp_path / "bozuk.pdf"))


def test_document_without_text_is_returned_with_warning(tmp_path, caplog):
    parser = FakeParser(pages=[(1, ""), (2, "   ")])

    doc = IngestionService(parser).ingest(_write(tmp_path / "bos_sayfalar.pdf"))

    assert doc.page_count == 2  # boş sayfalar korunur, numaralar kaymaz
    assert not doc.has_text
    assert all(p.is_empty for p in doc.pages)
    assert "metin çıkarılamadı" in caplog.text


def test_accepts_str_path(tmp_path):
    file = _write(tmp_path / "rapor.pdf")
    doc = IngestionService(FakeParser()).ingest(str(file))
    assert doc.source_path == file
