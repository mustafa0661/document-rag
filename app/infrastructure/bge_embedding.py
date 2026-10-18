"""BAAI/bge-m3 dense embedding sağlayıcısı (sentence-transformers).

- Model yapıcıda bir kez yüklenir; aynı nesne tüm istekler için kullanılır.
- Vektörler normalize edilir (kosinüs mesafesiyle tutarlı).
- BGE-M3 sorgular için instruction/önek gerektirmez; belge ve sorgu aynı
  şekilde kodlanır.
- `max_seq_length` 512'ye sınırlanır: chunk'lar zaten en fazla ~500 token;
  modelin 8192 tokenlık sınırı CPU'da uzun bir sorguda gereksiz bellek ve
  süre harcatırdı.
"""

from sentence_transformers import SentenceTransformer

from app.core.exceptions import EmbeddingDimensionError
from app.interfaces.embedding_provider import EmbeddingProvider

DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_DIMENSION = 1024


class BgeM3EmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        expected_dimension: int = DEFAULT_DIMENSION,
        device: str = "cpu",
        batch_size: int = 16,
        max_seq_length: int = 512,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._model = SentenceTransformer(model_name, device=device)
        self._model.max_seq_length = max_seq_length

        actual = self._model.get_embedding_dimension()
        if actual != expected_dimension:
            raise EmbeddingDimensionError(
                f"'{model_name}' modeli {actual} boyutlu vektör üretiyor; "
                f"yapılandırmada {expected_dimension} bekleniyor."
            )
        self._dimension = expected_dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        # BGE-M3 sorgu için önek istemez; belgeyle aynı şekilde kodlanır.
        return self.embed_documents([text])[0]

    def count_tokens(self, text: str) -> int:
        return len(self._model.tokenizer(text, add_special_tokens=False)["input_ids"])
