"""Unit-тест разбора OpenAI SSE-стрима в ("thinking"/"content", token).

parse_sse_line — чистая функция, поэтому backend/сервер поднимать не нужно.
"""

from src.models.openai_llm_client import OpenAICompatLLMClient, parse_sse_line


def _client(**kwargs) -> OpenAICompatLLMClient:
    kwargs.setdefault("model", "test-model")
    kwargs.setdefault("base_url", "http://llm.test/v1")
    return OpenAICompatLLMClient(**kwargs)


def test_headers_bearer_when_api_key_set():
    """Внешний OpenAI-совместимый провайдер: уходит Authorization: Bearer <key>."""
    assert _client(api_key="sk-secret")._headers() == {"Authorization": "Bearer sk-secret"}


def test_headers_empty_for_local_server():
    """Локальный llama-server без ключа: заголовков авторизации нет."""
    assert _client(api_key="")._headers() == {}


def test_body_includes_template_kwargs_by_default():
    """llama.cpp-путь: chat_template_kwargs (enable_thinking) присутствует."""
    body = _client(api_key="")._body([{"role": "user", "content": "x"}], False, False, None, None)
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


def test_body_omits_template_kwargs_when_disabled():
    """Внешний провайдер (LLM_SEND_TEMPLATE_KWARGS=False): нестандартный параметр не шлём."""
    client = _client(api_key="sk-x")
    client.send_template_kwargs = False
    body = client._body([{"role": "user", "content": "x"}], True, False, None, None)
    assert "chat_template_kwargs" not in body


def test_parse_content_delta():
    line = b'data: {"choices":[{"delta":{"content":"Hello"}}]}'
    assert parse_sse_line(line) == [("content", "Hello")]


def test_parse_reasoning_delta():
    line = b'data: {"choices":[{"delta":{"reasoning_content":"hmm"}}]}'
    assert parse_sse_line(line) == [("thinking", "hmm")]


def test_parse_both_fields_order_thinking_then_content():
    line = b'data: {"choices":[{"delta":{"reasoning_content":"r","content":"c"}}]}'
    assert parse_sse_line(line) == [("thinking", "r"), ("content", "c")]


def test_parse_done_blank_and_garbage():
    assert parse_sse_line(b"") == []
    assert parse_sse_line(b"data: [DONE]") == []
    assert parse_sse_line(b": keep-alive comment") == []
    assert parse_sse_line(b"data: {not json}") == []
    assert parse_sse_line(b'data: {"choices":[]}') == []
