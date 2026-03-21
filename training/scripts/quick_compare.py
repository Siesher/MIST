"""Quick comparison: GSPO vs base — math accuracy + Socratic quality."""

import re
import sys
import time

import requests

sys.stdout.reconfigure(encoding="utf-8")

OLLAMA = "http://localhost:11434/api/chat"
SYSTEM_MATH = r"Ты репетитор по STEM. Реши задачу пошагово и запиши финальный ответ в \boxed{}."
SYSTEM_SOCRATIC = (
    "Ты - сократический репетитор. Помогай студентам находить решения через наводящие вопросы.\n"
    "ПРИНЦИПЫ:\n1. НИКОГДА не давай готовых ответов\n2. Задавай ОДИН вопрос за раз\n"
    "ФОРМАТ ОТВЕТА в JSON:\n"
    '{"move": "scaffolding|hint|tell", "message": "ответ на русском", "reasoning": "обоснование"}'
)

MATH_PROBLEMS = [
    ("2x + 3 = 11", "4", "linear"),
    ("x^2 - 5x + 6 = 0, найди сумму корней", "5", "quadratic"),
    ("Производная sin(3x)", "3cos(3x)", "derivative"),
    ("log_2(8)", "3", "log"),
    ("3! + 4!", "30", "combinatorics"),
    ("lim (x->0) sin(x)/x", "1", "limit"),
    ("Сумма арифметической прогрессии 1+2+...+100", "5050", "series"),
    ("Сколько будет 17 * 23", "391", "arithmetic"),
    ("Решите: 2^x = 32", "5", "exponential"),
    ("Найди площадь треугольника со сторонами 3, 4, 5", "6", "geometry"),
]

SOCRATIC_SCENARIOS = [
    (
        "scaffolding",
        "ЗАДАЧА: x^2 - 7x + 12 = 0\nСТУДЕНТ: Я не знаю как начать\nСТРАТЕГИЯ: scaffolding\nОтветь в JSON.",
    ),
    (
        "rectify",
        "ЗАДАЧА: Найди производную f(x) = x^3 * sin(x)\nСТУДЕНТ: f'(x) = 3x^2 * cos(x)\nСТРАТЕГИЯ: rectify\nОтветь в JSON.",
    ),
    (
        "hint",
        "ЗАДАЧА: Вычислить интеграл int(x*e^x dx)\nСТУДЕНТ: Не помню какой метод использовать\nСТРАТЕГИЯ: hint\nОтветь в JSON.",
    ),
]


def extract_boxed(text: str):
    if "</think>" in text:
        text = text.split("</think>")[-1]
    for pattern in [r"\\boxed\{([^}]+)\}", r"boxed\{([^}]+)\}"]:
        matches = re.findall(pattern, text)
        if matches:
            return matches[-1].strip()
    return None


def normalize(s: str) -> str:
    """Normalize answer for comparison: strip LaTeX commands, spaces, braces."""
    s = re.sub(r"\\(cos|sin|tan|ln|log|pi|sqrt|frac|cdot|times)", r"\1", s)
    s = re.sub(r"[\\{}\s]", "", s)
    return s.lower()


def check_answer(extracted, truth) -> bool:
    if not extracted:
        return False
    e = normalize(extracted)
    t = normalize(truth)
    if t in e or e == t:
        return True
    try:
        if abs(float(e) - float(t)) < 0.01:
            return True
    except ValueError:
        pass
    return False


def check_socratic(content: str) -> dict:
    """Evaluate Socratic quality of response."""
    has_json_move = '"move"' in content
    has_question = "?" in content
    # Check if model leaks the answer
    leak_patterns = [
        r"\\boxed",
        r"ответ\s*[:=]",
        r"x\s*=\s*\d",
        r"= [34]\b",
        r"3x\^2.*cos",
        r"формула",
    ]
    leaks_answer = any(re.search(p, content, re.IGNORECASE) for p in leak_patterns)
    return {
        "json_format": has_json_move,
        "has_question": has_question,
        "leaks_answer": leaks_answer,
    }


