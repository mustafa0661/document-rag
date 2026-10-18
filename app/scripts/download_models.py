"""Docling, EasyOCR ve BGE-M3 modellerini önceden indirir.

Kullanım (proje kökünden):
    python -m app.scripts.download_models

Modeller normalde ilk kullanımda indirilir. Bu adımı kurulumda ayrıca
çalıştırmak, ağ sorunlarının test veya ilk kullanım sırasında değil burada,
anlaşılır bir mesajla görünmesini sağlar. Zaten indirilmiş modeller yeniden
indirilmez; betik yalnızca yükleyip doğrular.
"""

import logging
import sys
import time


def _step(title: str, action) -> bool:
    print(f"\n{title}")
    started = time.perf_counter()
    try:
        action()
    except Exception:
        logging.exception("Başarısız: %s", title)
        return False
    print(f"  hazır ({time.perf_counter() - started:.1f} sn)")
    return True


def _docling() -> None:
    from app.infrastructure.docling_parser import DoclingParser

    DoclingParser().warm_up()


def _embedding() -> None:
    from app.core.config import RagSettings
    from app.infrastructure.bge_embedding import BgeM3EmbeddingProvider

    settings = RagSettings.from_env()
    BgeM3EmbeddingProvider(settings.embedding_model, settings.embedding_dimension)


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    print("Modeller hazırlanıyor. İlk çalıştırmada indirme birkaç dakika sürebilir.")
    results = [
        _step("1/2 Docling layout/tablo modelleri ve EasyOCR (tr, en)", _docling),
        _step("2/2 BAAI/bge-m3 embedding modeli (~2.3 GB)", _embedding),
    ]
    if not all(results):
        print(
            "\nBazı modeller hazırlanamadı. README.md içindeki 'Sorun giderme' bölümüne bakın; "
            "yardım isterken yukarıdaki hata çıktısının tamamını paylaşın.",
            file=sys.stderr,
        )
        return 1
    print("\nTüm modeller hazır.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
