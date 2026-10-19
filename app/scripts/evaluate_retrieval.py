"""Gerçek belgelerle tekrarlanabilir retrieval değerlendirmesi.

Kullanım (proje kökünden):
    python -m app.scripts.evaluate_retrieval                    # eval/retrieval_eval.json
    python -m app.scripts.evaluate_retrieval baska_set.json
    python -m app.scripts.evaluate_retrieval --reset            # değerlendirme indeksini sil

Soru seti (JSON) her soru için beklenen dosyayı ve sayfa(ları) içerir; bu
beklentiler sistem çalıştırılmadan ÖNCE yazılmalıdır. Soru türleri:
    relevant      cevabı belgede var (expected zorunlu)
    near_miss     konu aynı ama cevap belgede yok (eşiği asıl belirleyen tür)
    out_of_scope  tamamen alakasız

Belgeler ana indeksten ayrı bir indekste tutulur (data/eval_chroma) ve
tekrar çalıştırmada yeniden okunmaz/indekslenmez. Rapor eval/results/
altına Markdown olarak yazılır; TESTING.md'ye doğrudan aktarılabilir.
"""

import argparse
import json
import logging
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DEFAULT_EVAL_FILE = Path("eval/retrieval_eval.json")
EVAL_CHROMA_PATH = Path("data/eval_chroma")
RESULTS_DIR = Path("eval/results")
TOP_K = 5
THRESHOLDS = tuple(round(0.30 + 0.05 * step, 2) for step in range(11))  # 0.30 … 0.80
QUESTION_TYPES = ("relevant", "near_miss", "out_of_scope")
LANGUAGES = ("tr", "en", "cross")


class EvalSetError(ValueError):
    """Soru seti dosyası geçersiz."""


@dataclass(frozen=True)
class Expected:
    file: str
    pages: frozenset[int]


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    type: str
    language: str
    expected: tuple[Expected, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class EvalSet:
    documents: tuple[Path, ...]
    questions: tuple[EvalQuestion, ...]


@dataclass(frozen=True)
class Hit:
    file_name: str
    page_number: int
    distance: float
    preview: str = ""


@dataclass(frozen=True)
class QuestionResult:
    question: EvalQuestion
    hits: tuple[Hit, ...]
    latency_ms: float = 0.0
    rank: int | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rank", rank_of_expected(self.hits, self.question.expected))

    @property
    def top_distance(self) -> float | None:
        return self.hits[0].distance if self.hits else None


# --- Soru seti --------------------------------------------------------------


def load_eval_set(path: Path) -> EvalSet:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EvalSetError(f"Soru seti bulunamadı: {path}") from None
    except json.JSONDecodeError as exc:
        raise EvalSetError(f"{path} geçerli JSON değil: {exc}") from None

    documents = tuple(Path(item) for item in raw.get("documents", []))
    if not documents:
        raise EvalSetError("'documents' listesi boş.")
    document_names = {doc.name for doc in documents}

    questions: list[EvalQuestion] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw.get("questions", []), start=1):
        where = f"{index}. soru ({item.get('id', 'id yok')})"
        question_id, text = item.get("id"), (item.get("question") or "").strip()
        question_type, language = item.get("type"), item.get("language", "tr")
        if not question_id or question_id in seen_ids:
            raise EvalSetError(f"{where}: 'id' eksik veya tekrar ediyor.")
        if not text:
            raise EvalSetError(f"{where}: 'question' boş.")
        if question_type not in QUESTION_TYPES:
            raise EvalSetError(f"{where}: 'type' şunlardan biri olmalı: {', '.join(QUESTION_TYPES)}.")
        if language not in LANGUAGES:
            raise EvalSetError(f"{where}: 'language' şunlardan biri olmalı: {', '.join(LANGUAGES)}.")

        expected = []
        for entry in item.get("expected", []):
            file_name, pages = entry.get("file"), entry.get("pages", [])
            if file_name not in document_names:
                raise EvalSetError(f"{where}: beklenen dosya '{file_name}' documents listesinde yok.")
            if not pages or not all(isinstance(p, int) and p > 0 for p in pages):
                raise EvalSetError(f"{where}: 'pages' pozitif tam sayılardan oluşan bir liste olmalı.")
            expected.append(Expected(file_name, frozenset(pages)))
        if question_type == "relevant" and not expected:
            raise EvalSetError(f"{where}: 'relevant' sorular için 'expected' zorunlu.")
        if question_type != "relevant" and expected:
            raise EvalSetError(f"{where}: cevabı belgede olmayan sorularda 'expected' olmamalı.")

        seen_ids.add(question_id)
        questions.append(EvalQuestion(question_id, text, question_type, language, tuple(expected), item.get("note", "")))

    if not questions:
        raise EvalSetError("'questions' listesi boş.")
    return EvalSet(documents, tuple(questions))


