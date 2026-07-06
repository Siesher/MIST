"""Общий контракт LLM-клиентов: локальный Ollama / llama-server / внешние OpenAI-совместимые API.

BaseLLMClient — runtime_checkable Protocol (структурная типизация): клиенты НЕ
наследуются от него, соответствие проверяется по факту наличия методов —
`isinstance(client, BaseLLMClient)` в parity-тестах, подсказки типов в фабрике.

Контракт описывает РЕАЛЬНО используемую общую поверхность. Сознательно вне контракта:

- ``chat_with_tools``: контракты клиентов принципиально различаются
  (``LLMClient`` → ``Dict``, executor'ы через ``available_functions``;
  ``OpenAICompatLLMClient`` → генератор ``("thinking"|"content", token)``,
  ``tool_executor``). Агентный tool-loop живёт только на OpenAI-совместимом пути.
- ``chat_with_thinking`` / ``chat_stream`` / ``generate_stream_simple``:
  Ollama-специфичные extras ``LLMClient``, в кодовой базе не вызываются.
"""

from __future__ import annotations

from typing import Generator, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class BaseLLMClient(Protocol):
    """Минимальный общий контракт LLM-клиента.

    Сигнатуры намеренно свободные (``**kwargs``): реализации различаются
    набором опциональных параметров (json_mode, температуры, коллбэки),
    вызывающий код передаёт их keyword'ами.
    """

    def generate(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """One-shot генерация: prompt (+system) → готовый текст."""
        ...

    def generate_stream(
        self, prompt: str, system: Optional[str] = None, **kwargs
    ) -> Generator[Tuple[str, str], None, None]:
        """Стриминг: yield ("thinking" | "content", token)."""
        ...

    def chat(self, messages: List[dict], **kwargs) -> str:
        """Диалог с историей [{"role", "content"}, ...] → ответ ассистента."""
        ...

    def check_connection(self) -> bool:
        """Доступен ли LLM-сервер (healthcheck)."""
        ...

    def list_models(self) -> List[str]:
        """Имена моделей, доступных на сервере."""
        ...
