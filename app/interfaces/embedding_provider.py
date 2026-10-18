"""Embedding sağlayıcı sözleşmesi."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Belge metinlerini normalize edilmiş vektörlere çevirir (girdi sırasıyla)."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Kullanıcı sorusunu normalize edilmiş vektöre çevirir.

        Belge ve sorgu için ayrı metot olması bilinçlidir: bazı modeller
        (ör. E5) ikisine farklı önek ister. BGE-M3 istemez.
        """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Metnin bu modelin tokenizer'ına göre token sayısı (özel tokenlar hariç).

        Chunk boyutu modelin kendi tokenlarıyla ölçülür; kelime sayısı Türkçe
        gibi eklemeli dillerde gerçek token sayısını olduğundan az gösterir.
        """