def call_ollama(model: str, system: str, user: str, think: bool = True, timeout: int = 300) -> dict:
    resp = requests.post(
        OLLAMA,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 2048, "num_ctx": 4096},
            "think": think,
        },
        timeout=timeout,
    )
    return resp.json()


MODELS = ["mits-tutor-9b-gspo", "qwen3.5:9b"]

# ═══════════════════════════════════════════════════════════
# Part 1: Math Accuracy (with thinking)
# ═══════════════════════════════════════════════════════════
print("=" * 60)
print("PART 1: MATH ACCURACY (thinking=True, \\boxed{} prompt)")
print("=" * 60)

math_results = {}
for model in MODELS:
    correct = 0
    boxed_count = 0
    total_time = 0.0
    print(f"\n=== {model} ===")
    for prompt, truth, topic in MATH_PROBLEMS:
        t0 = time.time()
        data = call_ollama(model, SYSTEM_MATH, prompt, think=True, timeout=600)
        elapsed = time.time() - t0
        total_time += elapsed

        if "error" in data:
            print(f"  [ERROR] {topic}: {data['error']}")
            continue

        content = data.get("message", {}).get("content", "")
        thinking = data.get("message", {}).get("thinking", "")
        extracted = extract_boxed(content)
        if extracted:
            boxed_count += 1
        ok = check_answer(extracted, truth)
        if ok:
            correct += 1
        tag = "OK" if ok else "WRONG"
        print(f"  [{tag}] {topic}: extracted={extracted}, truth={truth} ({elapsed:.1f}s)")

    pct = correct / len(MATH_PROBLEMS) * 100
    avg_time = total_time / len(MATH_PROBLEMS)
    print(f"  Score: {correct}/{len(MATH_PROBLEMS)} ({pct:.0f}%)")
    print(f"  Boxed: {boxed_count}/{len(MATH_PROBLEMS)}")
    print(f"  Avg time: {avg_time:.1f}s/problem")
    math_results[model] = {"correct": correct, "boxed": boxed_count, "avg_time": avg_time}

# ═══════════════════════════════════════════════════════════
# Part 2: Socratic Quality (no thinking)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PART 2: SOCRATIC QUALITY (thinking=False, tutor prompt)")
print("=" * 60)

socratic_results = {}
for model in MODELS:
    json_ok = 0
    question_ok = 0
    leak_count = 0
    print(f"\n=== {model} ===")
    for name, user_prompt in SOCRATIC_SCENARIOS:
        data = call_ollama(model, SYSTEM_SOCRATIC, user_prompt, think=False, timeout=300)
        content = data.get("message", {}).get("content", "")
        quality = check_socratic(content)
        if quality["json_format"]:
            json_ok += 1
        if quality["has_question"]:
            question_ok += 1
        if quality["leaks_answer"]:
            leak_count += 1
        status = []
        if quality["json_format"]:
            status.append("JSON-ok")
        if quality["has_question"]:
            status.append("has-?")
        if quality["leaks_answer"]:
            status.append("LEAKS!")
        print(f"  [{', '.join(status)}] {name}")
        print(f"    {content[:200]}")
        print()

    n = len(SOCRATIC_SCENARIOS)
    socratic_results[model] = {
        "json_format": json_ok,
        "questions": question_ok,
        "leaks": leak_count,
    }
    print(
        f"  JSON format: {json_ok}/{n}, Questions: {question_ok}/{n}, Leaks answer: {leak_count}/{n}"
    )

# ═══════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
for model in MODELS:
    m = math_results[model]
    s = socratic_results[model]
    print(f"\n{model}:")
    print(
        f"  Math: {m['correct']}/10 ({m['correct'] * 10}%), boxed={m['boxed']}/10, avg={m['avg_time']:.1f}s"
    )
    print(
        f"  Socratic: JSON={s['json_format']}/3, Questions={s['questions']}/3, Leaks={s['leaks']}/3"
    )
