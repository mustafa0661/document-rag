"""Gerçek bir belgeyi ingestion akışından geçirip sonucu inceler.

Kullanım (proje kökünden):
    python -m app.scripts.inspect_document belge.pdf
    python -m app.scripts.inspect_document belge1.pdf foto.jpg tarama.png

Her belge için sayfa sayısı, işlem süresi ve sayfa bazında özet ekrana yazılır;
tam çıktı `inspect_out/<dosya_adı>.md` dosyasına kaydedilir.
Uygulamanın kullandığı akışın aynısı kullanılır (IngestionService + DoclingParser).
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from app.core.exceptions import IngestionError
from app.core.models import IngestedDocument

OUTPUT_DIR = Path("inspect_out")
PREVIEW_CHARS = 200


def _has_table(text: str) -> bool:
    return any(line.lstrip().startswith("|") for line in text.splitlines())


def format_summary(document: IngestedDocument, elapsed: float) -> str:
    lines = [
        f"Dosya       : {document.file_name}",
        f"document_id : {document.document_id[:12]}…",
        f"Sayfa sayısı: {document.page_count}",
        f"Süre        : {elapsed:.1f} sn ({elapsed / max(document.page_count, 1):.1f} sn/sayfa)",
        "",
    ]
    for page in document.pages:
        flags = []
        if page.is_empty:
            flags.append("BOŞ")
        if _has_table(page.text):
            flags.append("TABLO")
        flag_text = f"  [{', '.join(flags)}]" if flags else ""
        preview = " ".join(page.text.split())[:PREVIEW_CHARS]
        lines.append(f"--- Sayfa {page.page_number}: {len(page.text)} karakter{flag_text}")
        if preview:
            lines.append(f"    {preview}{'…' if len(page.text) > PREVIEW_CHARS else ''}")
    return "\n".join(lines)


def format_full_output(document: IngestedDocument) -> str:
    parts = [f"# {document.file_name}\n"]
    for page in document.pages:
        parts.append(f"\n---\n\n<!-- Sayfa {page.page_number} -->\n\n{page.text or '_(boş sayfa)_'}\n")
    return "".join(parts)


def main() -> int:
    arg_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arg_parser.add_argument("files", nargs="+", type=Path, help="İncelenecek PDF/JPG/PNG dosyaları")
    args = arg_parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    # Docling importu modelleri yüklediği için burada yapılıyor; --help hızlı kalsın.
    from app.infrastructure.docling_parser import DoclingParser
    from app.services.ingestion_service import IngestionService

    print("Modeller yükleniyor...")
    started = time.perf_counter()
    parser = DoclingParser()
    parser.warm_up()
    print(f"Modeller hazır ({time.perf_counter() - started:.1f} sn).\n")

    service = IngestionService(parser)
    OUTPUT_DIR.mkdir(exist_ok=True)
    failures = 0

    for file_path in args.files:
        print("=" * 70)
        started = time.perf_counter()
        try:
            document = service.ingest(file_path)
        except (IngestionError, FileNotFoundError) as exc:
            failures += 1
            print(f"HATA ({type(exc).__name__}): {exc}\n")
            continue
        elapsed = time.perf_counter() - started

        print(format_summary(document, elapsed))
        output_path = OUTPUT_DIR / f"{file_path.stem}.md"
        output_path.write_text(format_full_output(document), encoding="utf-8")
        print(f"\nTam çıktı: {output_path}\n")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
