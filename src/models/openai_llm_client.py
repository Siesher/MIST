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


def parse_sse_chunk(raw_line: bytes) -> Optional[dict]:
    """SSE-строку → объект choices[0] ({"delta", "finish_reason", ...}) или None.

    Богаче parse_sse_line: сохраняет tool_calls и finish_reason — нужно tool-loop'у,
    который стримит content/reasoning И аккумулирует tool_calls по index. Чистая
    функция (без сети), поэтому тестируется без поднятого backend/сервера.
    """
    if not raw_line:
        return None
    s = raw_line.decode("utf-8", errors="replace").strip()
    if not s.startswith("data: "):
        return None
    payload = s[6:]
    if payload == "[DONE]":
        return None
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return None
    choices = chunk.get("choices") or []
    if not choices:
        return None
    return choices[0]


class OpenAICompatLLMClient:
    """LLM-клиент к OpenAI-совместимому endpoint (llama-swap/llama-server)."""

    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        api_key: str = None,
        send_template_kwargs: bool = None,
        **_,
    ):
        # Ленивый импорт настроек: parse_sse_line/parse_sse_chunk импортируются
        # в unit-тестах без конфига. Дефолты — из src.config (та же .env, что и
        # у backend/app/config.py): src/ не импортирует backend/ (слои).
        from src.config import get_settings

        settings = get_settings()
        self.model = model or settings.LLM_MODEL
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.chat_url = f"{self.base_url}/chat/completions"
        # Авторизация для внешних OpenAI-совместимых провайдеров; пусто = локальный llama-server.
        self.api_key = api_key if api_key is not None else settings.LLM_API_KEY
        # Слать ли llama.cpp/vLLM-специфичный chat_template_kwargs (см. config: часть
        # облачных провайдеров отвергает его как неизвестный параметр).
        self.send_template_kwargs = (
            send_template_kwargs if send_template_kwargs is not None else settings.LLM_SEND_TEMPLATE_KWARGS
        )
        logger.info(
            "openai_llm_client_initialized",
            model=self.model,
            base_url=self.base_url,
            auth=bool(self.api_key),
        )

    def _headers(self) -> dict:
        """HTTP-заголовки запроса: Bearer для внешних провайдеров, пусто для локального.

        Content-Type для json=-тела requests проставляет сам, поэтому здесь только
        авторизация. Пустой api_key (локальный llama-server) → без заголовков.
        """
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def list_models(self) -> List[str]:
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=5)
            r.raise_for_status()
            return [m.get("id", "") for m in r.json().get("data", [])]
        except requests.RequestException:
            return []

    def check_connection(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=5).ok
        except requests.RequestException:
            return False

    def _body(self, messages: list, thinking, stream: bool, temperature, max_tokens, json_mode: bool = False) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            **DEFAULT_SAMPLING,
        }
        if self.send_template_kwargs:
            body["chat_template_kwargs"] = {"enable_thinking": bool(thinking)}
        if json_mode:
            # Grammar-constrain llama-server to a valid JSON object, so strict-JSON
            # callers (e.g. TaskGenerator) don't have to salvage prose/fences from
            # the reply. enable_thinking is already off above for these calls.
            body["response_format"] = {"type": "json_object"}
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        elif json_mode:
            # Task JSON (problem + solution + hints + answer + common_mistakes) in
            # Cyrillic + LaTeX is token-heavy; 4096 truncated verbose tasks mid-object
            # (→ unterminated string → parse retry). 8192 is a ceiling, not a target —
            # short replies still stop early, so this only costs latency when needed.
            body["max_tokens"] = 8192
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
        json_mode: bool = False,
        **_,
    ) -> str:
        body = self._body(self._messages(prompt, system), thinking, False, temperature, max_tokens, json_mode=json_mode)
        return self._complete(body)

    def _complete(self, body: dict) -> str:
        """POST non-streaming chat/completions → content (общий путь generate/chat)."""
        r = requests.post(self.chat_url, json=body, headers=self._headers(), timeout=(30, 600))
        r.raise_for_status()
        try:
            content = r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as e:
            # llama-server может вернуть error-body без choices или message без
            # content (tool_calls-only) — иначе наружу летит голый KeyError
            logger.error("generate_response_parse_failed", error=str(e), body=r.text[:200])
            raise RuntimeError(f"Неожиданный формат ответа LLM-сервера: {e}") from e
        return content or ""

    def chat(self, messages: List[dict], **kwargs) -> str:
        """Диалог с историей — контракт BaseLLMClient.chat (парный к LLMClient.chat).

        thinking по умолчанию выключен: one-shot диалоговый вызов ждёт готовый
        текст, а не reasoning-канал.
        """
        body = self._body(
            list(messages),
            kwargs.get("thinking", False),
            False,
            kwargs.get("temperature"),
            kwargs.get("max_tokens"),
        )
        return self._complete(body)

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
        with requests.post(self.chat_url, json=body, headers=self._headers(), stream=True, timeout=(30, 120)) as r:
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
        max_rounds: int = 7,
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
        # Lower temp for tool-loop: stalls in reasoning_content are more frequent
        # at temp=1.0; 0.6 makes the "tool_call vs final answer" decision firmer.
        effective_temp = temperature if temperature is not None else 0.6
        tools_used = False  # flips true once we execute at least one tool

        for round_idx in range(max_rounds):
            body: dict = {
                "model": self.model,
                "messages": msgs,
                "stream": True,
                "tools": tools,
                **DEFAULT_SAMPLING,
                "temperature": effective_temp,
            }
            if self.send_template_kwargs:
                body["chat_template_kwargs"] = {"enable_thinking": bool(thinking)}
            if max_tokens is not None:
                body["max_tokens"] = max_tokens

            # Стримим раунд: reasoning/content дельты отдаём СРАЗУ (real-time чат),
            # а tool_calls аккумулируем по index до конца раунда. llama-server отдаёт
            # tool_calls дельтами с finish_reason="tool_calls" (проверено на :8090).
            reasoning_parts: List[str] = []
            content_streamed = False
            tc_acc: dict = {}  # index -> {"id","name","args"}

            with requests.post(self.chat_url, json=body, headers=self._headers(), stream=True, timeout=(30, 600)) as r:
                r.raise_for_status()
                for raw_line in r.iter_lines(decode_unicode=False):
                    choice = parse_sse_chunk(raw_line)
                    if not choice:
                        continue
                    delta = choice.get("delta") or {}
                    rc = delta.get("reasoning_content")
                    if rc:
                        reasoning_parts.append(rc)
                        yield ("thinking", rc)
                    ct = delta.get("content")
                    if ct:
                        content_streamed = True
                        yield ("content", ct)
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        acc = tc_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            acc["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            acc["name"] = fn["name"]
                        if fn.get("arguments"):
                            acc["args"] += fn["arguments"]

            reasoning = "".join(reasoning_parts).strip()
            # Реконструируем OpenAI tool_calls в стабильном порядке index.
            tool_calls = [
                {
                    "id": acc["id"] or f"call_{round_idx}_{idx}",
                    "type": "function",
                    "function": {"name": acc["name"], "arguments": acc["args"] or "{}"},
                }
                for idx, acc in sorted(tc_acc.items())
                if acc["name"]
            ]

            if not tool_calls:
                # Stall recovery: модель выдала reasoning + пустой content + ни одного
                # tool_call ПОСЛЕ того как мы уже звали инструменты — "подумала о повторе",
                # не выбрав ни tool_call, ни финальный ответ. Пнём и дадим ещё попытку.
                if not content_streamed and tools_used and reasoning and round_idx < max_rounds - 1:
                    yield ("thinking", "\n[stall — ре-промпт: tool либо финал]\n")
                    msgs.append({"role": "assistant", "content": reasoning})
                    msgs.append(
                        {
                            "role": "user",
                            "content": (
                                "Продолжи: либо ПОЗОВИ web_search ещё раз с другой "
                                "формулировкой (короче, без 'news', с конкретным "
                                "именем/датой), либо дай ИТОГОВЫЙ ответ пользователю "
                                "в обычном тексте на основе того, что уже нашёл."
                            ),
                        }
                    )
                    continue
                # Финальный ответ уже отстримлен дельтами выше. Если модель не выдала
                # видимого текста — отдаём маркер, чтобы UI не остался пустым.
                if not content_streamed:
                    yield ("content", "(модель вернула пустой ответ)")
                return

            # Есть tool_calls — записываем ход ассистента (с tool_calls) до выполнения,
            # чтобы следующий раунд видел полную историю.
            msgs.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
            tools_used = True

            for tc in tool_calls:
                tc_id = tc["id"]
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"] or "{}")
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

                msgs.append({"role": "tool", "tool_call_id": tc_id, "content": result_text})

        # Safety: hit the round cap without finishing.
        yield ("content", "(достигнут лимит вызовов инструментов)")
