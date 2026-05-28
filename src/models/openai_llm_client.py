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

    # ─────────────────────────────────────────────────────────────────
    # Agentic tool-loop (OpenAI tool-calling poverh llama-server --jinja)
    # ─────────────────────────────────────────────────────────────────

    def chat_with_tools(
        self,
        messages: list,
        tools: list,
        tool_executor: Callable[[str, dict], str],
        thinking: bool = True,
        max_rounds: int = 5,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[Tuple[str, str], None, None]:
        """Full OpenAI tool-loop: model decides → we execute → repeat.

        Yields tuples ("thinking" | "content", text):
          * "thinking" — model reasoning AND human-readable tool-call/result lines
          * "content"  — final assistant message (after no more tool_calls)

        Args:
          messages: full chat history as list of {"role","content"} (and optionally
                    "tool_calls" / "tool_call_id" for the agent's own turns).
          tools: OpenAI-format tool definitions
                 ([{"type":"function","function":{"name","description","parameters"}}]).
          tool_executor: (name, args_dict) -> str. The string is fed back as the
                         tool message content. Should never raise — wrap your own.
          max_rounds: safety net to break runaway loops (default 5).
        """
        msgs: list = list(messages)
        for round_idx in range(max_rounds):
            body: dict = {
                "model": self.model,
                "messages": msgs,
                "stream": False,
                "tools": tools,
                "chat_template_kwargs": {"enable_thinking": bool(thinking)},
                **DEFAULT_SAMPLING,
            }
            if temperature is not None:
                body["temperature"] = temperature
            if max_tokens is not None:
                body["max_tokens"] = max_tokens

            r = requests.post(self.chat_url, json=body, timeout=(30, 600))
            r.raise_for_status()
            resp = r.json()
            try:
                msg = resp["choices"][0]["message"]
            except (KeyError, IndexError):
                logger.warning("chat_with_tools_unexpected_response", body=resp)
                yield ("content", "(модель вернула пустой ответ)")
                return

            reasoning = msg.get("reasoning_content") or ""
            if reasoning:
                yield ("thinking", reasoning)

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                # Final assistant turn — no more tools needed.
                yield ("content", msg.get("content") or "")
                return

            # Has tool_calls — record the assistant turn (with its tool_calls)
            # before executing, so the next round sees the full history.
            msgs.append(
                {
                    "role": "assistant",
                    "content": msg.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )

            for tc in tool_calls:
                tc_id = tc.get("id") or f"call_{round_idx}_{len(msgs)}"
                fn = tc.get("function") or {}
                fn_name = fn.get("name") or ""
                try:
                    fn_args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                # Human-readable trace into the thinking stream.
                args_preview = json.dumps(fn_args, ensure_ascii=False)
                if len(args_preview) > 240:
                    args_preview = args_preview[:240] + "…"
                yield ("thinking", f"\n→ {fn_name}({args_preview})\n")

                try:
                    result_text = tool_executor(fn_name, fn_args) or ""
                except Exception as e:  # executor errors must not break the loop
                    logger.exception("tool_executor_error", name=fn_name)
                    result_text = json.dumps({"error": str(e)}, ensure_ascii=False)

                # Short preview for the panel; full text goes to the model.
                preview = result_text if len(result_text) <= 400 else result_text[:400] + "…"
                yield ("thinking", f"← {preview}\n")

                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": result_text,
                    }
                )

        # Safety: hit the round cap without finishing.
        yield ("content", "(достигнут лимит вызовов инструментов)")
