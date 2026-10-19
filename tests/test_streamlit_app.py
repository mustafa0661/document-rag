"""Streamlit arayüzü testleri (AppTest: gerçek betik, tarayıcı olmadan).

`build_pipeline` sahte bir pipeline döndürür ve çağrı sayısı ölçülür; böylece
modellerin her etkileşimde (rerun) yeniden yüklenmediği doğrudan doğrulanır.
"""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import app.bootstrap as bootstrap
from app.core.exceptions import LlmUnavailableError
from tests.fakes import FakeQuestionAnswering, fake_pipeline

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")
PDF = b"%PDF-1.4 sahte icerik"


@pytest.fixture
def backend(monkeypatch, tmp_path):
    st.cache_resource.clear()
    state = {"builds": 0, "pipeline": fake_pipeline()}

    def fake_build(settings, chroma_path=None):
        state["builds"] += 1
        return state["pipeline"]

    monkeypatch.setattr(bootstrap, "build_pipeline", fake_build)
    monkeypatch.setenv("RAG_UPLOAD_DIR", str(tmp_path / "uploads"))
    yield state
    st.cache_resource.clear()


def _app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def _upload_and_process(at: AppTest, name="rapor.pdf", data=PDF) -> AppTest:
    at.file_uploader[0].upload(name, data, "application/pdf").run()
    at.button(key="process").click().run()
    assert not at.exception, at.exception
    return at


def _chat_disabled(at: AppTest) -> bool:
    return at.chat_input[0].proto.disabled


def test_models_are_loaded_once_across_reruns_and_sessions(backend):
    first = _app()
    first.run()
    first.run()
    second = _app()  # ayrı bir oturum

    assert backend["builds"] == 1
    assert not second.exception


def test_question_cannot_be_asked_without_documents(backend):
    at = _app()
    assert _chat_disabled(at)
    assert "belge yükleyip" in at.chat_input[0].proto.placeholder


def test_upload_process_and_ask_shows_answer_with_sources(backend):
    at = _upload_and_process(_app())

    assert len(at.session_state["documents"]) == 1
    assert not _chat_disabled(at)
    assert any("hazır" in s.value for s in at.sidebar.success)

    at.chat_input[0].set_value("Açlık şekeri kaç?").run()

    qa = backend["pipeline"].question_answering
    assert qa.calls == [("Açlık şekeri kaç?", list(at.session_state["documents"]))]
    assert any("98 mg/dL" in m.value for m in at.markdown)
    assert at.expander[0].label == "Kaynaklar (1)"
    assert any("kaynak metinden doğrulayın" in c.value for c in at.caption)
    assert any("rapor.pdf" in m.value and "sayfa 2" in m.value for m in at.markdown)


def test_deselecting_all_documents_disables_questions(backend):
    at = _upload_and_process(_app())
    at.checkbox[0].uncheck().run()
    assert _chat_disabled(at)


def test_uploading_same_document_again_does_not_reprocess(backend):
    at = _upload_and_process(_app())
    at = _upload_and_process(at, name="kopya.pdf")

    assert len(at.session_state["documents"]) == 1
    assert len(backend["pipeline"].ingestion.calls) == 1
    assert any("zaten indeksli" in s.value for s in at.sidebar.info)


def test_ollama_down_shows_clear_error_and_app_keeps_working(backend):
    backend["pipeline"].question_answering = FakeQuestionAnswering(
        error=LlmUnavailableError("Ollama'ya bağlanılamadı (http://localhost:11434).")
    )
    at = _upload_and_process(_app())

    at.chat_input[0].set_value("Açlık şekeri kaç?").run()

    assert not at.exception
    assert any("bağlanılamadı" in e.value for e in at.error)
    assert not _chat_disabled(at)  # uygulama çalışmaya devam ediyor


def test_unexpected_error_does_not_crash_the_app(backend):
    backend["pipeline"].question_answering = FakeQuestionAnswering(error=RuntimeError("beklenmeyen"))
    at = _upload_and_process(_app())

    at.chat_input[0].set_value("Soru?").run()

    assert not at.exception
    assert any("Beklenmeyen bir hata" in e.value for e in at.error)


def test_sessions_do_not_share_documents_or_chat(backend):
    first = _upload_and_process(_app())
    first.chat_input[0].set_value("Açlık şekeri kaç?").run()

    second = _app()

    assert len(first.session_state["documents"]) == 1 and len(first.session_state["messages"]) == 2
    assert second.session_state["documents"] == {} and second.session_state["messages"] == []
    assert _chat_disabled(second)


def test_model_loading_failure_is_shown_without_crash(monkeypatch):
    st.cache_resource.clear()

    def failing_build(settings, chroma_path=None):
        raise OSError("model dosyası bulunamadı")

    monkeypatch.setattr(bootstrap, "build_pipeline", failing_build)
    at = AppTest.from_file(APP, default_timeout=30).run()

    assert not at.exception
    assert any("Modeller yüklenemedi" in e.value for e in at.error)
    st.cache_resource.clear()
