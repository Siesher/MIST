"""
Algorithmic Task Bank — Банк алгоритмических задач

50+ задач в стиле LeetCode/Codeforces с тестами.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.execution.code_executor import TestCase


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Category(Enum):
    ARRAYS = "arrays"
    STRINGS = "strings"
    MATH = "math"
    SORTING = "sorting"
    SEARCHING = "searching"
    RECURSION = "recursion"
    DYNAMIC = "dynamic_programming"
    GRAPHS = "graphs"
    TREES = "trees"
    GREEDY = "greedy"
    TWO_POINTERS = "two_pointers"
    STACK_QUEUE = "stack_queue"
    HASH_TABLE = "hash_table"


@dataclass
class AlgorithmicTask:
    """Алгоритмическая задача с тестами."""
    id: str
    title: str
    title_ru: str
    difficulty: Difficulty
    category: Category

    description_ru: str
    input_format: str
    output_format: str

    examples: List[Dict[str, str]]  # [{"input": "...", "output": "...", "explanation": "..."}]
    test_cases: List[TestCase]

    constraints: List[str] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)
    solution_code: str = ""
    solution_explanation: str = ""

    time_limit_sec: float = 2.0
    memory_limit_mb: int = 256

    # Статистика
    attempts: int = 0
    accepted: int = 0

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempts if self.attempts > 0 else 0

    def get_visible_tests(self) -> List[TestCase]:
        """Получить видимые тесты (из примеров)."""
        return [t for t in self.test_cases if not t.is_hidden]

    def get_problem_text(self) -> str:
        """Получить полный текст задачи."""
        text = f"# {self.title_ru}\n\n"
        text += f"**Сложность:** {self._diff_emoji()} {self._diff_ru()}\n"
        text += f"**Категория:** {self._cat_ru()}\n\n"
        text += "---\n\n"
        text += f"## Описание\n\n{self.description_ru}\n\n"
        text += f"## Формат входных данных\n\n{self.input_format}\n\n"
        text += f"## Формат выходных данных\n\n{self.output_format}\n\n"

        if self.constraints:
            text += "## Ограничения\n\n"
            for c in self.constraints:
                text += f"- {c}\n"
            text += "\n"

        text += "## Примеры\n\n"
        for i, ex in enumerate(self.examples, 1):
            text += f"### Пример {i}\n\n"
            text += f"**Вход:**\n```\n{ex['input']}\n```\n\n"
            text += f"**Выход:**\n```\n{ex['output']}\n```\n\n"
            if ex.get('explanation'):
                text += f"**Пояснение:** {ex['explanation']}\n\n"

        return text

    def _diff_emoji(self) -> str:
        return {"easy": "🟢", "medium": "🟡", "hard": "🔴"}[self.difficulty.value]

    def _diff_ru(self) -> str:
        return {"easy": "Лёгкая", "medium": "Средняя", "hard": "Сложная"}[self.difficulty.value]

    def _cat_ru(self) -> str:
        cats = {
            "arrays": "Массивы",
            "strings": "Строки",
            "math": "Математика",
            "sorting": "Сортировка",
            "searching": "Поиск",
            "recursion": "Рекурсия",
            "dynamic_programming": "Динамическое программирование",
            "graphs": "Графы",
            "trees": "Деревья",
            "greedy": "Жадные алгоритмы",
            "two_pointers": "Два указателя",
            "stack_queue": "Стек и очередь",
            "hash_table": "Хэш-таблицы"
        }
        return cats.get(self.category.value, self.category.value)


class AlgorithmicTaskBank:
    """Банк алгоритмических задач."""

    def __init__(self, bank_path: str = "./data/algo_tasks.json"):
        self.bank_path = Path(bank_path)
        self.tasks: Dict[str, AlgorithmicTask] = {}

        self._load_bank()

    def _load_bank(self):
        """Загрузить или создать банк."""
        if self.bank_path.exists():
            # Загружаем из файла
            with open(self.bank_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for task_data in data.get("tasks", []):
                    task = self._dict_to_task(task_data)
                    self.tasks[task.id] = task
        else:
            # Создаём с начальными задачами
            self._create_default_tasks()
            self.save()

    def _dict_to_task(self, d: dict) -> AlgorithmicTask:
        """Преобразовать словарь в задачу."""
        test_cases = [
            TestCase(
                input=t["input"],
                expected_output=t["output"],
                is_hidden=t.get("hidden", False)
            )
            for t in d.get("test_cases", [])
        ]

        return AlgorithmicTask(
            id=d["id"],
            title=d["title"],
            title_ru=d["title_ru"],
            difficulty=Difficulty(d["difficulty"]),
            category=Category(d["category"]),
            description_ru=d["description_ru"],
            input_format=d["input_format"],
            output_format=d["output_format"],
            examples=d.get("examples", []),
            test_cases=test_cases,
            constraints=d.get("constraints", []),
            hints=d.get("hints", []),
            solution_code=d.get("solution_code", ""),
            solution_explanation=d.get("solution_explanation", ""),
            time_limit_sec=d.get("time_limit_sec", 2.0),
            attempts=d.get("attempts", 0),
            accepted=d.get("accepted", 0)
        )

    def _task_to_dict(self, task: AlgorithmicTask) -> dict:
        """Преобразовать задачу в словарь."""
        return {
            "id": task.id,
            "title": task.title,
            "title_ru": task.title_ru,
            "difficulty": task.difficulty.value,
            "category": task.category.value,
            "description_ru": task.description_ru,
            "input_format": task.input_format,
            "output_format": task.output_format,
            "examples": task.examples,
            "test_cases": [
                {
                    "input": t.input,
                    "output": t.expected_output,
                    "hidden": t.is_hidden
                }
                for t in task.test_cases
            ],
            "constraints": task.constraints,
            "hints": task.hints,
            "solution_code": task.solution_code,
            "solution_explanation": task.solution_explanation,
            "time_limit_sec": task.time_limit_sec,
            "attempts": task.attempts,
            "accepted": task.accepted
        }

    def save(self):
        """Сохранить банк."""
        self.bank_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "tasks": [self._task_to_dict(t) for t in self.tasks.values()]
        }

        with open(self.bank_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_task(self, task_id: str) -> Optional[AlgorithmicTask]:
        """Получить задачу по ID."""
        return self.tasks.get(task_id)

    def get_tasks_by_difficulty(self, difficulty: Difficulty) -> List[AlgorithmicTask]:
        """Получить задачи по сложности."""
        return [t for t in self.tasks.values() if t.difficulty == difficulty]

    def get_tasks_by_category(self, category: Category) -> List[AlgorithmicTask]:
        """Получить задачи по категории."""
        return [t for t in self.tasks.values() if t.category == category]

    def get_random_task(
        self,
        difficulty: Optional[Difficulty] = None,
        category: Optional[Category] = None
    ) -> Optional[AlgorithmicTask]:
        """Получить случайную задачу с фильтрами."""
        import random

        candidates = list(self.tasks.values())

        if difficulty:
            candidates = [t for t in candidates if t.difficulty == difficulty]
        if category:
            candidates = [t for t in candidates if t.category == category]

        return random.choice(candidates) if candidates else None

    def record_attempt(self, task_id: str, is_accepted: bool):
        """Записать попытку решения."""
        if task_id in self.tasks:
            self.tasks[task_id].attempts += 1
            if is_accepted:
                self.tasks[task_id].accepted += 1
            self.save()

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику банка."""
        by_diff = {d.value: 0 for d in Difficulty}
        by_cat = {c.value: 0 for c in Category}

        for task in self.tasks.values():
            by_diff[task.difficulty.value] += 1
            by_cat[task.category.value] += 1

        return {
            "total": len(self.tasks),
            "by_difficulty": by_diff,
            "by_category": {k: v for k, v in by_cat.items() if v > 0}
        }

    def _create_default_tasks(self):
        """Создать начальный набор задач."""
        from src.data.algo_tasks_collection import get_all_algorithmic_tasks
        from src.data.algo_tasks_extra import get_all_additional_tasks

        # Основные задачи
        tasks = get_all_algorithmic_tasks()
        for task in tasks:
            self.tasks[task.id] = task

        # Дополнительные задачи
        extra_tasks = get_all_additional_tasks()
        for task in extra_tasks:
            self.tasks[task.id] = task
