"""Retrieval değerlendirme betiğinin metrik ve doğrulama testleri (model gerekmez).

Beklenen değerler elle hesaplanabilecek küçük örneklerle seçildi: raporda
sunulacak rakamların doğruluğu bu testlere dayanıyor.
"""

import json

import pytest

from app.scripts.evaluate_retrieval import (
    EvalQuestion,
    EvalSetError,
    Expected,
    Hit,
    QuestionResult,
    load_eval_set,
    rank_of_expected,
    ranking_metrics,
    render_report,
    suggest_threshold,
    threshold_sweep,
)


def _question(qid, qtype="relevant", language="tr", expected=(("a.pdf", {2}),)):
    exp = tuple(Expected(f, frozenset(p)) for f, p in expected) if qtype == "relevant" else ()
    return EvalQuestion(qid, f"soru {qid}", qtype, language, exp)


def _result(question, *hits):
    return QuestionResult(question, tuple(Hit(f, p, d) for f, p, d in hits))


# --- Sıra hesabı ----------------------------------------------------------


def test_rank_is_position_of_first_matching_file_and_page():
    hits = (Hit("a.pdf", 1, 0.2), Hit("b.pdf", 2, 0.3), Hit("a.pdf", 2, 0.4))
    assert rank_of_expected(hits, (Expected("a.pdf", frozenset({2})),)) == 3


def test_any_of_several_expected_pages_counts():
    hits = (Hit("a.pdf", 5, 0.2),)
    assert rank_of_expected(hits, (Expected("a.pdf", frozenset({4, 5})),)) == 1


def test_same_page_number_in_other_file_does_not_count():
    hits = (Hit("b.pdf", 2, 0.2),)
    assert rank_of_expected(hits, (Expected("a.pdf", frozenset({2})),)) is None


# --- Sıralama metrikleri ----------------------------------------------------


def test_hit_and_mrr_on_hand_computed_example():
    results = [
        _result(_question("q1"), ("a.pdf", 2, 0.30)),                         # sıra 1
        _result(_question("q2"), ("a.pdf", 9, 0.30), ("a.pdf", 2, 0.35)),    # sıra 2
        _result(_question("q3"), ("a.pdf", 9, 0.30)),                         # bulunamadı
        _result(_question("q4", "near_miss"), ("a.pdf", 1, 0.70)),            # hesaba katılmaz
    ]

    metrics = ranking_metrics(results)

    assert metrics["count"] == 3
    assert metrics["hit@1"] == pytest.approx(1 / 3)
    assert metrics["hit@5"] == pytest.approx(2 / 3)
    assert metrics["mrr"] == pytest.approx((1 + 1 / 2 + 0) / 3)


# --- Eşik taraması ----------------------------------------------------------


def test_threshold_sweep_counts_kept_and_rejected_correctly():
    results = [
        _result(_question("r1"), ("a.pdf", 2, 0.30)),
        _result(_question("r2"), ("a.pdf", 2, 0.50)),
        _result(_question("n1", "near_miss"), ("a.pdf", 1, 0.45)),
        _result(_question("o1", "out_of_scope"), ("a.pdf", 1, 0.70)),
        _result(_question("o2", "out_of_scope")),  # hiç sonuç yok → her eşikte reddedilir
    ]

    rows = {row["threshold"]: row for row in threshold_sweep(results, thresholds=(0.40, 0.60))}

    assert rows[0.40]["relevant_kept"] == pytest.approx(1 / 2)
    assert rows[0.40]["near_miss_rejected"] == pytest.approx(1.0)
    assert rows[0.40]["out_of_scope_rejected"] == pytest.approx(1.0)
    assert rows[0.40]["unanswerable_rejected"] == pytest.approx(1.0)
    assert rows[0.40]["balanced"] == pytest.approx(0.75)

    assert rows[0.60]["relevant_kept"] == pytest.approx(1.0)
    assert rows[0.60]["near_miss_rejected"] == pytest.approx(0.0)
    assert rows[0.60]["unanswerable_rejected"] == pytest.approx(2 / 3)
    assert rows[0.60]["balanced"] == pytest.approx((1 + 2 / 3) / 2)


def test_suggested_threshold_maximizes_balance_and_prefers_recall_on_ties():
    rows = [
        {"threshold": 0.4, "relevant_kept": 0.8, "unanswerable_rejected": 1.0, "balanced": 0.9},
        {"threshold": 0.5, "relevant_kept": 1.0, "unanswerable_rejected": 0.8, "balanced": 0.9},
        {"threshold": 0.6, "relevant_kept": 1.0, "unanswerable_rejected": 0.5, "balanced": 0.75},
    ]
    assert suggest_threshold(rows)["threshold"] == 0.5


def test_no_suggestion_without_both_question_kinds():
    results = [_result(_question("r1"), ("a.pdf", 2, 0.3))]
    assert suggest_threshold(threshold_sweep(results)) is None


def test_report_renders_all_sections():
    results = [
        _result(_question("r1"), ("a.pdf", 2, 0.30)),
        _result(_question("r2", language="cross"), ("a.pdf", 7, 0.40), ("a.pdf", 2, 0.45)),
        _result(_question("n1", "near_miss"), ("a.pdf", 1, 0.62)),
    ]
    report = render_report(results, [{"file": "a.pdf", "pages": 9, "chunks": 20}], "ayarlar")

    for section in ("## Belgeler", "## Sıralama başarısı", "## Eşik taraması", "## Soru bazında sonuçlar",
                    "## İlk sırada bulunamayan sorular", "aday eşik"):
        assert section in report
    assert "| r2 |" in report and "⚠️" in report


# --- Soru seti doğrulaması ----------------------------------------------------


def _write(tmp_path, content):
    path = tmp_path / "eval.json"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return path


def _valid():
    return {
        "documents": ["eval/documents/a.pdf"],
        "questions": [
            {"id": "tr-01", "question": "Doz nedir?", "type": "relevant", "language": "tr",
             "expected": [{"file": "a.pdf", "pages": [2]}]},
            {"id": "nm-01", "question": "Başka ilacın dozu?", "type": "near_miss"},
        ],
    }


def test_valid_eval_set_is_loaded(tmp_path):
    eval_set = load_eval_set(_write(tmp_path, _valid()))
    assert [q.id for q in eval_set.questions] == ["tr-01", "nm-01"]
    assert eval_set.questions[0].expected == (Expected("a.pdf", frozenset({2})),)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d["questions"][0].pop("expected"), "zorunlu"),
        (lambda d: d["questions"][1].update(expected=[{"file": "a.pdf", "pages": [1]}]), "olmamalı"),
        (lambda d: d["questions"][0]["expected"][0].update(file="yok.pdf"), "documents listesinde yok"),
        (lambda d: d["questions"][0]["expected"][0].update(pages=[0]), "pozitif"),
        (lambda d: d["questions"][1].update(id="tr-01"), "tekrar"),
        (lambda d: d["questions"][1].update(type="baska"), "type"),
        (lambda d: d["questions"][1].update(language="de"), "language"),
        (lambda d: d.update(documents=[]), "documents"),
    ],
)
def test_invalid_eval_sets_are_rejected_with_clear_message(tmp_path, mutate, message):
    data = _valid()
    mutate(data)
    with pytest.raises(EvalSetError, match=message):
        load_eval_set(_write(tmp_path, data))
