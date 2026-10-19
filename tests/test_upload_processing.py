"""Yükleme güvenliği ve tek dosya işleme akışı (Streamlit'ten bağımsız)."""

import threading

import pytest

from app.core.config import RagSettings
from app.core.exceptions import DocumentParseError
from app.ui.processing import SUPPORTED_EXTENSIONS, process_upload
from app.ui.uploads import UploadRejectedError, sanitize_filename, save_upload, validate_upload
from tests.fakes import FakeIndexing, FakeIngestion, fake_pipeline

PDF = b"%PDF-1.4 sahte icerik"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("../../etc/rapor.pdf", "rapor.pdf"),
        ("C:\\Users\\ali\\Desktop\\Rapor.PDF", "Rapor.pdf"),
        ("Kan Tahlili Şubat (2).pdf", "Kan Tahlili Şubat (2).pdf"),
        ('a<b>:c?"|*.png', "a_b__c____.png"),
        ("CON.pdf", "_CON.pdf"),
        ("..", "belge"),
        ("", "belge"),
        ("x" * 300 + ".jpg", "x" * 120 + ".jpg"),
    ],
    ids=["yol-gecisi", "windows-yolu", "turkce-karakter", "guvensiz-karakter", "windows-ayrilmis-ad",
         "yalnizca-nokta", "bos-ad", "uzun-ad"],
)
def test_client_file_names_are_sanitized(raw, expected):
    assert sanitize_filename(raw) == expected


# Veri boyutu bayt olarak verilir ve içerik test içinde üretilir; kimlikler açıkça yazılır.
# Not: Büyük bir bytes değerini doğrudan parametre yapmak, pytest'in test kimliğini o değerden
# üretmesine ve Windows'ta PYTEST_CURRENT_TEST ortam değişkeninin 32767 karakter sınırını
# aşmasına yol açıyordu.
@pytest.mark.parametrize(
    "name, size, message",
    [("notlar.txt", 10, "desteklenmiyor"), ("rapor.exe.pdf.sh", 10, "desteklenmiyor"),
     ("bos.pdf", 0, "boş"), ("buyuk.pdf", 1024 * 1024 + 1, "çok büyük")],
    ids=["desteklenmeyen-uzanti", "sahte-cift-uzanti", "bos-dosya", "boyut-siniri"],
)
def test_invalid_uploads_are_rejected(name, size, message):
    with pytest.raises(UploadRejectedError, match=message):
        validate_upload(name, b"x" * size, SUPPORTED_EXTENSIONS, max_mb=1)


def test_uppercase_extension_is_accepted():
    validate_upload("TARAMA.JPG", b"\xff\xd8", SUPPORTED_EXTENSIONS, max_mb=1)


def test_upload_is_saved_under_content_hash_inside_upload_dir(tmp_path):
    first = save_upload(PDF, "../../rapor.pdf", tmp_path)
    second = save_upload(PDF, "../../rapor.pdf", tmp_path)

    assert first == second  # aynı içerik bir kez saklanır
    assert first.read_bytes() == PDF
    assert first.name == "rapor.pdf"
    assert first.parent.parent == tmp_path.resolve()
    assert len(first.parent.name) == 64  # SHA-256 klasörü


# --- process_upload -------------------------------------------------------------


@pytest.fixture
def settings(tmp_path):
    return RagSettings(upload_dir=tmp_path / "uploads", max_upload_mb=1)


def _process(name, data, pipeline, settings):
    return process_upload(name, data, pipeline, settings, threading.Lock())


def test_new_document_is_ingested_and_indexed(settings):
    pipeline = fake_pipeline()
    progress = []

    outcome = process_upload("rapor.pdf", PDF, pipeline, settings, threading.Lock(), progress.append)

    assert outcome.level == "success"
    assert outcome.entry.file_name == "rapor.pdf" and outcome.entry.chunk_count == 1
    assert len(pipeline.ingestion.calls) == 1
    assert progress  # kullanıcıya durum mesajı verildi


def test_same_content_uploaded_again_is_not_reprocessed_and_keeps_original_name(settings):
    pipeline = fake_pipeline()
    first = _process("rapor.pdf", PDF, pipeline, settings)

    again = _process("baska_ad.pdf", PDF, pipeline, settings)

    assert again.level == "info"
    assert again.entry.document_id == first.entry.document_id
    assert again.entry.file_name == "rapor.pdf"  # kaynaklarda görünen adla aynı
    assert "rapor.pdf" in again.message
    assert len(pipeline.ingestion.calls) == 1  # OCR/okuma tekrar yapılmadı


def test_rejected_upload_is_not_saved(settings):
    outcome = _process("notlar.txt", b"metin", fake_pipeline(), settings)

    assert outcome.level == "error" and outcome.entry is None
    assert not settings.upload_dir.exists()


def test_ingestion_error_is_reported_without_raising(settings):
    pipeline = fake_pipeline(ingestion=FakeIngestion(error=DocumentParseError("'bozuk.pdf' işlenemedi")))
    outcome = _process("bozuk.pdf", PDF, pipeline, settings)
    assert outcome.level == "error" and "işlenemedi" in outcome.message


def test_unexpected_error_is_reported_without_raising(settings):
    pipeline = fake_pipeline(indexing=FakeIndexing(error=RuntimeError("disk dolu")))
    outcome = _process("rapor.pdf", PDF, pipeline, settings)
    assert outcome.level == "error" and outcome.entry is None


def test_document_without_text_is_not_offered_for_questions(settings):
    pipeline = fake_pipeline(ingestion=FakeIngestion(pages=["", "  "]))
    outcome = _process("bos_tarama.png", b"\x89PNG", pipeline, settings)
    assert outcome.level == "warning" and outcome.entry is None