# --- Metrikler (saf fonksiyonlar) ------------------------------------------


def rank_of_expected(hits: tuple[Hit, ...], expected: tuple[Expected, ...]) -> int | None:
    """Beklenen (dosya, sayfa) çiftinin sonuçlardaki ilk sırası (1'den başlar); yoksa None."""
    for rank, hit in enumerate(hits, start=1):
        if any(hit.file_name == e.file and hit.page_number in e.pages for e in expected):
            return rank
    return None


def ranking_metrics(results: list[QuestionResult]) -> dict[str, float]:
    """Yalnızca 'relevant' sorular için Hit@1, Hit@K ve MRR."""
    relevant = [r for r in results if r.question.type == "relevant"]
    if not relevant:
        return {"count": 0, "hit@1": 0.0, f"hit@{TOP_K}": 0.0, "mrr": 0.0}
    return {
        "count": len(relevant),
        "hit@1": sum(r.rank == 1 for r in relevant) / len(relevant),
        f"hit@{TOP_K}": sum(r.rank is not None for r in relevant) / len(relevant),
        "mrr": sum(1 / r.rank for r in relevant if r.rank) / len(relevant),
    }


def threshold_sweep(results: list[QuestionResult], thresholds=THRESHOLDS) -> list[dict[str, float]]:
    """Her eşik için: korunan alakalı oranı ve reddedilen cevapsız soru oranları.

    Bir soru, en iyi sonucunun mesafesi eşikten büyükse (veya hiç sonuç yoksa)
    "reddedilmiş" sayılır. Alakalı bir sorunun reddedilmesi, sistemin cevabı
    belgede olan bir soruya "bilgi yok" demesi anlamına gelir.
    """

    def kept(result: QuestionResult, threshold: float) -> bool:
        return result.top_distance is not None and result.top_distance <= threshold

    def share(group: list[QuestionResult], threshold: float, want_kept: bool) -> float | None:
        if not group:
            return None
        return sum(kept(r, threshold) == want_kept for r in group) / len(group)

    by_type = {t: [r for r in results if r.question.type == t] for t in QUESTION_TYPES}
    unanswerable = by_type["near_miss"] + by_type["out_of_scope"]
    rows = []
    for threshold in thresholds:
        relevant_kept = share(by_type["relevant"], threshold, True)
        rejected = share(unanswerable, threshold, False)
        rows.append(
            {
                "threshold": threshold,
                "relevant_kept": relevant_kept,
                "near_miss_rejected": share(by_type["near_miss"], threshold, False),
                "out_of_scope_rejected": share(by_type["out_of_scope"], threshold, False),
                "unanswerable_rejected": rejected,
                "balanced": None
                if relevant_kept is None or rejected is None
                else (relevant_kept + rejected) / 2,
            }
        )
    return rows


def suggest_threshold(rows: list[dict[str, float]]) -> dict[str, float] | None:
    """En yüksek dengeli doğruluğu veren eşik; eşitlikte alakalı soruları daha çok
    koruyan (daha büyük) eşik seçilir: cevabı olan soruya "bilgi yok" demek,
    LLM aşamasında ikinci bir kontrol olacağı için daha az zararlıdır."""
    candidates = [row for row in rows if row["balanced"] is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["balanced"], row["relevant_kept"], row["threshold"]))


def distance_stats(results: list[QuestionResult]) -> dict[str, dict[str, float]]:
    stats = {}
    for question_type in QUESTION_TYPES:
        distances = [r.top_distance for r in results if r.question.type == question_type and r.top_distance is not None]
        if distances:
            stats[question_type] = {
                "count": len(distances),
                "min": min(distances),
                "median": statistics.median(distances),
                "max": max(distances),
            }
    return stats


# --- Rapor ------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "—" if value is None else f"%{value * 100:.0f}"


