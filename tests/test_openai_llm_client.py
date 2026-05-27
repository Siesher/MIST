"""Unit-тест разбора OpenAI SSE-стрима в ("thinking"/"content", token).

parse_sse_line — чистая функция, поэтому backend/сервер поднимать не нужно.
"""

from src.models.openai_llm_client import parse_sse_line


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
