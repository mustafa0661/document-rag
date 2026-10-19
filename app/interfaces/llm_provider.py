"""LLM sağlayıcı sözleşmesi."""

from abc import ABC, abstractmethod
from typing import Any


class LlmProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Verilen JSON Schema'ya uyan bir nesne üretir.

        Raises:
            LlmUnavailableError: Servise ulaşılamıyor veya model yüklü değil.
            LlmResponseError: Cevap geçerli bir JSON nesnesi değil.
        """