def render_report(results: list[QuestionResult], document_rows: list[dict], settings_line: str) -> str:
    lines = [
        f"# Retrieval değerlendirmesi — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        settings_line,
        "",
        "## Belgeler",
        "",
        "| Dosya | Sayfa | Chunk | Okuma (sn) | İndeksleme (sn) |",
        "|---|---|---|---|---|",
    ]
    for row in document_rows:
        lines.append(
            f"| {row['file']} | {row.get('pages', '—')} | {row['chunks']} | "
            f"{row.get('parse_s', '—')} | {row.get('index_s', '—')} |"
        )

    lines += ["", "## Sıralama başarısı (yalnızca cevabı belgede olan sorular)", "",
              f"| Grup | Soru | Hit@1 | Hit@{TOP_K} | MRR |", "|---|---|---|---|---|"]
    groups = [("Tümü", results)] + [
        (label, [r for r in results if r.question.language == code])
        for code, label in (("tr", "Türkçe soru → Türkçe belge"), ("en", "İngilizce"), ("cross", "Diller arası"))
    ]
    for label, group in groups:
        metrics = ranking_metrics(group)
        if metrics["count"]:
            lines.append(
                f"| {label} | {metrics['count']} | {_pct(metrics['hit@1'])} | "
                f"{_pct(metrics[f'hit@{TOP_K}'])} | {metrics['mrr']:.2f} |"
            )

    lines += ["", "## En iyi sonucun mesafesi (küçük = daha alakalı)", "",
              "| Soru türü | Soru | En küçük | Medyan | En büyük |", "|---|---|---|---|---|"]
    for question_type, stat in distance_stats(results).items():
        lines.append(
            f"| {question_type} | {stat['count']} | {stat['min']:.4f} | {stat['median']:.4f} | {stat['max']:.4f} |"
        )

    rows = threshold_sweep(results)
    lines += ["", "## Eşik taraması", "",
              "Bir soru, en iyi sonucunun mesafesi eşikten büyükse reddedilir (\"belgede bu bilgi yok\").", "",
              "| Eşik | Alakalı korunan | near_miss reddedilen | out_of_scope reddedilen | Dengeli |",
              "|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row['threshold']:.2f} | {_pct(row['relevant_kept'])} | {_pct(row['near_miss_rejected'])} | "
            f"{_pct(row['out_of_scope_rejected'])} | {_pct(row['balanced'])} |"
        )
    best = suggest_threshold(rows)
    if best:
        lines += ["", f"**Ölçüme göre aday eşik: {best['threshold']:.2f}** — alakalı soruların "
                  f"{_pct(best['relevant_kept'])}'i korunuyor, cevabı belgede olmayan soruların "
                  f"{_pct(best['unanswerable_rejected'])}'i reddediliyor. Bu bir öneri; karar soru "
                  "setinin büyüklüğü ve hataların türü birlikte değerlendirilerek verilmeli."]

    lines += ["", "## Soru bazında sonuçlar", "",
              "| ID | Tür | Dil | Soru | Beklenen | En iyi sonuç | Sıra | Mesafe |",
              "|---|---|---|---|---|---|---|---|"]
    for r in results:
        expected = ", ".join(f"{e.file} s.{','.join(map(str, sorted(e.pages)))}" for e in r.question.expected) or "—"
        top = f"{r.hits[0].file_name} s.{r.hits[0].page_number}" if r.hits else "—"
        mark = "" if r.question.type != "relevant" else (" ✅" if r.rank == 1 else (" ⚠️" if r.rank else " ❌"))
        distance = f"{r.top_distance:.4f}" if r.top_distance is not None else "—"
        lines.append(
            f"| {r.question.id} | {r.question.type} | {r.question.language} | {r.question.question} | "
            f"{expected} | {top} | {r.rank or '—'}{mark} | {distance} |"
        )

    failures = [r for r in results if r.question.type == "relevant" and r.rank != 1]
    if failures:
        lines += ["", "## İlk sırada bulunamayan sorular", ""]
        for r in failures:
            lines.append(f"**{r.question.id} — {r.question.question}**" + (f" _(not: {r.question.note})_" if r.question.note else ""))
            for rank, hit in enumerate(r.hits[:3], start=1):
                lines.append(f"{rank}. `{hit.file_name}` s.{hit.page_number}, d={hit.distance:.4f}: {hit.preview}")
            lines.append("")
    latencies = [r.latency_ms for r in results]
    lines += ["", f"Ortalama sorgu süresi: {statistics.mean(latencies):.0f} ms (embedding + arama, CPU)."]
    return "\n".join(lines) + "\n"


