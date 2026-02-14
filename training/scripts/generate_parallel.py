#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Параллельная генерация диалогов с использованием нескольких API ключей.

Оптимизации:
- Asyncio для параллельных запросов
- Каждый воркер использует свой API ключ
- Инкрементальное сохранение
- Автоматическое возобновление

Использование:
    python training/scripts/generate_parallel.py \
        --output data/training/dialogs.jsonl \
        --workers 5 \
        --dialogs-per-combo 3
"""

import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass
import logging
import sys
import os
import aiofiles
from asyncio import Semaphore, Lock

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Попытка импорта Cerebras
try:
    from cerebras.cloud.sdk import AsyncCerebras
    HAS_ASYNC_CEREBRAS = True
except ImportError:
    HAS_ASYNC_CEREBRAS = False
    logger.warning("AsyncCerebras not available, trying sync version")

try:
    from cerebras.cloud.sdk import Cerebras
    HAS_CEREBRAS = True
except ImportError:
    HAS_CEREBRAS = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from training.scripts.cerebras_dialog_generator import (
    Discipline,
    StudentPersona,
    DialogConfig,
    CerebrasDialogGenerator,
)


@dataclass
class GenerationTask:
    """Задача на генерацию одного диалога."""
    discipline: Discipline
    topic: str
    difficulty: str
    persona: StudentPersona
    combo_index: int

    @property
    def key(self) -> tuple:
        return (self.discipline.value, self.topic, self.difficulty, self.persona.value, self.combo_index)


class ParallelDialogGenerator:
    """
    Параллельный генератор диалогов.

    Использует asyncio и несколько API ключей для ускорения.
    """

    MODELS = [
        "qwen-3-235b-a22b-instruct-2507",
        "llama-3.3-70b",
    ]

    SYSTEM_PROMPT = """Ты — генератор обучающих диалогов для сократического репетитора.

Сгенерируй реалистичный диалог между учеником и репетитором.

ПРАВИЛА РЕПЕТИТОРА:
1. Никогда не давать прямых ответов
2. Задавать наводящие вопросы
3. Использовать ходы: scaffolding, problematize, rectify, encourage, hint, tell (редко)

ФОРМАТ: Верни JSON с ключом "dialog" — массив сообщений:
{
  "dialog": [
    {"role": "system", "content": "Системный промпт"},
    {"role": "user", "content": "Задача: ... \\n\\nУченик: ..."},
    {"role": "assistant", "content": "{\\"move\\": \\"scaffolding\\", \\"message\\": \\"...\\"}"},
    ...
  ]
}

ВАЖНО: Все assistant сообщения — валидный JSON с move и message. Пиши на русском."""

    PERSONA_HINTS = {
        StudentPersona.NOVICE: "Начинающий — плохо понимает базу, нужны простые объяснения",
        StudentPersona.INTERMEDIATE: "Средний уровень — знает основы, но путается в деталях",
        StudentPersona.ADVANCED: "Продвинутый — хорошо понимает, ищет оптимальные решения",
        StudentPersona.CONFUSED: "Запутавшийся — имеет заблуждения, уверен в неправильном",
        StudentPersona.CURIOUS: "Любопытный — много спрашивает 'почему?', хочет понять суть",
    }

    def __init__(self, num_workers: int = 5, model: str = None):
        self.api_keys = self._load_api_keys()
        self.num_workers = min(num_workers, len(self.api_keys))
        self.model = model or self.MODELS[0]

        if not self.api_keys:
            raise ValueError("No Cerebras API keys found in .env")

        logger.info(f"Initialized with {self.num_workers} workers, {len(self.api_keys)} API keys")

        # Для синхронного fallback
        self.sync_generator = CerebrasDialogGenerator(model=self.model)

        # Статистика
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
        }

        # Lock для файла
        self.file_lock = Lock()
        self.completed_lock = Lock()
        self.completed: Set[tuple] = set()

    def _load_api_keys(self) -> List[str]:
        """Загрузка API ключей."""
        keys = []
        for i in range(1, 20):
            key = os.getenv(f'CEREBRAS_API_KEY_{i}')
            if key:
                keys.append(key)
        return keys

    async def _generate_one_async(
        self,
        task: GenerationTask,
        api_key: str,
        semaphore: Semaphore
    ) -> Optional[Dict[str, Any]]:
        """Генерация одного диалога (async версия)."""
        async with semaphore:
            # Проверяем, не сгенерирован ли уже
            async with self.completed_lock:
                if task.key in self.completed:
                    self.stats['skipped'] += 1
                    return None

            self.stats['total'] += 1

            # Получаем примеры задач для темы
            topic_examples = self.sync_generator.DISCIPLINE_TOPICS.get(
                task.discipline, {}
            ).get(task.topic, ["Решить задачу"])

            example_task = topic_examples[task.combo_index % len(topic_examples)]

            prompt = f"""Дисциплина: {task.discipline.value}
