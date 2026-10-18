"""MarkdownChunker birim testleri. Token sayımı kelime sayısıyla yapılır (model gerekmez)."""

import pytest

from app.infrastructure.markdown_chunker import MarkdownChunker
from tests.fakes import make_document, word_count


def _chunker(chunk_size: int = 40, chunk_overlap: int = 8) -> MarkdownChunker:
    return MarkdownChunker(word_count, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def _sentences(count: int, prefix: str = "Cümle") -> str:
    return " ".join(f"{prefix} {i} burada yazılı." for i in range(1, count + 1))


def _table(rows: int) -> str:
    lines = ["| Tetkik | Sonuç | Birim |", "|---|---|---|"]
    lines += [f"| Tetkik{i} | {i}.5 | mg/dL |" for i in range(1, rows + 1)]
    return "\n".join(lines)


# --- Sayfa sınırları ve metadata -------------------------------------------


def test_chunks_never_cross_pages_and_keep_page_numbers():
    document = make_document([_sentences(30, "Birinci"), _sentences(30, "İkinci")])

    chunks = _chunker().chunk(document)

    assert {c.page_number for c in chunks} == {1, 2}
    for chunk in chunks:
        assert ("Birinci" in chunk.text) == (chunk.page_number == 1)
        assert ("İkinci" in chunk.text) == (chunk.page_number == 2)


def test_metadata_and_deterministic_unique_ids():
    document = make_document([_sentences(30), _sentences(5)], document_id="abc", file_name="rapor.pdf")

    first = _chunker().chunk(document)
    second = _chunker().chunk(document)

    assert first == second  # aynı girdi + aynı ayar → aynı chunk'lar
    assert len({c.chunk_id for c in first}) == len(first)
    assert first[0].chunk_id == "abc:p0001:c000"
    assert all(c.document_id == "abc" and c.file_name == "rapor.pdf" for c in first)
    assert [c.chunk_index for c in first if c.page_number == 2] == [0]


def test_empty_pages_are_skipped():
    document = make_document(["", "   \n  ", "Tek cümle."])

    chunks = _chunker().chunk(document)

    assert [(c.page_number, c.text) for c in chunks] == [(3, "Tek cümle.")]


def test_document_without_text_produces_no_chunks():
    assert _chunker().chunk(make_document(["", ""])) == []


# --- Boyut sınırı -----------------------------------------------------------


def test_chunk_size_is_a_hard_limit_for_all_content_types():
    giant_sentence = " ".join(f"kelime{i}" for i in range(120))  # cümle sonu yok
    giant_token = "x" * 500  # boşluksuz dizgi; kelime sayacında 1 token
    page = "\n\n".join(
        [
            "## Uzun Bir Bölüm Başlığı",
            _sentences(25),
            _table(30),
            giant_sentence,
            giant_token,
            "- madde bir\n- madde iki\n- madde üç",
        ]
    )

    chunks = _chunker(chunk_size=40, chunk_overlap=8).chunk(make_document([page]))

    assert chunks
    assert all(c.token_count <= 40 for c in chunks), [c.token_count for c in chunks]
    assert all(c.token_count == word_count(c.text) for c in chunks)
    # İçerik kaybolmadı: dev cümlenin her kelimesi bir chunk'ta var.
    joined = "\n".join(c.text for c in chunks)
    assert all(f"kelime{i}" in joined for i in range(120))


def test_oversized_sentence_is_split_by_words():
    sentence = " ".join(f"k{i}" for i in range(100)) + "."
    chunks = _chunker(chunk_size=30, chunk_overlap=0).chunk(make_document([sentence]))

    assert len(chunks) >= 4
    assert " ".join(c.text for c in chunks).split() == sentence.split()


def test_invalid_settings_are_rejected():
    with pytest.raises(ValueError):
        MarkdownChunker(word_count, chunk_size=0)
    with pytest.raises(ValueError):
        MarkdownChunker(word_count, chunk_size=100, chunk_overlap=50)


# --- Overlap ----------------------------------------------------------------


def _shared_words(previous: str, current: str) -> list[str]:
    """`current`in başındaki, `previous`in sonuyla aynı olan en uzun kelime dizisi."""
    previous_words, current_words = previous.split(), current.split()
    for n in range(min(len(previous_words), len(current_words)), 0, -1):
        if previous_words[-n:] == current_words[:n]:
            return current_words[:n]
    return []


def test_overlap_repeats_tail_of_previous_chunk_from_a_sentence_start():
    chunks = _chunker(chunk_size=30, chunk_overlap=8).chunk(make_document([_sentences(40)]))

    assert len(chunks) >= 3
    for previous, current in zip(chunks, chunks[1:]):
        shared = _shared_words(previous.text, current.text)
        assert 0 < len(shared) <= 8, (previous.text, current.text)
        assert shared[0] == "Cümle"  # overlap cümle başından başlıyor


def test_overlap_falls_back_to_words_when_last_sentence_is_too_long():
    long_sentences = " ".join(
        f"Bu {i} numaralı oldukça uzun cümle on kelimeden fazladır." for i in range(20)
    )
    chunks = _chunker(chunk_size=40, chunk_overlap=8).chunk(make_document([long_sentences]))

    assert len(chunks) >= 3
    for previous, current in zip(chunks, chunks[1:]):
        assert 0 < len(_shared_words(previous.text, current.text)) <= 8


def test_no_overlap_when_disabled():
    chunks = _chunker(chunk_size=30, chunk_overlap=0).chunk(make_document([_sentences(40)]))
    texts = [c.text for c in chunks]

    assert " ".join(texts).split() == _sentences(40).split()  # tekrar yok, kayıp yok


# --- Tablolar ---------------------------------------------------------------


def test_short_table_stays_intact_in_one_chunk():
    table = _table(3)
    chunks = _chunker(chunk_size=60).chunk(make_document([f"Açıklama paragrafı.\n\n{table}"]))

    assert any(table in c.text for c in chunks)


def test_long_table_is_split_and_every_part_repeats_the_header():
    table = _table(40)
    chunks = _chunker(chunk_size=40, chunk_overlap=8).chunk(make_document([table]))

    assert len(chunks) > 1
    seen_rows = []
    for chunk in chunks:
        lines = chunk.text.splitlines()
        assert lines[0] == "| Tetkik | Sonuç | Birim |"
        assert lines[1] == "|---|---|---|"
        seen_rows += lines[2:]
    assert seen_rows == table.splitlines()[2:]  # her satır tam bir kez, sırası korunmuş


def test_no_overlap_is_injected_into_tables():
    page = _sentences(10) + "\n\n" + _table(40)
    chunks = _chunker(chunk_size=40, chunk_overlap=8).chunk(make_document([page]))

    for chunk in chunks:
        if "| Tetkik |" in chunk.text:
            assert chunk.text.startswith("| Tetkik | Sonuç | Birim |")


# --- Başlıklar --------------------------------------------------------------


def test_heading_is_prefixed_to_section_chunks_and_carried_to_next_page():
    page1 = "## Laboratuvar Sonuçları\n\n" + _sentences(30)
    page2 = _sentences(3, "Devam")
    chunks = _chunker(chunk_size=30, chunk_overlap=8).chunk(make_document([page1, page2]))

    assert all(c.text.startswith("## Laboratuvar Sonuçları") for c in chunks)
    assert chunks[-1].page_number == 2 and "Devam" in chunks[-1].text


def test_new_heading_starts_a_new_chunk_without_overlap():
    page = "## Bölüm A\n\n" + _sentences(3, "Alfa") + "\n\n## Bölüm B\n\n" + _sentences(3, "Beta")
    chunks = _chunker(chunk_size=60).chunk(make_document([page]))

    assert len(chunks) == 2
    assert chunks[1].text.startswith("## Bölüm B")
    assert "Alfa" not in chunks[1].text


def test_heading_at_end_of_page_is_not_lost():
    chunks = _chunker().chunk(make_document([_sentences(3) + "\n\n## Sonraki Bölüm", "İçerik cümlesi."]))

    assert any(c.page_number == 1 and "## Sonraki Bölüm" in c.text for c in chunks)
    assert chunks[-1].text.startswith("## Sonraki Bölüm")  # sonraki sayfaya bağlam olarak taşındı
