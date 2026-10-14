"""Docling ve EasyOCR modellerini önceden indirir.

Kullanım (proje kökünden):
    python -m scripts.download_models

Modeller normalde ilk belge işlenirken indirilir. Bu adımı kurulumda ayrıca
çalıştırmak, ağ sorunlarının test veya ilk kullanım sırasında değil burada,
anlaşılır bir mesajla görünmesini sağlar. Modeller zaten indirilmişse
yeniden indirilmez; betik yalnızca yükleyip doğrular.
"""

import logging
import sys
import time

from app.infrastructure.docling_parser import DEFAULT_OCR_LANGUAGES, DoclingParser


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    languages = ", ".join(DEFAULT_OCR_LANGUAGES)
    print(f"Docling layout/tablo modelleri ve EasyOCR ({languages}) modelleri hazırlanıyor...")
    print("İlk çalıştırmada indirme birkaç dakika sürebilir.")

    started = time.perf_counter()
    try:
        DoclingParser().warm_up()
    except Exception:
        logging.exception("Modeller indirilemedi veya yüklenemedi.")
        print(
            "\nREADME.md içindeki 'Sorun giderme' bölümüne bakın. "
            "Yardım isterken yukarıdaki hata çıktısının tamamını paylaşın.",
            file=sys.stderr,
        )
        return 1

    print(f"Modeller hazır ({time.perf_counter() - started:.1f} sn).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