Тема: {task.topic}
Сложность: {task.difficulty}
Пример задачи: {example_task}

Тип ученика: {self.PERSONA_HINTS[task.persona]}

Сгенерируй диалог из 4-8 реплик (чередование user/assistant)."""

            try:
                if HAS_ASYNC_CEREBRAS:
                    client = AsyncCerebras(api_key=api_key)
                    response = await client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": self.SYSTEM_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.9,
                        max_tokens=3000,
                    )
                    content = response.choices[0].message.content
                else:
                    # Sync fallback в executor
                    loop = asyncio.get_event_loop()
                    content = await loop.run_in_executor(
                        None,
                        self._generate_sync,
                        task, api_key
                    )
                    if content is None:
                        return None

                # Парсинг JSON
                dialog = self._parse_response(content, task)

                if dialog:
                    self.stats['success'] += 1
                    return dialog
                else:
                    self.stats['failed'] += 1
                    return None

            except Exception as e:
                logger.warning(f"Error generating {task.key}: {e}")
                self.stats['failed'] += 1
                return None

    def _generate_sync(self, task: GenerationTask, api_key: str) -> Optional[str]:
        """Синхронная генерация (fallback)."""
        try:
            client = Cerebras(api_key=api_key)

            topic_examples = self.sync_generator.DISCIPLINE_TOPICS.get(
                task.discipline, {}
            ).get(task.topic, ["Решить задачу"])

            example_task = topic_examples[task.combo_index % len(topic_examples)]

            prompt = f"""Дисциплина: {task.discipline.value}
Тема: {task.topic}
Сложность: {task.difficulty}
Пример задачи: {example_task}

Тип ученика: {self.PERSONA_HINTS[task.persona]}

