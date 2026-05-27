"""OpenAI-совместимый LLM-клиент для llama-server / llama-swap (:8090).

Реализует контракт src/models/llm_client.LLMClient в части chat-режима:
- generate() — one-shot;
- generate_stream() — yield ("thinking"|"content", token), как у LLMClient;
- check_connection(), list_models().

SSE-логика портирована из scripts/eval_local_llamaserver.py::call_llama_server_stream (DRY):
delta.content → ("content", ...), delta.reasoning_content → ("thinking", ...),
thinking-режим через chat_template_kwargs.enable_thinking (нужен --jinja у llama-server).
"""

from __future__ import annotations

import json
from typing import Callable, Generator, List, Optional, Tuple

import requests
import structlog

logger = structlog.get_logger()

# Дефолтный сэмплинг под Qwen3.5 (как в eval-стеке: temp/top_p/top_k/min_p; DRY — серверный)
DEFAULT_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0}


def parse_sse_line(raw_line: bytes) -> List[Tuple[str, str]]:
    """Разобрать одну SSE-строку OpenAI-стрима → список ("thinking"|"content", token).

    Пустые строки, не-data строки и [DONE] → []. Чистая функция (без сети/конфига),
    поэтому тестируется без поднятого backend/сервера.
    """
    if not raw_line:
        return []
    s = raw_line.decode("utf-8", errors="replace").strip()
    if not s.startswith("data: "):
        return []
    payload = s[6:]
    if payload == "[DONE]":
        return []
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return []
    choices = chunk.get("choices") or []
    if not choices:
        return []
    delta = choices[0].get("delta", {}) or {}
    out: List[Tuple[str, str]] = []
    if delta.get("reasoning_content"):
        out.append(("thinking", delta["reasoning_content"]))
    if delta.get("content"):
        out.append(("content", delta["content"]))
    return out


class OpenAICompatLLMClient:
    """LLM-клиент к OpenAI-совместимому endpoint (llama-swap/llama-server)."""

    def __init__(self, model: str = None, base_url: str = None, **_):
        # Ленивый импорт: модуль (и parse_sse_line) импортируется в unit-тестах без backend.
        from backend.app.config import backend_settings

        self.model = model or backend_settings.LLM_MODEL
        self.base_url = (base_url or backend_settings.LLM_BASE_URL).rstrip("/")
        self.chat_url = f"{self.base_url}/chat/completions"
        logger.info("openai_llm_client_initialized", model=self.model, base_url=self.base_url)

    def list_models(self) -> List[str]:
        try:
            r = requests.get(f"{self.base_url}/models", timeout=5)
            r.raise_for_status()
            return [m.get("id", "") for m in r.json().get("data", [])]
        except requests.RequestException:
            return []

    def check_connection(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/models", timeout=5).ok
        except requests.RequestException:
            return False

    def _body(self, messages: list, thinking, stream: bool, temperature, max_tokens) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "chat_template_kwargs": {"enable_thinking": bool(thinking)},
            **DEFAULT_SAMPLING,
        }
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        return body

    @staticmethod
    def _messages(prompt: str, system: Optional[str]) -> list:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        thinking: bool = None,
        temperature: float = None,
        max_tokens: int = None,
        **_,
    ) -> str:
        body = self._body(self._messages(prompt, system), thinking, False, temperature, max_tokens)
        r = requests.post(self.chat_url, json=body, timeout=(30, 600))
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        thinking: bool = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        **kwargs,
    ) -> Generator[Tuple[str, str], None, None]:
        body = self._body(
            self._messages(prompt, system),
            thinking,
            True,
            kwargs.get("temperature"),
            kwargs.get("max_tokens"),
        )
        with requests.post(self.chat_url, json=body, stream=True, timeout=(30, 120)) as r:
            r.raise_for_status()
            for raw_line in r.iter_lines(decode_unicode=False):
                for kind, tok in parse_sse_line(raw_line):
                    if kind == "thinking" and on_thinking:
                        on_thinking(tok)
                    elif kind == "content" and on_token:
                        on_token(tok)
                    yield (kind, tok)
