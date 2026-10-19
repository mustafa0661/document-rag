"""Soru-cevap akışı: soru → retrieval → bağlam → LLM (JSON) → kaynak doğrulama."""

import logging
from collections.abc import Callable

from app.core.exceptions import InvalidQueryError, LlmResponseError
from app.core.models import AnswerStatus, QuestionAnswer, RetrievedChunk, SourceReference
from app.interfaces.llm_provider import LlmProvider
from app.services.qa_prompt import (
    SYSTEM_PROMPT,
    answer_schema,
    detect_language,
    message,
    render_user_prompt,
    strip_citation_markers,
)
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class QuestionAnswerService:
    def __init__(
        self,
        retrieval: RetrievalService,
        llm: LlmProvider,
        count_tokens: Callable[[str], int],
        max_context_tokens: int = 3000,
        top_k: int = 5,
        max_distance: float | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._llm = llm
        self._count_tokens = count_tokens
        self._max_context_tokens = max_context_tokens
        self._top_k = top_k
        self._max_distance = max_distance

    def answer(self, question: str, document_ids: list[str]) -> QuestionAnswer:
        """Seçili belgelere dayanarak cevaplar.

        Raises:
            InvalidQueryError: Soru boş veya belge seçilmemiş.
            LlmUnavailableError: Ollama'ya ulaşılamıyor.
            LlmResponseError: Model beklenen yapıda cevap vermedi.
        """
        question = (question or "").strip()
        if not question:
            raise InvalidQueryError("Soru boş olamaz.")
        if not document_ids:
            raise InvalidQueryError("Soru sormak için en az bir belge seçin.")
        language = detect_language(question)

        hits = self._retrieval.search(question, list(document_ids), self._top_k)
        if self._max_distance is not None:
            hits = [hit for hit in hits if hit.distance <= self._max_distance]
        sources = self._build_sources(hits)
        if not sources:
            # Bağlam yoksa LLM çağrılmaz: modelin genel bilgisiyle cevap üretme fırsatı olmaz.
            return QuestionAnswer(question, AnswerStatus.NO_RELEVANT_CONTEXT, message("no_context", language))

        allowed = {source.source_id: source for source in sources}
        raw = self._llm.generate_json(
            SYSTEM_PROMPT, render_user_prompt(question, sources, language), answer_schema(list(allowed))
        )
        answerable, answer_text, cited_ids = _parse(raw)

        if not answerable:
            return QuestionAnswer(question, AnswerStatus.INSUFFICIENT_INFORMATION, message("insufficient", language))

        valid = [allowed[source_id] for source_id in dict.fromkeys(cited_ids) if source_id in allowed]
        rejected = tuple(source_id for source_id in dict.fromkeys(cited_ids) if source_id not in allowed)
        if rejected:
            logger.warning("LLM izin verilmeyen kaynak kimlikleri döndürdü (reddedildi): %s", rejected)

        answer_text = strip_citation_markers(answer_text)
        if not answer_text or not valid:
            # Kaynağa dayandırılamayan cevap kullanıcıya gösterilmez.
            logger.warning("Cevap geçerli kaynak içermediği için gösterilmiyor. Soru: %r", question)
            return QuestionAnswer(
                question, AnswerStatus.UNVERIFIED, message("unverified", language), rejected_source_ids=rejected
            )
        return QuestionAnswer(question, AnswerStatus.ANSWERED, answer_text, tuple(valid), rejected)

    def _build_sources(self, hits: list[RetrievedChunk]) -> list[SourceReference]:
        """Alaka sırasıyla, bağlam bütçesi dolana kadar kaynak ekler (en az bir kaynak)."""
        sources: list[SourceReference] = []
        used = 0
        for hit in hits:
            tokens = self._count_tokens(hit.chunk.text)
            if sources and used + tokens > self._max_context_tokens:
                break
            used += tokens
            chunk = hit.chunk
            sources.append(
                SourceReference(
                    source_id=f"S{len(sources) + 1}",
                    document_id=chunk.document_id,
                    file_name=chunk.file_name,
                    page_number=chunk.page_number,
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    distance=hit.distance,
                )
            )
        return sources


def _parse(raw: dict) -> tuple[bool, str, list[str]]:
    answerable, answer, source_ids = raw.get("answerable"), raw.get("answer"), raw.get("source_ids")
    if not isinstance(answerable, bool) or not isinstance(answer, str):
        raise LlmResponseError(f"Model cevabında 'answerable'/'answer' alanları eksik veya hatalı: {raw!r}")
    if not isinstance(source_ids, list) or not all(isinstance(item, str) for item in source_ids):
        raise LlmResponseError(f"Model cevabında 'source_ids' bir metin listesi değil: {raw!r}")
    return answerable, answer, source_ids
