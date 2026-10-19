"""Gerçek belgeleri indeksleyip soru sorar; sonuçları mesafeleriyle gösterir.

Kullanım (proje kökünden):
    python -m app.scripts.search_documents rapor.pdf fatura.jpg -q "Glukoz kaç?" -q "Son ödeme tarihi?"
    python -m app.scripts.search_documents rapor.pdf             # soru sormak için etkileşimli mod
    python -m app.scripts.search_documents --reset-index          # indeksi tamamen sil

Amaç: chunking ve retrieval kalitesini gerçek belgelerde gözle incelemek ve
alakalı/alakasız soruların mesafe dağılımını ölçerek ileride bir benzerlik
eşiği belirlemek. Arama yalnızca bu komutta verilen belgeler içinde yapılır.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

PREVIEW_CHARS = 160


def main() -> int:
    arg_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg_parser.add_argument("files", nargs="*", type=Path, help="PDF/JPG/PNG dosyaları")
    arg_parser.add_argument("-q", "--query", action="append", default=[], help="Soru (birden fazla verilebilir)")
    arg_parser.add_argument("--top-k", type=int, default=None)
    arg_parser.add_argument("--reindex", action="store_true", help="Belgeleri zorla yeniden indeksle")
    arg_parser.add_argument("--reset-index", action="store_true", help="İndeksi tamamen sil")
    args = arg_parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    # Ağır importlar burada: --help hızlı kalsın.
    from app.core.config import RagSettings
    from app.core.exceptions import IndexConfigMismatchError, IngestionError
    from app.infrastructure.chroma_store import delete_collection

    settings = RagSettings.from_env()
    if args.reset_index:
        removed = delete_collection(settings.chroma_path, settings.collection_name)
        print("İndeks silindi." if removed else "Silinecek indeks yok.")
        if not args.files:
            return 0
    if not args.files:
        arg_parser.error("en az bir dosya verin")

    from app.bootstrap import build_pipeline

    print("Modeller yükleniyor...")
    started = time.perf_counter()
    try:
        pipeline = build_pipeline(settings)
    except IndexConfigMismatchError as exc:
        print(f"\nHATA: {exc}", file=sys.stderr)
        return 2
    ingestion, indexing, retrieval = pipeline.ingestion, pipeline.indexing, pipeline.retrieval
    print(f"Hazır ({time.perf_counter() - started:.1f} sn).\n")

    document_ids: list[str] = []
    for file_path in args.files:
        started = time.perf_counter()
        try:
            document = ingestion.ingest(file_path)
        except (IngestionError, FileNotFoundError) as exc:
            print(f"[{file_path.name}] HATA: {exc}")
            continue
        parsed = time.perf_counter()
        result = indexing.index_document(document, reindex=args.reindex)
        indexed = time.perf_counter()
        document_ids.append(document.document_id)
        print(
            f"[{document.file_name}] {document.page_count} sayfa, {result.chunk_count} chunk, "
            f"durum={result.status.value} | okuma {parsed - started:.1f} sn, "
            f"indeksleme {indexed - parsed:.1f} sn"
        )

    if not document_ids:
        return 1

    queries = args.query or _interactive_queries()
    for query in queries:
        started = time.perf_counter()
        results = retrieval.search(query, document_ids, args.top_k)
        print(f"\nSoru: {query}  ({(time.perf_counter() - started) * 1000:.0f} ms)")
        print("  #  mesafe  benzerlik  kaynak")
        for rank, item in enumerate(results, start=1):
            chunk = item.chunk
            preview = " ".join(chunk.text.split())[:PREVIEW_CHARS]
            print(
                f"  {rank}  {item.distance:.4f}  {item.similarity:.4f}     "
                f"{chunk.file_name} s.{chunk.page_number} ({':'.join(chunk.chunk_id.rsplit(':', 2)[-2:])})"
            )
            print(f"     {preview}")
    return 0


def _interactive_queries():
    print("\nSoru yazın (çıkmak için boş bırakıp Enter):")
    while True:
        query = input("> ").strip()
        if not query:
            return
        yield query


if __name__ == "__main__":
    sys.exit(main())
