"""Quick E2E test: LLM + native tool calling + SKI."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.llm_client import LLMClient
from src.tools.ski_tools import SKI_TOOL_DEFINITIONS, SKI_FUNCTIONS

llm = LLMClient(model="qwen3.5:9b")

print("=== Test 1: Formulas query (expect get_formula tool) ===")
result = llm.chat_with_tools(
    messages=[
        {"role": "system", "content": "Ты репетитор. Используй инструменты для поиска информации перед ответом."},
        {"role": "user", "content": "Какие формулы нужны для производных?"},
    ],
    tools=SKI_TOOL_DEFINITIONS,
    available_functions=SKI_FUNCTIONS,
)
print(f"Tools used: {[tc['function'] for tc in result['tool_calls_made']]}")
print(f"Response: {result['content'][:400]}")
print()

print("=== Test 2: Concept query (expect lookup_concept tool) ===")
result2 = llm.chat_with_tools(
    messages=[
        {"role": "system", "content": "Ты репетитор. Используй инструменты для поиска информации перед ответом."},
        {"role": "user", "content": "Что такое квадратное уравнение и какие ошибки делают студенты?"},
    ],
    tools=SKI_TOOL_DEFINITIONS,
    available_functions=SKI_FUNCTIONS,
)
print(f"Tools used: {[tc['function'] for tc in result2['tool_calls_made']]}")
print(f"Response: {result2['content'][:400]}")
print()

print("=== Test 3: No tools needed (simple greeting) ===")
result3 = llm.chat_with_tools(
    messages=[
        {"role": "system", "content": "Ты репетитор. Используй инструменты для поиска информации перед ответом."},
        {"role": "user", "content": "Привет! Как дела?"},
    ],
    tools=SKI_TOOL_DEFINITIONS,
    available_functions=SKI_FUNCTIONS,
)
print(f"Tools used: {[tc['function'] for tc in result3['tool_calls_made']]}")
print(f"Response: {result3['content'][:400]}")
