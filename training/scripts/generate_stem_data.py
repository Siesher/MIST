#!/usr/bin/env python3
"""
Generate balanced STEM training dataset via Cerebras API multi-model distillation.

Teacher models (per-key limits):
  - gpt-oss-120b      30 rpm / 900 rph / 14 400 rpd / 64K tpm
  - llama-3.3-70b     30 rpm / 900 rph / 14 400 rpd / 64K tpm
  - llama3.1-8b       30 rpm / 900 rph / 14 400 rpd / 64K tpm
  - qwen-3-32b        30 rpm / 900 rph / 14 400 rpd / 64K tpm
  - zai-glm-4.7       10 rpm / 100 rph / 100 rpd   / 60K tpm

Uses 10 API keys x 5 models with async parallelism for high-throughput generation.
Each (key, model) pair = independent rate-limit slot.
Worker pool sends concurrent requests across all available slots.

Supports checkpoint/resume for multi-day runs.

Usage:
    cd C:/Work/MITS
    python training/scripts/generate_stem_data.py
    python training/scripts/generate_stem_data.py -n 1000 --domains math,physics
    python training/scripts/generate_stem_data.py --workers 30
    python training/scripts/generate_stem_data.py --resume
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
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from openai import AsyncOpenAI
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Model definitions & rate limits
# ─────────────────────────────────────────────────────────────

MODEL_CONFIGS = {
    "gpt-oss-120b": {
        "rpm": 30, "rph": 900, "rpd": 14_400,
        "tpm": 64_000, "tph": 1_000_000, "tpd": 1_000_000,
        "tier": "primary",  # best quality teacher
    },
    "llama-3.3-70b": {
        "rpm": 30, "rph": 900, "rpd": 14_400,
        "tpm": 64_000, "tph": 1_000_000, "tpd": 1_000_000,
        "tier": "primary",
    },
    "qwen-3-32b": {
        "rpm": 30, "rph": 900, "rpd": 14_400,
        "tpm": 64_000, "tph": 1_000_000, "tpd": 1_000_000,
        "tier": "primary",
    },
    "llama3.1-8b": {
        "rpm": 30, "rph": 900, "rpd": 14_400,
        "tpm": 64_000, "tph": 1_000_000, "tpd": 1_000_000,
        "tier": "secondary",  # simpler tasks only
    },
    "zai-glm-4.7": {
        "rpm": 10, "rph": 100, "rpd": 100,
        "tpm": 60_000, "tph": 1_000_000, "tpd": 1_000_000,
        "tier": "limited",
    },
}

# Which models to use for which difficulty (shuffled at selection time)
# zai-glm-4.7 is the best model but has only 100 rpd — reserve for hardest tasks
DIFFICULTY_MODEL_PREFERENCE = {
    "олимпиадный": ["zai-glm-4.7", "gpt-oss-120b", "llama-3.3-70b", "qwen-3-32b"],
    "продвинутый": ["zai-glm-4.7", "gpt-oss-120b", "llama-3.3-70b", "qwen-3-32b"],
    "базовый университетский": ["qwen-3-32b", "llama-3.3-70b", "gpt-oss-120b", "llama3.1-8b"],
    "школьный": ["llama3.1-8b", "qwen-3-32b", "llama-3.3-70b", "gpt-oss-120b"],
}

# ─────────────────────────────────────────────────────────────
#  Rate limiter with minute / hour / day windows
# ─────────────────────────────────────────────────────────────

@dataclass
class MultiWindowRateLimiter:
    """Track rate limits across minute, hour, and day windows."""
    rpm: int = 30
    rph: int = 900
    rpd: int = 14_400
    _minute_log: deque = field(default_factory=lambda: deque())
    _hour_log: deque = field(default_factory=lambda: deque())
    _day_log: deque = field(default_factory=lambda: deque())

    def _prune(self, now: float):
        while self._minute_log and now - self._minute_log[0] > 60:
            self._minute_log.popleft()
        while self._hour_log and now - self._hour_log[0] > 3600:
            self._hour_log.popleft()
        while self._day_log and now - self._day_log[0] > 86400:
            self._day_log.popleft()

    def can_request(self) -> bool:
        now = time.time()
        self._prune(now)
        return (
            len(self._minute_log) < self.rpm
            and len(self._hour_log) < self.rph
            and len(self._day_log) < self.rpd
        )

    def record(self):
        now = time.time()
        self._minute_log.append(now)
        self._hour_log.append(now)
        self._day_log.append(now)

    def wait_time(self) -> float:
        """Seconds until the next request slot opens."""
        now = time.time()
        self._prune(now)
        waits = []
        if len(self._minute_log) >= self.rpm:
            waits.append(60 - (now - self._minute_log[0]))
        if len(self._hour_log) >= self.rph:
            waits.append(3600 - (now - self._hour_log[0]))
        if len(self._day_log) >= self.rpd:
            waits.append(86400 - (now - self._day_log[0]))
        return max(0, min(waits)) if waits else 0

    @property
    def minute_usage(self) -> int:
        self._prune(time.time())
        return len(self._minute_log)

    @property
    def day_usage(self) -> int:
        self._prune(time.time())
        return len(self._day_log)


# ─────────────────────────────────────────────────────────────
#  Async multi-model Cerebras client
# ─────────────────────────────────────────────────────────────

class AsyncMultiModelCerebrasClient:
    """
    Async Cerebras API client with key rotation AND model rotation.

    For each (key, model) pair we maintain independent rate limits.
    10 keys × 5 models = 50 independent slots with concurrent requests.

    Slot acquisition pre-records the request to prevent over-subscription
    when multiple coroutines select slots simultaneously.
    """

    BASE_URL = "https://api.cerebras.ai/v1"

    def __init__(self, env_file: str = ".env", models: List[str] = None):
        load_dotenv(env_file)

        # Load API keys
        self.api_keys: List[str] = []
        for i in range(1, 11):
            key = os.getenv(f"CEREBRAS_API_KEY_{i}")
            if key and key.startswith("csk-"):
                self.api_keys.append(key)
        if not self.api_keys:
            raise ValueError("No valid Cerebras API keys (CEREBRAS_API_KEY_1..10) in env")
        logger.info(f"Loaded {len(self.api_keys)} API keys")

        # AsyncOpenAI client per key
        self.clients: List[AsyncOpenAI] = [
            AsyncOpenAI(base_url=self.BASE_URL, api_key=key) for key in self.api_keys
        ]

        # Models
        if models is None:
            models = list(MODEL_CONFIGS.keys())
        self.models = [m for m in models if m in MODEL_CONFIGS]
        logger.info(f"Models: {self.models}")

        # Rate limiters: (key_idx, model_name) -> limiter
        self.limiters: Dict[Tuple[int, str], MultiWindowRateLimiter] = {}
        for key_idx in range(len(self.api_keys)):
            for model_name in self.models:
                cfg = MODEL_CONFIGS[model_name]
                self.limiters[(key_idx, model_name)] = MultiWindowRateLimiter(
                    rpm=cfg["rpm"], rph=cfg["rph"], rpd=cfg["rpd"],
                )

        # Stats (protected by _lock)
        self.total_requests = 0
        self.total_tokens = 0
        self.model_requests: Dict[str, int] = {m: 0 for m in self.models}
        self._next_key: Dict[str, int] = {m: 0 for m in self.models}

        # Lock protects slot selection + stats updates
        self._lock = asyncio.Lock()

    def _find_slot_unlocked(
        self, preferred_models: List[str] = None
    ) -> Optional[Tuple[int, str]]:
        """
        Find best (key_idx, model_name) slot. MUST be called under _lock.

        Shuffles preferred models for even distribution, then round-robins
        keys within each model.  Falls back to non-preferred models.
        """
        candidates = list(preferred_models or self.models)
        random.shuffle(candidates)

        for model_name in candidates:
            if model_name not in self.models:
                continue
            start = self._next_key.get(model_name, 0)
            n_keys = len(self.api_keys)
            for i in range(n_keys):
                key_idx = (start + i) % n_keys
                if self.limiters[(key_idx, model_name)].can_request():
                    self._next_key[model_name] = (key_idx + 1) % n_keys
                    return key_idx, model_name

        # Fallback: non-preferred models
        fallback = [m for m in self.models if m not in candidates]
        random.shuffle(fallback)
        for model_name in fallback:
            start = self._next_key.get(model_name, 0)
            n_keys = len(self.api_keys)
            for i in range(n_keys):
                key_idx = (start + i) % n_keys
                if self.limiters[(key_idx, model_name)].can_request():
                    self._next_key[model_name] = (key_idx + 1) % n_keys
                    return key_idx, model_name

        return None

    async def acquire_slot(
        self, preferred_models: List[str] = None
    ) -> Optional[Tuple[AsyncOpenAI, int, str]]:
        """
        Acquire a slot atomically: find + pre-record under lock.

        Pre-recording prevents multiple coroutines from selecting the same
        slot before any of them complete their API call.
        Returns (client, key_idx, model_name) or None.
        """
        async with self._lock:
            result = self._find_slot_unlocked(preferred_models)
            if result is None:
                return None
            key_idx, model_name = result
            self.limiters[(key_idx, model_name)].record()
            return self.clients[key_idx], key_idx, model_name

    def _min_wait(self) -> float:
        """Minimum wait across all slots (no lock needed, read-only)."""
        return min(lim.wait_time() for lim in self.limiters.values())

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        preferred_models: List[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> Optional[Tuple[str, str]]:
        """
        Generate a completion, rotating across keys and models.

        Returns (response_text, model_used) or None on failure.
        """
        for attempt in range(max_retries):
            slot = await self.acquire_slot(preferred_models)

            if slot is None:
                wait = self._min_wait()
                await asyncio.sleep(max(0.5, wait) + random.uniform(0, 0.5))
                continue

            client, key_idx, model_name = slot

            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                async with self._lock:
                    self.total_requests += 1
                    self.model_requests[model_name] += 1
                    if response.usage:
                        self.total_tokens += response.usage.total_tokens

                text = response.choices[0].message.content
                return text, model_name

            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "429" in error_str:
                    logger.warning(
                        f"Rate limit on key {key_idx+1}/{model_name}, rotating"
                    )
                else:
                    wait = 2 ** attempt
                    logger.warning(f"Error [{model_name}]: {e}, retry in {wait}s")
                    await asyncio.sleep(wait)

        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "per_model": dict(self.model_requests),
            "keys": len(self.api_keys),
        }

    def daily_capacity_remaining(self) -> Dict[str, int]:
        """Estimate remaining requests per model today."""
        remaining = {}
        for model_name in self.models:
            total = 0
            for key_idx in range(len(self.api_keys)):
                lim = self.limiters[(key_idx, model_name)]
                total += max(0, lim.rpd - lim.day_usage)
            remaining[model_name] = total
        return remaining

    async def close(self):
        for client in self.clients:
            await client.close()


# ─────────────────────────────────────────────────────────────
#  STEM Templates (Russian, with <think> tags)
# ─────────────────────────────────────────────────────────────

DIFFICULTY_LEVELS = ["школьный", "базовый университетский", "продвинутый", "олимпиадный"]

STEM_TEMPLATES = {
    "math": {
        "calc": [
            {"system": "Ты опытный преподаватель математики. Сгенерируй задачу и подробное пошаговое решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с окончательным результатом в \\boxed{{}}.", "prompt": "Сгенерируй задачу по алгебре уровня {difficulty}: решение уравнений, неравенств или систем. Задача должна иметь числовой ответ."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй задачу и подробное пошаговое решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с окончательным результатом в \\boxed{{}}.", "prompt": "Сгенерируй задачу по математическому анализу уровня {difficulty}: вычисление производных, интегралов или пределов."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй задачу и подробное пошаговое решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с окончательным результатом в \\boxed{{}}.", "prompt": "Сгенерируй вычислительную задачу по геометрии уровня {difficulty}: нахождение площадей, объёмов, углов или длин."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй задачу и подробное пошаговое решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с окончательным результатом в \\boxed{{}}.", "prompt": "Сгенерируй задачу по теории чисел уровня {difficulty}: делимость, НОД, простые числа, сравнения по модулю."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй задачу и подробное пошаговое решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с окончательным результатом в \\boxed{{}}.", "prompt": "Сгенерируй вычислительную задачу по комбинаторике уровня {difficulty}: перестановки, сочетания, подсчёт."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй задачу и подробное пошаговое решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с окончательным результатом в \\boxed{{}}.", "prompt": "Сгенерируй задачу по тригонометрии уровня {difficulty}: уравнения, тождества, вычисление значений."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй задачу и подробное пошаговое решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с окончательным результатом в \\boxed{{}}.", "prompt": "Сгенерируй вычислительную задачу по линейной алгебре уровня {difficulty}: определители, собственные значения, системы линейных уравнений."},
        ],
        "conceptual": [
            {"system": "Ты опытный преподаватель математики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по алгебре уровня {difficulty}: объяснение свойств, доказательство утверждения или анализ метода решения."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по математическому анализу уровня {difficulty}: смысл производной, интеграла, непрерывность, сходимость рядов."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по геометрии уровня {difficulty}: свойства фигур, теоремы, геометрические преобразования."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по теории чисел уровня {difficulty}: свойства простых чисел, основная теорема арифметики."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по теории вероятностей уровня {difficulty}: случайные события, распределения, центральная предельная теорема."},
            {"system": "Ты опытный преподаватель математики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Объясни связь между двумя математическими концепциями уровня {difficulty}. Почему одно понятие вытекает из другого?"},
        ],
    },
    "physics": {
        "calc": [
            {"system": "Ты опытный преподаватель физики. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по механике уровня {difficulty}: кинематика, динамика, законы Ньютона, работа и энергия."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по термодинамике уровня {difficulty}: теплообмен, газовые законы, циклы, энтропия."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по электромагнетизму уровня {difficulty}: закон Кулона, цепи, индукция, магнитное поле."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по оптике уровня {difficulty}: преломление, дифракция, интерференция, линзы."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по колебаниям и волнам уровня {difficulty}: гармонические колебания, резонанс, волновое уравнение."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по ядерной физике уровня {difficulty}: радиоактивный распад, энергия связи, ядерные реакции."},
        ],
        "conceptual": [
            {"system": "Ты опытный преподаватель физики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по механике уровня {difficulty}: объяснение физического явления, принципа или закона."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по термодинамике уровня {difficulty}: начала термодинамики, тепловые машины, энтропия."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по электромагнетизму уровня {difficulty}: уравнения Максвелла, электромагнитные волны, принцип суперпозиции."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по современной физике уровня {difficulty}: специальная теория относительности, квантовая механика."},
            {"system": "Ты опытный преподаватель физики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Объясни физический парадокс или контринтуитивное явление уровня {difficulty}. Почему наивная интуиция ошибается?"},
        ],
    },
    "chemistry": {
        "calc": [
            {"system": "Ты опытный преподаватель химии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по стехиометрии уровня {difficulty}: расчёт по уравнениям реакций, выход продукта, избыток реагента."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по растворам уровня {difficulty}: концентрация, разбавление, смешивание, pH."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по термохимии уровня {difficulty}: тепловой эффект, закон Гесса, энтальпия."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по электрохимии уровня {difficulty}: ЭДС, уравнение Нернста, электролиз, законы Фарадея."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по химической кинетике уровня {difficulty}: скорость реакции, порядок реакции, константа скорости."},
        ],
        "conceptual": [
            {"system": "Ты опытный преподаватель химии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по органической химии уровня {difficulty}: механизмы реакций, функциональные группы, изомерия, номенклатура."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по неорганической химии уровня {difficulty}: строение атома, периодический закон, химическая связь."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по химическому равновесию уровня {difficulty}: принцип Ле Шателье, константа равновесия, факторы смещения."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по окислительно-восстановительным реакциям уровня {difficulty}: степени окисления, ОВР, электронный баланс."},
            {"system": "Ты опытный преподаватель химии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по растворам и коллоидной химии уровня {difficulty}: растворимость, коллигативные свойства, осмос."},
        ],
    },
    "cs": {
        "calc": [
            {"system": "Ты опытный преподаватель информатики. Сгенерируй задачу на программирование и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с кодом на Python.", "prompt": "Сгенерируй задачу на алгоритмы уровня {difficulty}: сортировка, поиск, жадные алгоритмы, бинарный поиск. Задача должна иметь конкретный ответ."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй задачу на программирование и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с кодом на Python.", "prompt": "Сгенерируй задачу на структуры данных уровня {difficulty}: стеки, очереди, деревья, хеш-таблицы, графы. Задача с конкретным результатом."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй задачу на программирование и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с кодом на Python.", "prompt": "Сгенерируй задачу на динамическое программирование уровня {difficulty}: подсчёт путей, оптимальные подструктуры, мемоизация."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй задачу на программирование и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с кодом на Python.", "prompt": "Сгенерируй задачу на теорию графов уровня {difficulty}: обходы, кратчайшие пути, остовные деревья, потоки в сетях."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй задачу на программирование и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с кодом на Python.", "prompt": "Сгенерируй задачу на рекурсию и комбинаторику уровня {difficulty}: генерация перестановок, подмножеств, рекуррентные соотношения."},
        ],
        "conceptual": [
            {"system": "Ты опытный преподаватель информатики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по сложности алгоритмов уровня {difficulty}: O-нотация, классы P и NP, NP-полнота."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по архитектуре компьютера уровня {difficulty}: кэш, конвейер, виртуальная память, многопоточность."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по операционным системам уровня {difficulty}: процессы, потоки, планирование, взаимоблокировка."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по базам данных уровня {difficulty}: нормализация, SQL vs NoSQL, индексы, транзакции, ACID."},
            {"system": "Ты опытный преподаватель информатики. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по парадигмам программирования уровня {difficulty}: ООП, функциональное, паттерны проектирования, SOLID."},
        ],
    },
    "biology": {
        "calc": [
            {"system": "Ты опытный преподаватель биологии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по генетике уровня {difficulty}: законы Менделя, скрещивание, вероятности генотипов."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по молекулярной биологии уровня {difficulty}: репликация ДНК, транскрипция, трансляция, подсчёт нуклеотидов."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по экологии уровня {difficulty}: динамика популяций, цепи питания, продуктивность экосистемы, расчёт биомассы."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по биохимии уровня {difficulty}: энергетический обмен, гликолиз, цикл Кребса, подсчёт АТФ."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй расчётную задачу и подробное решение на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ с числовым результатом в \\boxed{{}}.", "prompt": "Сгенерируй расчётную задачу по эволюции уровня {difficulty}: частоты аллелей, уравнение Харди-Вайнберга, отбор, дрейф генов."},
        ],
        "conceptual": [
            {"system": "Ты опытный преподаватель биологии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по клеточной биологии уровня {difficulty}: строение клетки, органеллы, мембранный транспорт, деление клетки."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по генетике уровня {difficulty}: мутации, генная регуляция, эпигенетика, геномное редактирование."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по экологии уровня {difficulty}: биоразнообразие, экосистемные услуги, сукцессия, глобальные проблемы."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по анатомии и физиологии человека уровня {difficulty}: нервная система, эндокринная система, иммунитет, кровообращение."},
            {"system": "Ты опытный преподаватель биологии. Сгенерируй концептуальный вопрос и подробный ответ на русском языке. Сначала размышляй в тегах <think>...</think>, затем дай ответ.", "prompt": "Сгенерируй концептуальный вопрос по эволюционной биологии уровня {difficulty}: механизмы эволюции, видообразование, филогенетика, молекулярные часы."},
        ],
    },
}

# Domain targets (balanced STEM, total ~65K)
DOMAIN_TARGETS = {
    "math": 15_000,
    "physics": 12_000,
    "chemistry": 10_000,
    "cs": 10_000,
    "biology": 8_000,
}

CALC_RATIO = 0.5  # 50% calc, 50% conceptual per domain


# ─────────────────────────────────────────────────────────────
#  Checkpoint / resume
# ─────────────────────────────────────────────────────────────

def load_checkpoint(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"domain_counts": {}, "total": 0}


def save_checkpoint(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def count_existing(output_path: str) -> Dict[str, Dict[str, int]]:
    """Count existing examples per domain/type for resume."""
    counts: Dict[str, Dict[str, int]] = {}
    for domain in DOMAIN_TARGETS:
        counts[domain] = {"calc": 0, "conceptual": 0}

    if not os.path.exists(output_path):
        return counts

    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ex = json.loads(line.strip())
                d = ex.get("domain", "")
                t = ex.get("type", "")
                if d in counts and t in counts[d]:
                    counts[d][t] += 1
            except (json.JSONDecodeError, KeyError):
                continue
    return counts


# ─────────────────────────────────────────────────────────────
#  Generation logic
# ─────────────────────────────────────────────────────────────

def build_generation_queue(
    existing: Dict[str, Dict[str, int]],
    targets: Dict[str, int],
    calc_ratio: float = 0.5,
) -> List[Dict[str, str]]:
    """Build a shuffled queue of (domain, type) tasks still needed."""
    queue = []
    for domain, target in targets.items():
        calc_target = int(target * calc_ratio)
        concept_target = target - calc_target

        calc_remaining = max(0, calc_target - existing.get(domain, {}).get("calc", 0))
        concept_remaining = max(0, concept_target - existing.get(domain, {}).get("conceptual", 0))

        queue.extend([{"domain": domain, "type": "calc"} for _ in range(calc_remaining)])
        queue.extend([{"domain": domain, "type": "conceptual"} for _ in range(concept_remaining)])

    random.shuffle(queue)
    return queue


async def generate_one(
    client: AsyncMultiModelCerebrasClient,
    domain: str,
    question_type: str,
) -> Optional[Dict[str, Any]]:
    """Generate a single STEM example (async)."""
    templates = STEM_TEMPLATES[domain][question_type]
    template = random.choice(templates)
    difficulty = random.choice(DIFFICULTY_LEVELS)

    system_prompt = template["system"]
    user_prompt = template["prompt"].format(difficulty=difficulty)

    # Select preferred models based on difficulty
    preferred = DIFFICULTY_MODEL_PREFERENCE.get(difficulty)

    result = await client.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
        preferred_models=preferred,
        max_tokens=2048,
        temperature=0.7,
    )

    if result is None:
        return None

    response_text, model_used = result

    if not response_text or len(response_text) < 50:
        return None

    return {
        "instruction": user_prompt,
        "output": response_text,
        "domain": domain,
        "type": question_type,
        "difficulty": difficulty,
        "teacher_model": model_used,
    }


# ─────────────────────────────────────────────────────────────
#  Async worker pool
# ─────────────────────────────────────────────────────────────

async def _worker(
    worker_id: int,
    client: AsyncMultiModelCerebrasClient,
    task_queue: asyncio.Queue,
    result_queue: asyncio.Queue,
    error_count: List[int],
    max_errors: int = 500,
):
    """
    Worker coroutine: pulls tasks from queue, generates examples.

    Each worker independently acquires the best available slot via
    client.acquire_slot(), so all 50 slots can be used concurrently.
    """
    while True:
        try:
            task = task_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        if error_count[0] > max_errors:
            task_queue.task_done()
            break

        example = await generate_one(client, task["domain"], task["type"])

        if example:
            await result_queue.put(example)
        else:
            error_count[0] += 1

        task_queue.task_done()


async def _writer(
    result_queue: asyncio.Queue,
    output_path: str,
    checkpoint_path: str,
    domain_counts: Dict[str, int],
    pbar: tqdm,
    checkpoint_interval: int,
    client: AsyncMultiModelCerebrasClient,
    existing_total: int,
    done_event: asyncio.Event,
):
    """Writer coroutine: serializes disk I/O from result_queue."""
    buffer: List[Dict] = []
    generated = 0
    start_time = time.time()

    while True:
        try:
            example = await asyncio.wait_for(result_queue.get(), timeout=2.0)
        except asyncio.TimeoutError:
            if done_event.is_set() and result_queue.empty():
                break
            continue

        if example is None:
            break

        buffer.append(example)
        generated += 1
        domain = example["domain"]
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        pbar.update(1)

        elapsed = time.time() - start_time
        rate = generated / elapsed if elapsed > 0 else 0
        pbar.set_postfix({
            "rate": f"{rate:.1f}/s",
            "workers": "async",
            domain: domain_counts[domain],
        })

        if len(buffer) >= checkpoint_interval:
            _flush_buffer(buffer, output_path)
            save_checkpoint(checkpoint_path, {
                "domain_counts": domain_counts,
                "total": existing_total + generated,
                "timestamp": datetime.now().isoformat(),
                "stats": client.get_stats(),
            })
            buffer.clear()

    # Final flush
    if buffer:
        _flush_buffer(buffer, output_path)
    return generated


def _flush_buffer(buffer: List[Dict], output_path: str):
    """Append buffered examples to JSONL file."""
    with open(output_path, "a", encoding="utf-8") as f:
        for item in buffer:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


async def generate_dataset(
    output_path: str,
    targets: Dict[str, int] = None,
    env_file: str = ".env",
    checkpoint_interval: int = 50,
    models: List[str] = None,
    num_workers: int = 50,
) -> str:
    """
    Generate the full STEM training dataset with async worker pool.

    Spawns `num_workers` concurrent coroutines, each independently
    acquiring (key, model) slots and making API calls in parallel.
    A single writer coroutine serializes disk I/O.
    """
    if targets is None:
        targets = DOMAIN_TARGETS.copy()

    # Resume: count existing examples
    existing = count_existing(output_path)
    existing_total = sum(c["calc"] + c["conceptual"] for c in existing.values())

    if existing_total > 0:
        logger.info(f"Resuming from {existing_total} existing examples")
        for d, counts in existing.items():
            if counts["calc"] + counts["conceptual"] > 0:
                logger.info(f"  {d}: {counts['calc']} calc + {counts['conceptual']} conceptual")

    # Build queue of remaining tasks
    queue_items = build_generation_queue(existing, targets, CALC_RATIO)
    total_target = sum(targets.values())

    if not queue_items:
        logger.info("Dataset already complete!")
        return output_path

    logger.info(f"Target: {total_target} examples, remaining: {len(queue_items)}")
    logger.info(f"Workers: {num_workers}")

    # Initialize async client
    client = AsyncMultiModelCerebrasClient(env_file=env_file, models=models)

    # Checkpoint setup
    checkpoint_path = output_path + ".checkpoint"
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Fill async queues
    task_queue: asyncio.Queue = asyncio.Queue()
    result_queue: asyncio.Queue = asyncio.Queue()
    for task in queue_items:
        await task_queue.put(task)

    domain_counts = {
        d: existing.get(d, {}).get("calc", 0) + existing.get(d, {}).get("conceptual", 0)
        for d in targets
    }

    # Progress bar
    pbar = tqdm(total=total_target, initial=existing_total, desc="STEM generation")
    done_event = asyncio.Event()
    error_count = [0]  # mutable counter shared across workers
    start_time = time.time()

    # Start writer
    writer_task = asyncio.create_task(
        _writer(
            result_queue, output_path, checkpoint_path,
            domain_counts, pbar, checkpoint_interval,
            client, existing_total, done_event,
        )
    )

    # Start worker pool
    workers = [
        asyncio.create_task(
            _worker(i, client, task_queue, result_queue, error_count)
        )
        for i in range(num_workers)
    ]

    # Wait for all workers to finish
    await asyncio.gather(*workers)

    # Signal writer to stop
    done_event.set()
    await result_queue.put(None)
    generated = await writer_task

    pbar.close()
    await client.close()

    # Cleanup checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    # Stats
    stats = client.get_stats()
    elapsed = time.time() - start_time
    logger.info(f"Generation complete: {generated} new examples in {elapsed/3600:.1f} hours")
    logger.info(f"Total requests: {stats['total_requests']}, tokens: {stats['total_tokens']:,}")
    logger.info(f"Per model: {stats['per_model']}")
    logger.info(f"Errors: {error_count[0]}")
    logger.info(f"Domain distribution: {domain_counts}")

    remaining_cap = client.daily_capacity_remaining()
    logger.info(f"Daily capacity remaining: {remaining_cap}")

    return output_path


def print_dataset_stats(output_path: str):
    """Print statistics for the generated dataset."""
    from collections import Counter

    examples = []
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                examples.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    total = len(examples)
    if total == 0:
        print("No examples found.")
        return

    print(f"\n{'='*60}")
    print(f"Dataset: {output_path}")
    print(f"Total examples: {total}")
    print(f"{'='*60}")

    # Domain distribution
    domain_counts = Counter(ex["domain"] for ex in examples)
    print(f"\nDomain distribution:")
    for domain in DOMAIN_TARGETS:
        count = domain_counts.get(domain, 0)
        pct = 100 * count / total
        target = DOMAIN_TARGETS.get(domain, 0)
        status = "OK" if count >= target * 0.95 else "LOW"
        print(f"  {domain:12s}: {count:6d} / {target:6d} ({pct:5.1f}%) [{status}]")

    # Balance check
    print(f"\nBalance check (invariants):")
    ok = True
    for domain in DOMAIN_TARGETS:
        pct = 100 * domain_counts.get(domain, 0) / total
        if pct > 25:
            print(f"  FAIL: {domain} = {pct:.1f}% (> 25%)")
            ok = False
        elif pct < 12:
            print(f"  FAIL: {domain} = {pct:.1f}% (< 12%)")
            ok = False
    if ok:
        print("  PASS: All domains within 12%-25%")

    # Type distribution
    type_counts = Counter(ex.get("type", "?") for ex in examples)
    print(f"\nType distribution:")
    for t, c in type_counts.most_common():
        print(f"  {t:15s}: {c:6d} ({100*c/total:.1f}%)")

    # Difficulty distribution
    diff_counts = Counter(ex.get("difficulty", "?") for ex in examples)
    print(f"\nDifficulty distribution:")
    for d, c in diff_counts.most_common():
        print(f"  {d:25s}: {c:6d} ({100*c/total:.1f}%)")

    # Teacher model distribution
    model_counts = Counter(ex.get("teacher_model", "?") for ex in examples)
    print(f"\nTeacher model distribution:")
    for m, c in model_counts.most_common():
        print(f"  {m:20s}: {c:6d} ({100*c/total:.1f}%)")

    # Output quality
    lengths = [len(ex.get("output", "")) for ex in examples]
    has_think = sum(1 for ex in examples if "<think>" in ex.get("output", ""))
    print(f"\nOutput quality:")
    print(f"  Avg length:    {sum(lengths)/len(lengths):.0f} chars")
    print(f"  Min length:    {min(lengths)} chars")
    print(f"  Max length:    {max(lengths)} chars")
    print(f"  With <think>:  {has_think}/{total} ({100*has_think/total:.1f}%)")


# ─────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate STEM training dataset via Cerebras API multi-model distillation"
    )
    parser.add_argument(
        "-o", "--output",
        default="training/data/raw_stem.jsonl",
        help="Output JSONL file (default: training/data/raw_stem.jsonl)",
    )
    parser.add_argument(
        "-n", "--num-examples",
        type=int,
        default=None,
        help="Total examples (default: use DOMAIN_TARGETS = 55K)",
    )
    parser.add_argument(
        "-d", "--domains",
        default=None,
        help="Comma-separated domains (default: all 5 STEM)",
    )
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated model names to use (default: all 5)",
    )
    parser.add_argument(
        "--env-file",
        default=".env.example",
        help="Path to .env file with CEREBRAS_API_KEY_1..10",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=50,
        help="Flush to disk every N examples (default: 50)",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=50,
        help="Number of async workers (default: 50 = 10 keys × 5 models)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Print stats for existing dataset and exit",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing output file (default behavior if file exists)",
    )

    args = parser.parse_args()

    if args.stats_only:
        if os.path.exists(args.output):
            print_dataset_stats(args.output)
        else:
            print(f"File not found: {args.output}")
        return 0

    # Build targets
    domains = None
    targets = DOMAIN_TARGETS.copy()

    if args.domains:
        domains = [d.strip() for d in args.domains.split(",")]
        targets = {d: targets[d] for d in domains if d in targets}

    if args.num_examples:
        # Scale targets proportionally
        total_default = sum(targets.values())
        scale = args.num_examples / total_default
        targets = {d: max(1, int(v * scale)) for d, v in targets.items()}
        # Adjust to match exact total
        diff = args.num_examples - sum(targets.values())
        if diff != 0:
            largest = max(targets, key=targets.get)
            targets[largest] += diff

    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(",")]

    logger.info(f"Targets: {targets} (total: {sum(targets.values())})")
    logger.info(f"Output: {args.output}")
    logger.info(f"Models: {models or 'all'}")
    logger.info(f"Workers: {args.workers}")

    try:
        asyncio.run(
            generate_dataset(
                output_path=args.output,
                targets=targets,
                env_file=args.env_file,
                checkpoint_interval=args.checkpoint_interval,
                models=models,
                num_workers=args.workers,
            )
        )

        # Print final stats
        if os.path.exists(args.output):
            print_dataset_stats(args.output)

        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted. Progress saved — rerun to resume.")
        return 1
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise


if __name__ == "__main__":
    exit(main())
