"""
Tests for LLMClient.chat_with_tools().

Uses mocked Ollama client to test the tool execution loop
without requiring a running Ollama instance.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.models.llm_client import LLMClient

# ── Helpers ──────────────────────────────────────────────────────

def make_text_response(content: str):
    """Create a mock Ollama response with text content (no tool calls)."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None
    resp = MagicMock()
    resp.message = msg
    return resp


def make_tool_call_response(fn_name: str, fn_args: dict):
    """Create a mock Ollama response with a tool call."""
    tc = MagicMock()
    tc.function.name = fn_name
    tc.function.arguments = fn_args

    msg = MagicMock()
    msg.content = ""
    msg.tool_calls = [tc]
    resp = MagicMock()
    resp.message = msg
    return resp


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def llm():
    """Create LLMClient with mocked Ollama."""
    with patch("src.models.llm_client.ollama.Client") as MockClient:
        mock_client = MockClient.return_value
        # Mock list() so model resolution works
        mock_list = MagicMock()
        mock_list.models = [MagicMock(model="qwen3.5:9b")]
        mock_client.list.return_value = mock_list

        client = LLMClient(model="qwen3.5:9b")
        client.client = mock_client
        yield client


@pytest.fixture
def simple_tools():
    """Simple tool definitions for testing."""
    return [
        {
            "type": "function",
            "function": {
                "name": "add",
                "description": "Add two numbers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                },
            },
        }
    ]


@pytest.fixture
def simple_functions():
    """Simple tool implementations for testing."""
    return {
        "add": lambda a, b: json.dumps({"result": a + b}),
    }


# ── Tests ────────────────────────────────────────────────────────

class TestChatWithToolsNoToolCall:
    """Model responds with text directly (no tool use)."""

    def test_returns_content(self, llm, simple_tools, simple_functions):
        llm.client.chat.return_value = make_text_response("The answer is 42")

        result = llm.chat_with_tools(
            messages=[{"role": "user", "content": "What is 2+2?"}],
            tools=simple_tools,
            available_functions=simple_functions,
        )

        assert result["content"] == "The answer is 42"
        assert result["tool_calls_made"] == []
        assert result["thinking"] == ""

    def test_calls_ollama_with_tools(self, llm, simple_tools, simple_functions):
        llm.client.chat.return_value = make_text_response("Hi")

        llm.chat_with_tools(
            messages=[{"role": "user", "content": "Hi"}],
            tools=simple_tools,
            available_functions=simple_functions,
        )

        call_kwargs = llm.client.chat.call_args
        assert call_kwargs.kwargs.get("tools") == simple_tools


class TestChatWithToolsSingleRound:
    """Model calls a tool once, then responds with text."""

    def test_executes_tool_and_returns(self, llm, simple_tools, simple_functions):
        # Round 1: model calls add(2, 3)
        # Round 2: model responds with text
        llm.client.chat.side_effect = [
            make_tool_call_response("add", {"a": 2, "b": 3}),
            make_text_response("2 + 3 = 5"),
        ]

        result = llm.chat_with_tools(
            messages=[{"role": "user", "content": "What is 2+3?"}],
            tools=simple_tools,
            available_functions=simple_functions,
        )

        assert result["content"] == "2 + 3 = 5"
        assert len(result["tool_calls_made"]) == 1
        assert result["tool_calls_made"][0]["function"] == "add"
        assert result["tool_calls_made"][0]["arguments"] == {"a": 2, "b": 3}

    def test_tool_result_appended_to_messages(self, llm, simple_tools, simple_functions):
        llm.client.chat.side_effect = [
            make_tool_call_response("add", {"a": 1, "b": 1}),
            make_text_response("Done"),
        ]

        llm.chat_with_tools(
            messages=[{"role": "user", "content": "1+1"}],
            tools=simple_tools,
            available_functions=simple_functions,
        )

        # Second call should include tool result in messages
        second_call = llm.client.chat.call_args_list[1]
        messages = second_call.kwargs.get("messages") or second_call[1].get("messages", [])
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert '"result": 2' in tool_msgs[0]["content"]


class TestChatWithToolsErrorHandling:
    """Edge cases and error handling."""

    def test_unknown_function(self, llm, simple_tools, simple_functions):
        llm.client.chat.side_effect = [
            make_tool_call_response("unknown_fn", {}),
            make_text_response("Fallback response"),
        ]

        result = llm.chat_with_tools(
            messages=[{"role": "user", "content": "test"}],
            tools=simple_tools,
            available_functions=simple_functions,
        )

        assert result["content"] == "Fallback response"
        assert "error" in result["tool_calls_made"][0]["result"]

    def test_tool_execution_error(self, llm, simple_tools):
        def broken_add(**kwargs):
            raise ValueError("division by zero")

        llm.client.chat.side_effect = [
            make_tool_call_response("add", {"a": 1, "b": 0}),
            make_text_response("Error occurred"),
        ]

        result = llm.chat_with_tools(
            messages=[{"role": "user", "content": "test"}],
            tools=simple_tools,
            available_functions={"add": broken_add},
        )

        assert result["content"] == "Error occurred"
        assert "division by zero" in result["tool_calls_made"][0]["result"]

    def test_max_rounds_exhausted(self, llm, simple_tools, simple_functions):
        # Model keeps calling tools forever
        llm.client.chat.return_value = make_tool_call_response("add", {"a": 1, "b": 1})

        result = llm.chat_with_tools(
            messages=[{"role": "user", "content": "loop"}],
            tools=simple_tools,
            available_functions=simple_functions,
            max_tool_rounds=2,
        )

        assert result["content"] == ""
        assert len(result["tool_calls_made"]) >= 2

    def test_strips_think_prefix_for_qwen(self, llm, simple_tools, simple_functions):
        llm.client.chat.return_value = make_text_response("OK")

        llm.chat_with_tools(
            messages=[
                {"role": "user", "content": "/think\nWhat is 2+2?"},
            ],
            tools=simple_tools,
            available_functions=simple_functions,
        )

        call_kwargs = llm.client.chat.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages", [])
        user_msg = [m for m in messages if m["role"] == "user"][0]
        assert "/think" not in user_msg["content"]


class TestChatWithToolsMultiRound:
    """Model calls tools multiple times before responding."""

    def test_two_sequential_tool_calls(self, llm, simple_tools, simple_functions):
        llm.client.chat.side_effect = [
            make_tool_call_response("add", {"a": 1, "b": 2}),
            make_tool_call_response("add", {"a": 3, "b": 4}),
            make_text_response("1+2=3, 3+4=7"),
        ]

        result = llm.chat_with_tools(
            messages=[{"role": "user", "content": "Calculate 1+2 and 3+4"}],
            tools=simple_tools,
            available_functions=simple_functions,
            max_tool_rounds=3,
        )

        assert result["content"] == "1+2=3, 3+4=7"
        assert len(result["tool_calls_made"]) == 2
