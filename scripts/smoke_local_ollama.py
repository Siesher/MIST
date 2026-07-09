"""Smoke test для locally registered Ollama models — UTF-8 safe via Python.

Tests:
  - mits-eval-base через /api/chat
  - 2-3 calc problems с identical eval params (matches Colab DECODING_CONFIG)
  - Verify: thinking field, content, tokens count, tok/s
"""
import io
import sys
import time

import requests

# Force UTF-8 stdout — Windows default cp1251 cannot encode Russian Cyrillic в print().
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT = "Ты — репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \\boxed{}."

PROBLEMS = [
    {
        "id": "easy_wave",
        "prompt": "Длина волны равна 2 метра, а частота равна 50 Гц. Какова скорость этой волны?",
        "truth": 100,
    },
    {
        "id": "medium_combo",
        "prompt": "В школе 15 учеников. Из них необходимо выбрать 3 человек для участия в математической олимпиаде. Сколько существует разных комбинаций для выбора трёх участников из 15?",
        "truth": 455,
    },
]


def call_ollama(model: str, problem: dict) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": problem["prompt"]},
        ],
        "stream": False,
        "options": {
            "num_predict": 2048,
            "temperature": 0,
            "top_k": 1,
            "top_p": 1.0,
        },
    }
    t0 = time.time()
    r = requests.post(OLLAMA_URL, json=body, timeout=600)
    r.raise_for_status()
    elapsed = time.time() - t0
    data = r.json()
    return {
        "elapsed": elapsed,
        "tokens": data.get("eval_count", 0),
        "done_reason": data.get("done_reason"),
        "thinking": data.get("message", {}).get("thinking", ""),
        "content": data.get("message", {}).get("content", ""),
    }


def main(model: str = "mits-eval-base") -> None:
    print(f"=== Smoke test: {model} ===\n")
    for i, p in enumerate(PROBLEMS, 1):
        print(f"--- Problem {i}: {p['id']} (truth={p['truth']}) ---")
        print(f"Q: {p['prompt'][:120]}{'...' if len(p['prompt']) > 120 else ''}")
        try:
            r = call_ollama(model, p)
        except Exception as e:
            print(f"ERROR: {e}\n")
            continue

        tokps = r["tokens"] / max(r["elapsed"], 0.01)
        print(f"Time: {r['elapsed']:.1f}s | tokens: {r['tokens']} | tok/s: {tokps:.1f}")
        print(f"done_reason: {r['done_reason']}")
        print(f"thinking len: {len(r['thinking'])} | content len: {len(r['content'])}")

        if r["thinking"]:
            tk = r["thinking"][:300]
            print(f"\n[Thinking first 300 chars]:\n{tk}")
        if r["content"]:
            ct = r["content"][:500]
            print(f"\n[Content first 500 chars]:\n{ct}")

        boxed = "\\boxed{" in r["content"]
        print(f"\nHas \\boxed{{}}: {boxed}")
        print()


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "mits-eval-base")
