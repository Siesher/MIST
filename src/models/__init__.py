"""MITS Models Module — LLM-клиенты и единая фабрика выбора бэкенда."""

from typing import Optional

from src.models.base import BaseLLMClient
from src.models.llm_client import LLMClient
from src.models.openai_llm_client import OpenAICompatLLMClient


def create_llm_client(
    backend: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    """Единственная развилка выбора LLM-бэкенда.

    До неё выбор клиента был размазан копиями по кодовой базе и местами
    обходился (голый ``LLMClient()`` игнорировал ``LLM_BACKEND``) — копии
    неизбежно разъезжаются, поэтому развилка ровно одна.

    Args:
        backend: ``"llamacpp"`` — llama-server/llama-swap и любые внешние
            OpenAI-совместимые API (OpenRouter/DeepSeek/vLLM/...);
            ``"ollama"`` — legacy-путь через Ollama-native API.
            ``None`` → ``LLM_BACKEND`` из настроек (.env).
        model: Явный id модели; ``None`` → дефолт клиента из настроек.
        base_url: OpenAI-совместимый ``/v1`` endpoint (только llamacpp-путь).
        api_key: Bearer-ключ внешнего провайдера (только llamacpp-путь).
        **kwargs: Прочие параметры конструктора выбранного клиента.

    Returns:
        Клиент, удовлетворяющий контракту :class:`BaseLLMClient`.
    """
    if backend is None:
        from src.config import get_settings

        backend = get_settings().LLM_BACKEND
    if backend == "ollama":
        return LLMClient(model=model, **kwargs)
    # llamacpp и любые OpenAI-совместимые endpoint'ы: локальные и облачные.
    return OpenAICompatLLMClient(model=model, base_url=base_url, api_key=api_key, **kwargs)


__all__ = ["BaseLLMClient", "LLMClient", "OpenAICompatLLMClient", "create_llm_client"]
