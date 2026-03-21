#!/usr/bin/env python3
"""
Generate evaluation dataset for MITS training pipeline.

Uses LLM-based generation via Cerebras API (or Ollama fallback) to create
verifiable STEM problems for per-stage model evaluation.

Each problem is generated with a solution, then cross-validated:
the LLM solves it twice — only problems where both solutions agree are kept.
This ensures answer correctness without human review.

Output: JSONL file with schema matching the training data format:
  {prompt, ground_truth, domain, difficulty, answer_type, source}

Usage:
    # Generate 200 eval problems (40 per domain)
    python training/scripts/generate_eval_dataset.py --total 200

    # Generate using Ollama locally
    python training/scripts/generate_eval_dataset.py --backend ollama --model qwen3:4b

    # Resume interrupted generation
    python training/scripts/generate_eval_dataset.py --resume
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import asyncio
import json
import logging
import os
import random
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ─── Domain-specific generation templates ─────────────────────

DOMAIN_TEMPLATES = {
    "math": {
        "topics": [
            "линейные уравнения", "квадратные уравнения", "системы уравнений",
            "производные", "интегралы", "пределы", "арифметические прогрессии",
            "геометрические прогрессии", "тригонометрия", "логарифмы",
            "площади фигур", "объёмы тел", "комбинаторика", "теория вероятностей",
            "неравенства", "модули", "параметры", "планиметрия", "стереометрия",
        ],
        "difficulties": {
            "easy": "школьный уровень (8-9 класс), одношаговое решение",
            "medium": "базовый университетский, 2-3 шага решения",
            "hard": "олимпиадный или продвинутый, нетривиальное решение",
        },
    },
    "physics": {
        "topics": [
            "кинематика", "динамика", "законы Ньютона", "работа и энергия",
            "импульс", "электростатика", "закон Ома", "магнетизм",
            "оптика (линзы, зеркала)", "термодинамика", "волны и колебания",
            "гидростатика", "закон сохранения энергии",
        ],
        "difficulties": {
            "easy": "базовая формула с подстановкой",
            "medium": "2-3 формулы, нужно комбинировать",
            "hard": "несколько этапов, нестандартная постановка",
        },
    },
    "chemistry": {
        "topics": [
            "расчёт молярной массы", "стехиометрия реакций", "растворы (концентрация)",
            "окислительно-восстановительные реакции", "электролиз",
            "химическое равновесие", "pH растворов", "газовые законы",
            "органическая химия (номенклатура)", "термохимия",
        ],
        "difficulties": {
            "easy": "прямой расчёт по одной формуле",
            "medium": "2-3 шага, нужно уравнять реакцию",
            "hard": "многостадийный расчёт, нестандартные условия",
        },
    },
    "biology": {
        "topics": [
            "генетика (законы Менделя)", "молекулярная биология (ДНК, РНК)",
            "экология (цепи питания, популяции)", "физиология человека",
            "клеточная биология", "эволюция", "ботаника", "зоология",
        ],
        "difficulties": {
            "easy": "знание одного факта или определения",
            "medium": "применение закона или классификация",
            "hard": "генетическая задача или многоуровневый анализ",
        },
    },
    "cs": {
        "topics": [
            "сложность алгоритмов", "сортировка", "поиск", "рекурсия",
            "структуры данных (стек, очередь, дерево)", "графы",
            "динамическое программирование", "системы счисления",
            "побитовые операции", "базовый SQL",
        ],
        "difficulties": {
            "easy": "определение или простой алгоритм",
            "medium": "реализация алгоритма или анализ сложности",
            "hard": "оптимизация, нестандартный подход",
        },
    },
}

# System prompts for generation and verification
GENERATOR_SYSTEM = """Ты — опытный преподаватель STEM. Твоя задача — придумать задачу по указанной теме и сложности.

ФОРМАТ ОТВЕТА (строго):
```json
{
  "prompt": "Текст задачи на русском языке",
  "solution": "Подробное пошаговое решение",
  "ground_truth": "Числовой или краткий ответ (число, формула, буква)",
  "answer_type": "numeric|latex_boxed|mc_letter"
}
```

