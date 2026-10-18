"""Embedding çıktısının sayı ve boyut kontrolü (indeksleme ve arama ortak kullanır).

Kontrol servis katmanında yapılır, provider'a güvenilmez: yanlış boyutlu bir
vektör veritabanına girerse aramaları sessizce bozar.
"""

from app.core.exceptions import EmbeddingDimensionError


def validate_embeddings(
    embeddings: list[list[float]], expected_count: int, expected_dimension: int
) -> None:
    if len(embeddings) != expected_count:
        raise EmbeddingDimensionError(
            f"{expected_count} metin için {len(embeddings)} embedding üretildi."
        )
    wrong = {len(vector) for vector in embeddings if len(vector) != expected_dimension}
    if wrong:
        raise EmbeddingDimensionError(
            f"Embedding boyutu {sorted(wrong)}; beklenen {expected_dimension}."
        )
