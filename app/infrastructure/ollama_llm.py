"""Ollama tabanlı LLM sağlayıcısı (yapılandırılmış JSON çıktısı).

- `format` parametresine JSON Schema verilir; Ollama üretimi bu şemaya göre
  kısıtlar. Yine de çıktı servis katmanında ayrıca doğrulanır.
- Sunucuya ilk çağrıda bağlanılır: Ollama kapalıyken de uygulama açılabilir,
  hata yalnızca soru sorulduğunda ve anlaşılır bir mesajla ortaya çıkar.
- Ollama'nın üç hata biçimi (bağlantı, HTTP hatası, zaman aşımı) tek tip
  hatalara çevrilir; ham httpx/ollama istisnaları üst katmana sızmaz.
"""

import json
from typing import Any

import httpx
from ollama import Client, ResponseError

from app.core.exceptions import LlmResponseError, LlmUnavailableError
from app.interfaces.llm_provider import LlmProvider


class OllamaLlmProvider(LlmProvider):
    def __init__(
        self,
        model: str = "qwen3:4b-instruct",
        host: str = "http://localhost:11434",
        temperature: float = 0.1,
        num_ctx: int = 8192,
        timeout_seconds: float = 120.0,
        client: Client | None = None,
    ) -> None:
        self._model = model
        self._host = host
        self._options = {"temperature": temperature, "num_ctx": num_ctx}
        self._client = client or Client(host=host, timeout=timeout_seconds)

    @property
    def model_name(self) -> str:
        return self._model

    def generate_json(self, system_prompt: str, user_prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format=schema,
                options=self._options,
            )
        except ConnectionError as exc:
            raise LlmUnavailableError(
                f"Ollama'ya bağlanılamadı ({self._host}). Ollama'nın çalıştığından emin olun "
                "(Windows'ta Ollama uygulamasını açın veya `ollama serve`)."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LlmUnavailableError(
                "Ollama zamanında cevap vermedi. Model ilk kez yükleniyor olabilir; tekrar deneyin."
            ) from exc
        except ResponseError as exc:
            if exc.status_code == 404:
                raise LlmUnavailableError(
                    f"'{self._model}' modeli Ollama'da yüklü değil. Yüklemek için: ollama pull {self._model}"
                ) from exc
            raise LlmUnavailableError(f"Ollama hata döndürdü: {exc.error}") from exc

        content = (response.message.content or "").strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmResponseError(f"Model geçerli JSON döndürmedi: {content[:200]!r}") from exc
        if not isinstance(data, dict):
            raise LlmResponseError(f"Model JSON nesnesi yerine {type(data).__name__} döndürdü.")
        return data