Сгенерируй диалог из 4-8 реплик."""

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=3000,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Sync generation error: {e}")
            return None

    def _parse_response(self, content: str, task: GenerationTask) -> Optional[Dict]:
        """Парсинг ответа в формат диалога."""
        import re

        try:
            # Очистка markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            content = content.strip()

            # Поиск JSON
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end > start:
                content = content[start:end+1]

            # Удаление trailing commas
            content = re.sub(r',(\s*[}\]])', r'\1', content)

            data = json.loads(content)

            if "dialog" in data and isinstance(data["dialog"], list):
                dialog_list = data["dialog"]

                # Валидация
                if len(dialog_list) < 3:
                    return None

                # Проверка assistant ответов
                for msg in dialog_list:
                    if msg.get("role") == "assistant":
                        try:
                            assistant_data = json.loads(msg["content"])
                            if "move" not in assistant_data or "message" not in assistant_data:
                                return None
                        except:
                            return None

                return {
                    "conversations": dialog_list,
                    "metadata": {
                        "discipline": task.discipline.value,
                        "topic": task.topic,
                        "difficulty": task.difficulty,
                        "persona": task.persona.value,
                        "combo_index": task.combo_index,
                        "generated_at": datetime.now().isoformat(),
                        "model": self.model,
                    }
                }
        except Exception as e:
            pass

        return None

    async def _save_dialog(self, dialog: Dict, output_path: Path):
        """Сохранение диалога в файл."""
        async with self.file_lock:
            async with aiofiles.open(output_path, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(dialog, ensure_ascii=False) + '\n')

            # Добавляем в completed
            meta = dialog["metadata"]
            key = (meta["discipline"], meta["topic"], meta["difficulty"],
                   meta["persona"], meta["combo_index"])
            async with self.completed_lock:
                self.completed.add(key)

    def _load_completed(self, output_path: Path) -> Set[tuple]:
        """Загрузка уже сгенерированных комбинаций."""
        completed = set()

        if not output_path.exists():
            return completed

        with open(output_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    dialog = json.loads(line)
                    meta = dialog.get("metadata", {})
                    key = (
                        meta.get("discipline", ""),
                        meta.get("topic", ""),
                        meta.get("difficulty", ""),
                        meta.get("persona", ""),
                        meta.get("combo_index", 0)
                    )
                    completed.add(key)
                except:
                    pass

        return completed

    async def generate_all(
        self,
        output_path: Path,
        disciplines: List[Discipline] = None,
        dialogs_per_combo: int = 3,
    ):
        """
        Параллельная генерация всех диалогов.
        """
        if disciplines is None:
            disciplines = list(Discipline)

        difficulties = ["easy", "medium", "hard"]
        personas = list(StudentPersona)

        # Загружаем уже сгенерированные
        self.completed = self._load_completed(output_path)
        logger.info(f"Found {len(self.completed)} existing dialogs")

        # Создаём задачи
        tasks = []
        for disc in disciplines:
            topics = list(self.sync_generator.DISCIPLINE_TOPICS.get(disc, {}).keys())
            for topic in topics:
                for difficulty in difficulties:
                    for persona in personas:
                        for idx in range(dialogs_per_combo):
                            task = GenerationTask(
                                discipline=disc,
                                topic=topic,
                                difficulty=difficulty,
                                persona=persona,
                                combo_index=idx
                            )
                            if task.key not in self.completed:
                                tasks.append(task)

        total_tasks = len(tasks)
        logger.info(f"Tasks to generate: {total_tasks}")

        if total_tasks == 0:
            logger.info("All dialogs already generated!")
            return

        print(f"\n{'='*60}")
        print("ПАРАЛЛЕЛЬНАЯ ГЕНЕРАЦИЯ ДИАЛОГОВ")
        print(f"{'='*60}")
        print(f"Воркеров:          {self.num_workers}")
        print(f"API ключей:        {len(self.api_keys)}")
        print(f"Задач к генерации: {total_tasks}")
        print(f"Уже сгенерировано: {len(self.completed)}")
        print(f"{'='*60}\n")

        # Semaphore для ограничения параллельных запросов
        semaphore = Semaphore(self.num_workers)

        # Распределяем ключи по задачам
        async def process_task(task: GenerationTask, task_num: int):
            key_idx = task_num % len(self.api_keys)
            api_key = self.api_keys[key_idx]

            logger.info(f"[{task_num+1}/{total_tasks}] {task.discipline.value}:{task.topic} | {task.difficulty} | {task.persona.value}")

            dialog = await self._generate_one_async(task, api_key, semaphore)

            if dialog:
                await self._save_dialog(dialog, output_path)
                async with self.completed_lock:
                    total_in_file = len(self.completed)
                logger.info(f"  -> Saved (session: {self.stats['success']}, file: {total_in_file})")

        # Запускаем все задачи
        await asyncio.gather(*[
            process_task(task, i) for i, task in enumerate(tasks)
        ])

        # Статистика
        print(f"\n{'='*60}")
        print("РЕЗУЛЬТАТЫ")
        print(f"{'='*60}")
        print(f"Успешно:     {self.stats['success']}")
        print(f"Ошибок:      {self.stats['failed']}")
        print(f"Пропущено:   {self.stats['skipped']}")
        print(f"Всего:       {len(self.completed)}")
        if self.stats['success'] + self.stats['failed'] > 0:
            rate = 100 * self.stats['success'] / (self.stats['success'] + self.stats['failed'])
            print(f"Успешность:  {rate:.1f}%")
        print(f"{'='*60}\n")


async def main_async(args):
    """Async main."""
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.discipline.lower() == 'all':
        disciplines = list(Discipline)
    else:
        disciplines = [Discipline(args.discipline.lower())]

    generator = ParallelDialogGenerator(
        num_workers=args.workers,
        model=args.model
    )

    await generator.generate_all(
        output_path=output_path,
        disciplines=disciplines,
        dialogs_per_combo=args.dialogs_per_combo,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Параллельная генерация диалогов (быстрее в N раз)"
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='data/training/dialogs.jsonl',
        help='Выходной файл'
    )
    parser.add_argument(
        '--discipline',
        type=str,
        default='all',
        help='Дисциплина или "all"'
    )
    parser.add_argument(
        '--dialogs-per-combo',
        type=int,
        default=3,
        help='Диалогов на комбинацию'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Количество параллельных воркеров'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Модель Cerebras'
    )

    args = parser.parse_args()

    # Проверяем aiofiles
    try:
        import aiofiles
    except ImportError:
        print("Installing aiofiles...")
        os.system("pip install aiofiles")
        import aiofiles

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
