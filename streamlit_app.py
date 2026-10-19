"""Belge Analiz ve Soru-Cevap — Streamlit arayüzü.

Çalıştırma (proje kökünden):  streamlit run streamlit_app.py

- Modeller `st.cache_resource` ile süreç başına bir kez yüklenir; her etkileşimde
  (rerun) yeniden yüklenmez.
- Belgeler, seçimler ve sohbet `st.session_state` içinde, yani oturuma özeldir.
  Vektör indeksi paylaşılır, ama her oturum yalnızca kendi yüklediği belgelerde arar.
"""

import logging
import re
import threading

import streamlit as st

import app.bootstrap as bootstrap
from app.core.config import RagSettings
from app.core.exceptions import IndexConfigMismatchError, InvalidQueryError, LlmResponseError, LlmUnavailableError
from app.core.models import AnswerStatus, QuestionAnswer
from app.ui.processing import SUPPORTED_EXTENSIONS, process_upload

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("streamlit_app")
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

st.set_page_config(page_title="Belge Soru-Cevap", page_icon="📄", layout="wide")


@st.cache_resource(show_spinner="Modeller yükleniyor (ilk açılışta 1–2 dakika sürebilir)…")
def load_resources():
    settings = RagSettings.from_env()
    return settings, bootstrap.build_pipeline(settings), threading.Lock()


def _init_session() -> None:
    st.session_state.setdefault("documents", {})      # document_id → DocumentEntry
    st.session_state.setdefault("messages", [])       # sohbet geçmişi
    st.session_state.setdefault("notices", [])        # son işlemin sonuç mesajları
    st.session_state.setdefault("uploader_key", 0)    # işlemden sonra yükleyiciyi temizlemek için


def _selected_document_ids() -> list[str]:
    return [doc_id for doc_id in st.session_state.documents if st.session_state.get(f"select_{doc_id}", True)]


def _render_sources(sources: list[dict]) -> None:
    with st.expander(f"Kaynaklar ({len(sources)})"):
        for source in sources:
            st.markdown(f"**{source['file_name']}** — sayfa {source['page_number']}")
            with st.container(border=True):
                # Kaynak metindeki Markdown başlıkları (#) cevaptan büyük görünmesin: kalın yaz.
                st.markdown(_HEADING_LINE_RE.sub(r"**\1**", source["text"]))


def _render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        kind = message.get("kind", "answer")
        if kind == "error":
            st.error(message["content"])
        elif kind == "notice":
            st.info(message["content"])
        else:
            st.markdown(message["content"])
        if message.get("sources"):
            _render_sources(message["sources"])


def _assistant_message(result: QuestionAnswer) -> dict:
    if result.status is AnswerStatus.ANSWERED:
        sources = [
            {"file_name": s.file_name, "page_number": s.page_number, "text": s.text} for s in result.sources
        ]
        return {"role": "assistant", "kind": "answer", "content": result.answer, "sources": sources}
    return {"role": "assistant", "kind": "notice", "content": result.answer}


def _sidebar(settings: RagSettings, pipeline, lock: threading.Lock) -> None:
    sidebar = st.sidebar
    sidebar.header("Belgeler")
    files = sidebar.file_uploader(
        "PDF, JPG veya PNG yükleyin",
        type=[ext.lstrip(".") for ext in sorted(SUPPORTED_EXTENSIONS)],
        accept_multiple_files=True,
        max_upload_size=settings.max_upload_mb,
        key=f"uploader_{st.session_state.uploader_key}",
    )
    if sidebar.button("Belgeleri işle", type="primary", disabled=not files, key="process"):
        notices = []
        for uploaded in files:
            with sidebar.status(f"{uploaded.name} işleniyor…", expanded=True) as status:
                outcome = process_upload(uploaded.name, uploaded.getvalue(), pipeline, settings, lock, status.write)
                state = "error" if outcome.level == "error" else "complete"
                status.update(label=uploaded.name, state=state, expanded=False)
            if outcome.entry:
                st.session_state.documents[outcome.entry.document_id] = outcome.entry
                st.session_state[f"select_{outcome.entry.document_id}"] = True
            notices.append((outcome.level, outcome.message))
        st.session_state.notices = notices
        st.session_state.uploader_key += 1  # yükleyiciyi temizle
        st.rerun()

    for level, text in st.session_state.notices:
        getattr(sidebar, level)(text)

    documents = st.session_state.documents
    if documents:
        sidebar.subheader("Soru sorulacak belgeler")
        for doc_id, entry in documents.items():
            sidebar.checkbox(f"{entry.file_name} · {entry.chunk_count} parça", key=f"select_{doc_id}")
        if st.session_state.messages and sidebar.button("Sohbeti temizle", key="clear_chat"):
            st.session_state.messages = []
            st.rerun()
    else:
        sidebar.caption("Henüz belge yok. Dosya seçip **Belgeleri işle**'ye basın.")


def _ask(question: str, pipeline, document_ids: list[str]) -> dict:
    try:
        result = pipeline.question_answering.answer(question, document_ids)
        return _assistant_message(result)
    except (InvalidQueryError, LlmUnavailableError) as exc:
        return {"role": "assistant", "kind": "error", "content": str(exc)}
    except LlmResponseError:
        logger.exception("LLM beklenmeyen yapıda cevap verdi")
        return {"role": "assistant", "kind": "error",
                "content": "Model beklenmeyen biçimde cevap verdi. Soruyu tekrar sormayı deneyin."}
    except Exception:  # Arayüz çökmemeli.
        logger.exception("Soru cevaplanırken beklenmeyen hata")
        return {"role": "assistant", "kind": "error",
                "content": "Beklenmeyen bir hata oluştu. Ayrıntılar logda; tekrar deneyin."}


def main() -> None:
    _init_session()
    st.title("📄 Belge Soru-Cevap")
    st.caption("Cevaplar yalnızca seçili belgelerden üretilir; her cevabın altında kaynak sayfalar gösterilir.")

    try:
        settings, pipeline, lock = load_resources()
    except IndexConfigMismatchError as exc:
        st.error(f"{exc}")
        st.stop()
    except Exception as exc:
        logger.exception("Modeller yüklenemedi")
        st.error(f"Modeller yüklenemedi: {exc}\n\nKurulum için README'deki adımlara bakın "
                 "(`python -m app.scripts.download_models`).")
        st.stop()

    _sidebar(settings, pipeline, lock)

    for message in st.session_state.messages:
        _render_message(message)

    selected = _selected_document_ids()
    if not st.session_state.documents:
        placeholder = "Önce soldan belge yükleyip işleyin"
    elif not selected:
        placeholder = "Soru sormak için soldan en az bir belge seçin"
    else:
        placeholder = f"Seçili {len(selected)} belge hakkında bir soru sorun"
    question = st.chat_input(placeholder, disabled=not selected, key="question")

    if question and selected:
        user_message = {"role": "user", "kind": "answer", "content": question}
        st.session_state.messages.append(user_message)
        _render_message(user_message)
        with st.spinner("Cevap hazırlanıyor…"):
            reply = _ask(question, pipeline, selected)
        st.session_state.messages.append(reply)
        _render_message(reply)


main()
