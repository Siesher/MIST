#!/usr/bin/env python3
"""
Generate SimPO preference pairs from the STEM dataset.

Strategy: For each prompt, create (chosen, rejected) pairs where:
  - Chosen: Socratic response (guiding questions, step-by-step scaffolding)
  - Rejected: Direct answer without pedagogical scaffolding

Uses Cerebras API (async) with multi-model support to generate both variants.

Usage:
    python training/scripts/generate_preference_pairs.py
    python training/scripts/generate_preference_pairs.py --workers 30 --target 10000
    python training/scripts/generate_preference_pairs.py --resume
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

# ─── Configuration ───

CEREBRAS_MODELS = [
    "llama-3.3-70b",
    "llama3.1-8b",
    "qwen-3-32b",
]

DOMAIN_TARGETS = {
    "math": 2000,
    "physics": 2000,
    "chemistry": 1500,
    "cs": 1500,
    "biology": 1500,
    "mixed": 1500,
}

SYSTEM_SOCRATIC = """Ты — опытный сократический репетитор. Вместо того чтобы давать прямой ответ, ты:
1. Задаёшь наводящие вопросы, помогающие студенту самому прийти к ответу
2. Разбиваешь сложную задачу на простые шаги
3. Поощряешь самостоятельное мышление
4. Даёшь подсказки, но не решение
Отвечай на русском языке."""

SYSTEM_DIRECT = """Ты — помощник, который даёт прямые и полные ответы на вопросы.
Сразу предоставь готовое решение без наводящих вопросов.
Отвечай на русском языке."""

OUTPUT_PATH = "training/data/preference_pairs.jsonl"


# ─── Rate limiter (simplified) ───

class SimpleRateLimiter:
    """Track per-minute rate with a sliding window."""

    def __init__(self, rpm=30):
        self.rpm = rpm
        self.timestamps = []

    def available(self) -> bool:
        now = time.time()
        self.timestamps = [t for t in self.timestamps if now - t < 60]
        return len(self.timestamps) < self.rpm

    def record(self):
        self.timestamps.append(time.time())

    def wait_time(self) -> float:
        if self.available():
            return 0.0
        return 60.0 - (time.time() - self.timestamps[0]) + 0.1


class AsyncPreferenceClient:
    """Multi-key multi-model async client for preference pair generation."""

    def __init__(self):
        self.api_keys = []
        for i in range(1, 20):
            key = os.environ.get(f"CEREBRAS_API_KEY_{i}")
            if key:
                self.api_keys.append(key)

        # Fallback to single key
        if not self.api_keys:
            single = os.environ.get("CEREBRAS_API_KEY")
            if single:
                self.api_keys.append(single)

        if not self.api_keys:
            raise RuntimeError("No CEREBRAS_API_KEY_* environment variables found")

        print(f"Loaded {len(self.api_keys)} API keys × {len(CEREBRAS_MODELS)} models = {len(self.api_keys) * len(CEREBRAS_MODELS)} slots")

        self.clients = [
            AsyncOpenAI(api_key=k, base_url="https://api.cerebras.ai/v1")
            for k in self.api_keys
        ]
        self.limiters = {
            (ki, m): SimpleRateLimiter(rpm=28)
            for ki in range(len(self.api_keys))
            for m in CEREBRAS_MODELS
        }
        self._lock = asyncio.Lock()
        self.stats = Counter()

    async def acquire_slot(self):
        """Find an available (client, model) slot."""
        async with self._lock:
            for ki in range(len(self.clients)):
                for model in CEREBRAS_MODELS:
                    limiter = self.limiters[(ki, model)]
                    if limiter.available():
                        limiter.record()
                        return self.clients[ki], model
        return None, None

    async def generate(self, messages, max_tokens=1500):
        """Generate a completion, retrying with backoff."""
        for attempt in range(5):
            client, model = await self.acquire_slot()
            if client is None:
                await asyncio.sleep(2.0)
                continue

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
                self.stats[model] += 1
                return response.choices[0].message.content, model
            except Exception as e:
                if "rate" in str(e).lower() or "429" in str(e):
                    await asyncio.sleep(5.0)
                else:
                    await asyncio.sleep(1.0)

        return None, None


async def generate_pair(client: AsyncPreferenceClient, instruction: str, domain: str):
    """Generate a (chosen, rejected) preference pair."""
    # Generate Socratic (chosen) response
    chosen_messages = [
        {"role": "system", "content": SYSTEM_SOCRATIC},
        {"role": "user", "content": instruction},
    ]
    chosen_text, chosen_model = await client.generate(chosen_messages)
    if not chosen_text:
        return None

    # Generate direct (rejected) response
    rejected_messages = [
        {"role": "system", "content": SYSTEM_DIRECT},
        {"role": "user", "content": instruction},
    ]
    rejected_text, rejected_model = await client.generate(rejected_messages)
    if not rejected_text:
        return None

    # Validate: chosen should have questions, rejected should not (or fewer)
    chosen_questions = chosen_text.count("?")
    rejected_questions = rejected_text.count("?")

    if chosen_questions <= rejected_questions:
        # Swap didn't produce desired effect — still save but flag
        pass

    return {
        "prompt": [{"role": "user", "content": instruction}],
        "chosen": chosen_text,
        "rejected": rejected_text,
        "domain": domain,
        "chosen_model": chosen_model,
        "rejected_model": rejected_model,
        "chosen_questions": chosen_questions,
        "rejected_questions": rejected_questions,
    }


async def writer(result_queue: asyncio.Queue, output_path: str, total_target: int):
    """Write results to JSONL as they arrive."""
    written = 0
    domain_counts = Counter()

    with open(output_path, "a", encoding="utf-8") as f:
        while True:
            item = await result_queue.get()
            if item is None:  # sentinel
                break
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            written += 1
            domain_counts[item["domain"]] += 1

            if written % 50 == 0:
                print(f"  Written: {written}/{total_target} | {dict(domain_counts)}")

    print(f"Writer done: {written} pairs saved")
    return written


async def worker(worker_id: int, client: AsyncPreferenceClient,
                 task_queue: asyncio.Queue, result_queue: asyncio.Queue):
    """Worker that generates preference pairs from the task queue."""
    while True:
        try:
            task = task_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        pair = await generate_pair(client, task["instruction"], task["domain"])
        if pair:
            await result_queue.put(pair)

        task_queue.task_done()


async def generate_dataset(input_path: str, output_path: str, target: int, workers: int, resume: bool):
    """Main async pipeline."""

    # Load source examples
    examples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))

    print(f"Source dataset: {len(examples)} examples")

    # Count existing pairs if resuming
    existing = 0
    existing_domains = Counter()
    if resume and Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    pair = json.loads(line)
                    existing += 1
                    existing_domains[pair.get("domain", "unknown")] += 1
        print(f"Resuming: {existing} existing pairs")

    # Build task queue with domain balancing
    tasks = []
    rng = random.Random(42)

    for domain, domain_target in DOMAIN_TARGETS.items():
        remaining = domain_target - existing_domains.get(domain, 0)
        if remaining <= 0:
            continue

        if domain == "mixed":
            # Sample from all domains for mixed pairs
            domain_examples = rng.sample(examples, min(remaining * 2, len(examples)))
        else:
            domain_examples = [e for e in examples if e.get("domain") == domain]

        rng.shuffle(domain_examples)

        for ex in domain_examples[:remaining]:
            tasks.append({
                "instruction": ex.get("instruction", ""),
                "domain": domain if domain != "mixed" else ex.get("domain", "unknown"),
            })

    rng.shuffle(tasks)
    total_tasks = len(tasks)
    print(f"Tasks to generate: {total_tasks}")

    if total_tasks == 0:
        print("Nothing to generate!")
        return

    # Initialize client
    client = AsyncPreferenceClient()

    # Fill queues
    task_queue = asyncio.Queue()
    result_queue = asyncio.Queue()
    for t in tasks:
        await task_queue.put(t)

    # Start writer
    writer_task = asyncio.create_task(writer(result_queue, output_path, total_tasks))

    # Start workers
    worker_tasks = [
        asyncio.create_task(worker(i, client, task_queue, result_queue))
        for i in range(workers)
    ]

    # Wait for all workers to finish
    await asyncio.gather(*worker_tasks)

    # Signal writer to stop
    await result_queue.put(None)
    await writer_task

    # Print stats
    print(f"\nGeneration complete!")
    print(f"Model usage: {dict(client.stats)}")

    # Final count
    total_pairs = 0
    domain_counts = Counter()
    if Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    pair = json.loads(line.strip())
                    total_pairs += 1
                    domain_counts[pair.get("domain", "?")] += 1

    print(f"Total pairs: {total_pairs}")
    for d, c in sorted(domain_counts.items()):
        print(f"  {d}: {c}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default="training/data/combined_stem_balanced.jsonl")
    parser.add_argument("-o", "--output", default=OUTPUT_PATH)
    parser.add_argument("-w", "--workers", type=int, default=30)
    parser.add_argument("-t", "--target", type=int, default=10000)
    parser.add_argument("-e", "--env-file", default=".env",
                        help="Path to .env file with CEREBRAS_API_KEY_1..10")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    load_dotenv(args.env_file)

    if not Path(args.input).exists():
        print(f"Not found: {args.input}")
        return 1

    asyncio.run(generate_dataset(args.input, args.output, args.target, args.workers, args.resume))
    return 0


if __name__ == "__main__":
    sys.exit(main())
