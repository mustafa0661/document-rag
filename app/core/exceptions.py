"""Ingestion hataları.

Hepsi `IngestionError`dan türer; böylece üst katmanlar (ileride arayüz)
tek bir `except IngestionError` ile kullanıcıya anlaşılır mesaj gösterebilir.
"""


class IngestionError(Exception):
    """Belge işleme sırasında oluşan tüm beklenen hataların tabanı."""


class UnsupportedFileTypeError(IngestionError):
    """Dosya uzantısı parser tarafından desteklenmiyor."""


class EmptyFileError(IngestionError):
    """Dosya 0 bayt."""


class DocumentParseError(IngestionError):
    """Dosya okunamadı veya dönüştürülemedi (bozuk dosya, uyumsuz içerik vb.)."""


class IndexConfigMismatchError(Exception):
    """Mevcut vektör indeksi farklı bir model veya chunk ayarıyla oluşturulmuş."""


class EmbeddingDimensionError(Exception):
    """Embedding boyutu veya sayısı beklenenle uyuşmuyor."""


class InvalidQueryError(ValueError):
    """Arama isteği geçersiz: boş sorgu, boş belge listesi veya geçersiz top_k."""


class LlmUnavailableError(Exception):
    """LLM servisine ulaşılamıyor (Ollama kapalı, model yüklü değil, zaman aşımı)."""


class LlmResponseError(Exception):
    """LLM beklenen yapıda bir cevap döndürmedi."""
