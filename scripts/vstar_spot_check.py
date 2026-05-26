"""V-STaR memorization spot-check.

Samples 20 problems из rl_combined.jsonl (balanced domains, skip-easy), runs them
through base model via llama-server, measures correctness. Если accuracy >80% на math
→ memorization risk. <60% per domain → V-STaR generation will produce diverse outcomes
(useful chosen-rejected pairs).

Usage:
  uv run python scripts/vstar_spot_check.py
"""

from __future__ import annotations

import io
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
RL_DATA = ROOT / "training/data/rl_combined.jsonl"
LLAMA_URL = "http://127.0.0.1:8081/v1/chat/completions"
MODEL = "mits-eval-base"  # base checkpoint — measure pre-training memorization

DOMAINS = ["math", "physics", "chemistry", "biology", "cs"]
DIFFICULTIES = ["medium", "hard"]  # skip-easy
N_PER_DOMAIN = 4  # 5 domains × 4 = 20 problems total

SYSTEM_PROMPT = (
    "Ты — репетитор по STEM. Реши задачу пошагово и запиши ОДИН финальный ответ в \\boxed{}."
)

random.seed(42)


def load_rl_combined() -> list[dict]:
    items = []
    with open(RL_DATA, "r", encoding="utf-8") as f:
        for line in f:
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return items


def stratified_sample(items: list[dict]) -> list[dict]:
    """Balanced sample: 4 per domain (2 medium + 2 hard where available)."""
    by_domain_diff = defaultdict(list)
    for item in items:
        d = item.get("domain")
        diff = item.get("difficulty")
        if d in DOMAINS and diff in DIFFICULTIES:
            by_domain_diff[(d, diff)].append(item)

    sample = []
    for d in DOMAINS:
        for diff in DIFFICULTIES:
            pool = by_domain_diff.get((d, diff), [])
            n = min(2, len(pool))
            if n > 0:
                sample.extend(random.sample(pool, n))
    return sample


def extract_answer(text: str) -> str:
    if "</think>" in text:
        text = text.split("</think>")[-1].strip()
    m = re.findall(r"\\boxed\{([^{}]+)\}", text)
    if m:
        s = m[-1].strip()
        s = re.sub(r"\\text\s*\{[^}]*\}?", "", s)
        return s.strip()
    nums = re.findall(r"[-+]?\d*\.?\d+", text[-300:])
    return nums[-1] if nums else ""


def normalize(s) -> str:
    if s is None:
        return ""
    s = str(s).strip().replace(",", ".").replace(" ", "")
    m = re.match(r"^[+-]?\d+(?:\.\d+)?", s)
    return m.group(0) if m else s


def is_correct(extracted, truth, tol: float = 0.02) -> bool | None:
    e, g = normalize(extracted), normalize(truth)
    if not e or not g:
        return None
    try:
        ef, gf = float(e), float(g)
        if abs(gf) < 1e-9:
            return abs(ef) < 0.001
        return abs(ef - gf) / abs(gf) < tol
    except ValueError:
        return e.lower() == g.lower()


def call_model(prompt: str) -> tuple[str, float]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.95,
        "seed": 42,
        "chat_template_kwargs": {"enable_thinking": True},
    }
    import time

    t0 = time.time()
    r = requests.post(LLAMA_URL, json=body, timeout=300)
    r.raise_for_status()
    data = r.json()
    elapsed = time.time() - t0
    msg = data.get("choices", [{}])[0].get("message", {})
    content = msg.get("content", "") or ""
    reasoning = msg.get("reasoning_content", "") or ""
    full = (reasoning + "\n" + content).strip()
    return full, elapsed


def main() -> None:
    print("[spot-check] Loading rl_combined.jsonl...")
    items = load_rl_combined()
    print(f"  Total items: {len(items)}")

    sample = stratified_sample(items)
    print(f"  Sampled: {len(sample)} problems\n")

    by_domain = defaultdict(lambda: {"correct": 0, "total": 0})
    results = []

    for i, item in enumerate(sample):
        prompt = item.get("prompt", "")
        truth = item.get("answer", "")
        d = item.get("domain")
        diff = item.get("difficulty")

        print(f"[{i + 1}/{len(sample)}] {d}/{diff} | truth={truth!r}")
        try:
            response, elapsed = call_model(prompt)
            extracted = extract_answer(response)
            correct = is_correct(extracted, truth)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append(
                {"domain": d, "diff": diff, "truth": truth, "extracted": "ERR", "correct": None}
            )
            continue

        ok_str = "✓" if correct else ("?" if correct is None else "✗")
        print(f"  {ok_str} extracted={extracted!r} | {elapsed:.1f}s")

        results.append(
            {
                "domain": d,
                "diff": diff,
                "truth": truth,
                "extracted": extracted,
                "correct": correct,
                "elapsed": elapsed,
            }
        )

        by_domain[d]["total"] += 1
        if correct:
            by_domain[d]["correct"] += 1

    print("\n=== SPOT-CHECK SUMMARY ===")
    print(f"{'Domain':<12} {'Correct':<10} {'Total':<8} {'Acc':<8}")
    print("-" * 50)
    for d in DOMAINS:
        stats = by_domain.get(d, {"correct": 0, "total": 0})
        c, t = stats["correct"], stats["total"]
        acc = c / max(t, 1)
        flag = ""
        if d == "math" and acc > 0.80:
            flag = " ⚠️ MEMORIZATION RISK"
        elif acc < 0.20:
            flag = " ⚠️ TOO HARD (no V-STaR signal)"
        print(f"{d:<12} {c:<10} {t:<8} {acc:.3f}{flag}")

    # Diagnostic
    total_correct = sum(s["correct"] for s in by_domain.values())
    total = sum(s["total"] for s in by_domain.values())
    print(f"\nOverall: {total_correct}/{total} = {total_correct / max(total, 1):.3f}")

    print("\nDecision rule:")
    print("  >80% math accuracy → memorization, consider raw_stem_clean alternative")
    print("  20-70% per domain → ideal V-STaR generation regime (diverse outcomes)")
    print("  <20% per domain → too hard, no signal (rare)")


if __name__ == "__main__":
    main()