ПРАВИЛА:
- Задача должна иметь ЕДИНСТВЕННЫЙ правильный ответ
- Для числовых задач: ответ — число (возможно с единицами)
- Для формул: ответ в формате LaTeX
- Для multiple-choice: 4 варианта (A, B, C, D), ответ — буква
- Решение должно быть проверяемо математически
- НЕ используй данные, которые надо искать в справочниках"""

SOLVER_SYSTEM = """Реши задачу пошагово. Запиши финальный ответ в \\boxed{}.
Если задача multiple-choice, запиши букву ответа в \\boxed{}."""


@dataclass
class GenerationConfig:
    total: int = 200
    per_domain: Optional[int] = None
    backend: str = "cerebras"  # "cerebras" or "ollama"
    model: str = "llama-3.3-70b"
    ollama_model: str = "qwen3:4b"
    ollama_host: str = "http://localhost:11434"
    output_path: str = "training/data/eval_dataset.jsonl"
    cross_validate: bool = True
    max_retries: int = 3
    resume: bool = False


def _extract_json_from_response(text: str) -> Optional[Dict]:
    """Extract JSON object from LLM response, handling markdown fences."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ```
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { ... }
    match = re.search(r'\{[^{}]*"prompt"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _extract_answer_from_solution(text: str) -> str:
    """Extract answer from a solution with \\boxed{}."""
    boxed = re.findall(r'\\boxed\{([^}]+)\}', text)
    if boxed:
        return boxed[-1].strip()
    numbers = re.findall(r'[-+]?\d*\.?\d+', text)
    return numbers[-1] if numbers else ""


def _answers_match(a1: str, a2: str) -> bool:
    """Check if two answers are equivalent."""
    a1, a2 = a1.strip().lower(), a2.strip().lower()
    if a1 == a2:
        return True
    # Try numeric comparison
    try:
        n1 = float(re.findall(r'[-+]?\d*\.?\d+', a1)[-1])
        n2 = float(re.findall(r'[-+]?\d*\.?\d+', a2)[-1])
        return abs(n1 - n2) < 1e-6 or (abs(n1) > 1e-10 and abs(n1 - n2) / abs(n1) < 0.01)
    except (ValueError, IndexError):
        return False


class EvalDatasetGenerator:
    """Generates evaluation dataset using LLM-based generation with cross-validation."""

    def __init__(self, config: GenerationConfig):
        self.config = config
        self.problems: List[Dict] = []
        self._api_keys: List[str] = []
        self._clients: list = []
        self._load_existing()
        if self.config.backend == "cerebras":
            self._init_cerebras()

    def _init_cerebras(self):
        """Load Cerebras API keys from .env (CEREBRAS_API_KEY_1..10)."""
        from dotenv import load_dotenv
        env_path = _PROJECT_ROOT / ".env"
        load_dotenv(env_path)
        for i in range(1, 11):
            key = os.getenv(f"CEREBRAS_API_KEY_{i}")
            if key and key.startswith("csk-"):
                self._api_keys.append(key)
        if not self._api_keys:
            raise ValueError(
                f"No valid Cerebras API keys (CEREBRAS_API_KEY_1..10) found in {env_path}"
            )
        logger.info(f"Loaded {len(self._api_keys)} Cerebras API keys from {env_path}")
        from openai import AsyncOpenAI
        self._clients = [
            AsyncOpenAI(base_url="https://api.cerebras.ai/v1", api_key=key)
            for key in self._api_keys
        ]

    def _load_existing(self):
        """Load existing problems for resume support."""
        path = Path(self.config.output_path)
        if self.config.resume and path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.problems.append(json.loads(line))
            logger.info(f"Resumed: loaded {len(self.problems)} existing problems")

    async def _call_llm(self, system: str, user: str) -> str:
        """Call LLM via Cerebras or Ollama."""
        if self.config.backend == "ollama":
            return await self._call_ollama(system, user)
        return await self._call_cerebras(system, user)

    async def _call_cerebras(self, system: str, user: str) -> str:
        """Call Cerebras API with random key rotation."""
        client = random.choice(self._clients)
        resp = await client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
            max_tokens=2048,
        )
        return resp.choices[0].message.content or ""

    async def _call_ollama(self, system: str, user: str) -> str:
        """Call Ollama API."""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.config.ollama_host}/api/chat",
                json={
                    "model": self.config.ollama_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.8, "num_predict": 2048},
                },
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                data = await resp.json()
                return data.get("message", {}).get("content", "")

    async def generate_problem(self, domain: str, difficulty: str, topic: str) -> Optional[Dict]:
        """Generate a single problem and optionally cross-validate it."""
        template = DOMAIN_TEMPLATES[domain]
        diff_desc = template["difficulties"][difficulty]

        user_prompt = (
            f"Домен: {domain}\n"
            f"Тема: {topic}\n"
            f"Сложность: {difficulty} ({diff_desc})\n\n"
            f"Придумай задачу с ОДНИМ правильным ответом."
        )

        for attempt in range(self.config.max_retries):
            try:
                response = await self._call_llm(GENERATOR_SYSTEM, user_prompt)
                problem = _extract_json_from_response(response)
                if not problem or not problem.get("prompt") or not problem.get("ground_truth"):
                    continue

                problem["domain"] = domain
                problem["difficulty"] = difficulty
                problem["topic"] = topic
                problem["source"] = f"llm_generated_{self.config.backend}"
                if "answer_type" not in problem:
                    problem["answer_type"] = "numeric"

                # Cross-validation: solve independently and check answer matches
                if self.config.cross_validate:
                    solver_response = await self._call_llm(SOLVER_SYSTEM, problem["prompt"])
                    solver_answer = _extract_answer_from_solution(solver_response)
                    if not _answers_match(str(problem["ground_truth"]), solver_answer):
                        logger.debug(
                            f"Cross-validation failed: "
                            f"generated={problem['ground_truth']}, solved={solver_answer}"
                        )
                        continue

                # Remove solution from eval data (only keep prompt + ground truth)
                problem.pop("solution", None)
                return problem

            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {domain}/{topic}: {e}")
                await asyncio.sleep(2 ** attempt)

        return None

    async def generate_all(self):
        """Generate evaluation dataset across all domains."""
        domains = list(DOMAIN_TEMPLATES.keys())
        per_domain = self.config.per_domain or (self.config.total // len(domains))

        # Count existing by domain
        existing_counts = Counter(p["domain"] for p in self.problems)
        logger.info(f"Target: {per_domain} problems per domain, {len(domains)} domains")
        logger.info(f"Existing: {dict(existing_counts)}")

        tasks = []
        for domain in domains:
            needed = per_domain - existing_counts.get(domain, 0)
            if needed <= 0:
                logger.info(f"  {domain}: already have {existing_counts.get(domain, 0)}, skipping")
                continue

            template = DOMAIN_TEMPLATES[domain]
            difficulties = ["easy", "medium", "hard"]
            per_diff = max(1, needed // len(difficulties))

            for difficulty in difficulties:
                for i in range(per_diff):
                    topic = random.choice(template["topics"])
                    tasks.append((domain, difficulty, topic))

        random.shuffle(tasks)
        logger.info(f"Generating {len(tasks)} problems...")

        # Process with concurrency limit
        semaphore = asyncio.Semaphore(5 if self.config.backend == "cerebras" else 2)

        async def _bounded_generate(domain, difficulty, topic):
            async with semaphore:
                return await self.generate_problem(domain, difficulty, topic)

        results = await asyncio.gather(
            *[_bounded_generate(d, diff, t) for d, diff, t in tasks],
            return_exceptions=True,
        )

        new_count = 0
        for result in results:
            if isinstance(result, dict):
                self.problems.append(result)
                new_count += 1

        logger.info(f"Generated {new_count} new problems (total: {len(self.problems)})")

    def save(self):
        """Save dataset to JSONL."""
        path = Path(self.config.output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            for problem in self.problems:
                f.write(json.dumps(problem, ensure_ascii=False) + "\n")

        # Print stats
        domain_counts = Counter(p["domain"] for p in self.problems)
        diff_counts = Counter(p["difficulty"] for p in self.problems)
        type_counts = Counter(p.get("answer_type", "unknown") for p in self.problems)

        logger.info(f"\nDataset saved to {path}")
        logger.info(f"Total: {len(self.problems)} problems")
        logger.info(f"By domain: {dict(domain_counts)}")
        logger.info(f"By difficulty: {dict(diff_counts)}")
        logger.info(f"By answer type: {dict(type_counts)}")

        # Save metadata
        meta = {
            "generated_at": datetime.now().isoformat(),
            "total": len(self.problems),
            "backend": self.config.backend,
            "model": self.config.model if self.config.backend == "cerebras" else self.config.ollama_model,
            "cross_validated": self.config.cross_validate,
            "domain_counts": dict(domain_counts),
            "difficulty_counts": dict(diff_counts),
        }
        meta_path = path.with_suffix(".meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        logger.info(f"Metadata saved to {meta_path}")


async def main():
    parser = argparse.ArgumentParser(description="Generate MITS evaluation dataset")
    parser.add_argument("--total", type=int, default=200, help="Total problems to generate")
    parser.add_argument("--per-domain", type=int, help="Problems per domain (overrides --total)")
    parser.add_argument("--backend", choices=["cerebras", "ollama"], default="cerebras")
    parser.add_argument("--model", default="llama-3.3-70b", help="Cerebras model name")
    parser.add_argument("--ollama-model", default="qwen3:4b", help="Ollama model name")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--output", default="training/data/eval_dataset.jsonl")
    parser.add_argument("--no-cross-validate", action="store_true", help="Skip cross-validation")
    parser.add_argument("--resume", action="store_true", help="Resume from existing output")
    args = parser.parse_args()

    config = GenerationConfig(
        total=args.total,
        per_domain=args.per_domain,
        backend=args.backend,
        model=args.model,
        ollama_model=args.ollama_model,
        ollama_host=args.ollama_host,
        output_path=args.output,
        cross_validate=not args.no_cross_validate,
        resume=args.resume,
    )

    generator = EvalDatasetGenerator(config)
    await generator.generate_all()
    generator.save()


if __name__ == "__main__":
    asyncio.run(main())
