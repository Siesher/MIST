"""Стриминг agentic tool-loop: chat_with_tools обязан отдавать content/thinking
по токенам (а не одним блобом) и слать stream=True. Регрессия: до фикса цикл
делал stream=False и yield-ил целые куски → реальный стриминг в чате пропадал.

Тесты гоняют замоканный SSE-стрим (без живого сервера) — мок отдаёт и iter_lines()
(стриминговый путь), и json() (старый путь), поэтому тест impl-agnostic: на старой
реализации он КРАСНЫЙ (1 content-токен + stream=False), на новой — зелёный.
"""

import json

import pytest

from src.models import openai_llm_client as mod
from src.models.openai_llm_client import OpenAICompatLLMClient


def _sse(delta=None, finish=None):
    payload = {"choices": [{"delta": delta or {}, "finish_reason": finish}]}
    return b"data: " + json.dumps(payload).encode("utf-8")


class _FakeResp:
    """Имитация requests-ответа: стриминговый iter_lines() + json() для старого пути."""

    def __init__(self, sse_lines, message):
        self._lines = sse_lines
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=False):
        return iter(self._lines)

    def json(self):
        return {"choices": [{"message": self._message}]}


def _round(reasoning=(), content=(), tool_calls=(), finish="stop"):
    """Собрать один раунд модели как SSE-строки + эквивалентный message.

    tool_calls: список (name, args_dict); аргументы режутся на 2 дельты,
    чтобы проверить аккумуляцию по index.
    """
    lines = []
    for rc in reasoning:
        lines.append(_sse({"reasoning_content": rc}))

    msg_tool_calls = []
    for i, (name, args) in enumerate(tool_calls):
        args_json = json.dumps(args)
        half = max(1, len(args_json) // 2)
        lines.append(
            _sse(
                {
                    "tool_calls": [
                        {
                            "index": i,
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {"name": name, "arguments": args_json[:half]},
                        }
                    ]
                }
            )
        )
        lines.append(
            _sse({"tool_calls": [{"index": i, "function": {"arguments": args_json[half:]}}]})
        )
        msg_tool_calls.append(
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": name, "arguments": args_json},
            }
        )

    for ct in content:
        lines.append(_sse({"content": ct}))
    lines.append(_sse({}, finish=finish))
    lines.append(b"data: [DONE]")

    message = {
        "role": "assistant",
        "content": "".join(content),
        "reasoning_content": "".join(reasoning),
    }
    if msg_tool_calls:
        message["tool_calls"] = msg_tool_calls
    return _FakeResp(lines, message)


@pytest.fixture
def client():
    return OpenAICompatLLMClient(model="test-model", base_url="http://test/v1")


def _patch_post(monkeypatch, responses):
    posted = []
    queue = list(responses)

    def fake_post(url, json=None, stream=False, timeout=None, **kw):
        posted.append({"url": url, "body": json, "stream_kw": stream})
        return queue.pop(0)

    monkeypatch.setattr(mod.requests, "post", fake_post)
    return posted


def test_streams_content_token_by_token(client, monkeypatch):
    posted = _patch_post(
        monkeypatch, [_round(reasoning=["дум", "аю"], content=["При", "вет", "!"])]
    )
    calls = []
    out = list(
        client.chat_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            tool_executor=lambda n, a: calls.append((n, a)) or "x",
        )
    )
    content = [t for k, t in out if k == "content"]
    thinking = [t for k, t in out if k == "thinking"]

    assert content == ["При", "вет", "!"], "final answer must stream token-by-token, not one blob"
    assert "дум" in thinking and "аю" in thinking, "reasoning must stream as thinking tokens"
    assert calls == [], "no tool should be called when none requested"
    assert posted[0]["body"]["stream"] is True, "the round request must be stream=True"


def test_executes_tool_then_streams_answer(client, monkeypatch):
    posted = _patch_post(
        monkeypatch,
        [
            _round(
                reasoning=["надо узнать"], tool_calls=[("get_x", {"a": 1})], finish="tool_calls"
            ),
            _round(content=["От", "вет"]),
        ],
    )
    calls = []

    def executor(name, args):
        calls.append((name, args))
        return "RESULT"

    out = list(
        client.chat_with_tools(
            messages=[{"role": "user", "content": "q"}],
            tools=[{"type": "function", "function": {"name": "get_x"}}],
            tool_executor=executor,
        )
    )
    content = [t for k, t in out if k == "content"]
    thinking = "".join(t for k, t in out if k == "thinking")

    assert calls == [("get_x", {"a": 1})], "streamed tool_call args must be accumulated and parsed"
    assert content == ["От", "вет"], "post-tool answer must stream token-by-token"
    assert "→ get_x" in thinking and "RESULT" in thinking, (
        "tool-call/result trace must reach thinking"
    )
    assert len(posted) == 2 and all(p["body"]["stream"] is True for p in posted)