# --- Çalıştırma -------------------------------------------------------------


def main() -> int:
    arg_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg_parser.add_argument("eval_file", nargs="?", type=Path, default=DEFAULT_EVAL_FILE)
    arg_parser.add_argument("--reindex", action="store_true", help="Belgeleri yeniden okuyup indeksle")
    arg_parser.add_argument("--reset", action="store_true", help="Değerlendirme indeksini sil ve çık")
    args = arg_parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    from app.core.config import RagSettings
    from app.core.exceptions import IndexConfigMismatchError, IngestionError
    from app.infrastructure.chroma_store import delete_collection

    settings = RagSettings.from_env()
    if args.reset:
        removed = delete_collection(EVAL_CHROMA_PATH, settings.collection_name)
        print("Değerlendirme indeksi silindi." if removed else "Silinecek indeks yok.")
        return 0

    try:
        eval_set = load_eval_set(args.eval_file)
    except EvalSetError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2
    missing = [str(doc) for doc in eval_set.documents if not doc.is_file()]
    if missing:
        print(f"HATA: Belge(ler) bulunamadı: {', '.join(missing)}", file=sys.stderr)
        return 2

    from app.bootstrap import build_pipeline
    from app.services.ingestion_service import IngestionService

    print("Modeller yükleniyor...")
    try:
        pipeline = build_pipeline(settings, chroma_path=EVAL_CHROMA_PATH)
    except IndexConfigMismatchError as exc:
        print(f"HATA: {exc}\nDeğerlendirme indeksini sıfırlamak için: --reset", file=sys.stderr)
        return 2

    document_ids, document_rows = [], []
    for path in eval_set.documents:
        document_id = IngestionService.compute_document_id(path)
        existing = pipeline.indexing.indexed_chunk_count(document_id)
        if existing and not args.reindex:
            print(f"[{path.name}] zaten indeksli ({existing} chunk), atlandı.")
            document_ids.append(document_id)
            document_rows.append({"file": path.name, "chunks": existing})
            continue
        started = time.perf_counter()
        try:
            document = pipeline.ingestion.ingest(path)
        except IngestionError as exc:
            print(f"[{path.name}] HATA: {exc}", file=sys.stderr)
            return 1
        parsed = time.perf_counter()
        result = pipeline.indexing.index_document(document, reindex=args.reindex)
        indexed = time.perf_counter()
        document_ids.append(document_id)
        document_rows.append({
            "file": path.name, "pages": document.page_count, "chunks": result.chunk_count,
            "parse_s": f"{parsed - started:.1f}", "index_s": f"{indexed - parsed:.1f}",
        })
        print(f"[{path.name}] {document.page_count} sayfa, {result.chunk_count} chunk "
              f"(okuma {parsed - started:.1f} sn, indeksleme {indexed - parsed:.1f} sn)")

    print(f"\n{len(eval_set.questions)} soru değerlendiriliyor...")
    results = []
    for question in eval_set.questions:
        started = time.perf_counter()
        retrieved = pipeline.retrieval.search(question.question, document_ids, TOP_K)
        latency = (time.perf_counter() - started) * 1000
        hits = tuple(
            Hit(r.chunk.file_name, r.chunk.page_number, r.distance, " ".join(r.chunk.text.split())[:150])
            for r in retrieved
        )
        results.append(QuestionResult(question, hits, latency))

    settings_line = (f"Model: `{settings.embedding_model}` · chunk {settings.chunk_size} token, "
                     f"overlap {settings.chunk_overlap} · top-k {TOP_K} · arama tüm değerlendirme belgelerinde")
    report = render_report(results, document_rows, settings_line)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / f"retrieval_{datetime.now():%Y%m%d-%H%M}.md"
    report_path.write_text(report, encoding="utf-8")

    metrics = ranking_metrics(results)
    best = suggest_threshold(threshold_sweep(results))
    print(f"\nHit@1 {_pct(metrics['hit@1'])} · Hit@{TOP_K} {_pct(metrics[f'hit@{TOP_K}'])} · MRR {metrics['mrr']:.2f}")
    if best:
        print(f"Aday eşik {best['threshold']:.2f}: alakalı korunan {_pct(best['relevant_kept'])}, "
              f"cevapsız reddedilen {_pct(best['unanswerable_rejected'])}")
    print(f"Rapor: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
