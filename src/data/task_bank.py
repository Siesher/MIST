"""
Task Bank — Банк предгенерированных задач

Обеспечивает мгновенный выбор задач без ожидания генерации.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import json
import random
from pathlib import Path

from src.data.schemas import Task, Difficulty


@dataclass
class TaskStats:
    """Статистика по задаче."""
    attempts: int = 0
    successes: int = 0
    avg_time_seconds: float = 0
    avg_hints_used: float = 0
    
    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts > 0 else 0


class TaskBank:
    """
    Банк предгенерированных задач.
    
    Возможности:
    - Мгновенный выбор задачи по критериям
    - Статистика по каждой задаче
    - Адаптивный выбор на основе уровня студента
    """
    
    def __init__(self, bank_path: str = "./data/task_bank.json"):
        self.bank_path = Path(bank_path)
        self.tasks: Dict[str, Task] = {}
        self.stats: Dict[str, TaskStats] = {}
        
        self._load_bank()
    
    def _load_bank(self):
        """Загрузить банк задач."""
        if self.bank_path.exists():
            with open(self.bank_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for task_data in data.get("tasks", []):
                    task = Task(**task_data)
                    self.tasks[task.id] = task
                    
                    # Загружаем статистику
                    stats_data = data.get("stats", {}).get(task.id, {})
                    self.stats[task.id] = TaskStats(**stats_data)
        else:
            # Создаём банк с начальными задачами
            self._create_default_bank()
    
    def _create_default_bank(self):
        """Создать банк с начальными задачами."""
        default_tasks = self._get_default_tasks()
        
        for task in default_tasks:
            self.tasks[task.id] = task
            self.stats[task.id] = TaskStats()
        
        self.save()
    
    def save(self):
        """Сохранить банк на диск."""
        self.bank_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "tasks": [
                {
                    "id": t.id,
                    "topic": t.topic,
                    "difficulty": t.difficulty.value if isinstance(t.difficulty, Difficulty) else t.difficulty,
                    "problem": t.problem,
                    "solution": t.solution,
                    "answer": t.answer,
                    "skills": t.skills,
                    "hints": t.hints,
                    "common_mistakes": t.common_mistakes
                }
                for t in self.tasks.values()
            ],
            "stats": {
                task_id: {
                    "attempts": s.attempts,
                    "successes": s.successes,
                    "avg_time_seconds": s.avg_time_seconds,
                    "avg_hints_used": s.avg_hints_used
                }
                for task_id, s in self.stats.items()
            }
        }
        
        with open(self.bank_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_task(
        self,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        skills: Optional[List[str]] = None,
        exclude_ids: Optional[List[str]] = None
    ) -> Optional[Task]:
        """
        Получить задачу по критериям.
        
        Args:
            topic: Фильтр по теме
            difficulty: Фильтр по сложности
            skills: Фильтр по навыкам (хотя бы один должен совпасть)
            exclude_ids: ID задач для исключения (уже решённые)
        """
        exclude_ids = exclude_ids or []
        candidates = []
        
        for task in self.tasks.values():
            if task.id in exclude_ids:
                continue
            
            if topic and task.topic != topic:
                continue
            
            task_diff = task.difficulty.value if isinstance(task.difficulty, Difficulty) else task.difficulty
            if difficulty and task_diff != difficulty:
                continue
            
            if skills:
                if not any(s in task.skills for s in skills):
                    continue
            
            candidates.append(task)
        
        if not candidates:
            return None
        
        return random.choice(candidates)
    
    def get_adaptive_task(
        self,
        skill_masteries: Dict[str, float],
        exclude_ids: Optional[List[str]] = None
    ) -> Optional[Task]:
        """
        Выбрать задачу адаптивно на основе уровня знаний.
        
        Алгоритм:
        - Находим навыки с mastery 0.3-0.7 (зона развития)
        - Выбираем задачу на эти навыки
        - Предпочитаем задачи с success_rate близким к 70%
        """
        exclude_ids = exclude_ids or []
        
        # Находим навыки в зоне развития
        target_skills = [
            skill for skill, mastery in skill_masteries.items()
            if 0.3 <= mastery <= 0.7
        ]
        
        if not target_skills:
            # Если нет - берём самые слабые
            target_skills = sorted(
                skill_masteries.keys(),
                key=lambda s: skill_masteries[s]
            )[:3]
        
        # Ищем задачи на эти навыки
        candidates = []
        for task in self.tasks.values():
            if task.id in exclude_ids:
                continue
            
            skill_match = any(s in target_skills for s in task.skills)
            if skill_match:
                candidates.append(task)
        
        if not candidates:
            # Fallback - любая задача
            return self.get_task(exclude_ids=exclude_ids)
        
        # Сортируем по близости success_rate к 0.7
        def score(task):
            stats = self.stats.get(task.id, TaskStats())
            return abs(stats.success_rate - 0.7)
        
        candidates.sort(key=score)
        
        # Берём из топ-5 случайно (для разнообразия)
        top_candidates = candidates[:5]
        return random.choice(top_candidates)
    
    def record_attempt(
        self,
        task_id: str,
        success: bool,
        time_seconds: float,
        hints_used: int
    ):
        """Записать результат попытки решения."""
        if task_id not in self.stats:
            self.stats[task_id] = TaskStats()
        
        stats = self.stats[task_id]
        
        # Обновляем средние с экспоненциальным сглаживанием
        alpha = 0.1  # Вес новых данных
        
        if stats.attempts > 0:
            stats.avg_time_seconds = (1 - alpha) * stats.avg_time_seconds + alpha * time_seconds
            stats.avg_hints_used = (1 - alpha) * stats.avg_hints_used + alpha * hints_used
        else:
            stats.avg_time_seconds = time_seconds
            stats.avg_hints_used = hints_used
        
        stats.attempts += 1
        if success:
            stats.successes += 1
        
        self.save()
    
    def add_task(self, task: Task):
        """Добавить новую задачу в банк."""
        self.tasks[task.id] = task
        self.stats[task.id] = TaskStats()
        self.save()
    
    def get_topics(self) -> List[str]:
        """Получить список всех тем."""
        return list(set(t.topic for t in self.tasks.values()))
    
    def get_skills(self) -> List[str]:
        """Получить список всех навыков."""
        skills = set()
        for task in self.tasks.values():
            skills.update(task.skills)
        return list(skills)
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Получить сводную статистику банка."""
        total_tasks = len(self.tasks)
        total_attempts = sum(s.attempts for s in self.stats.values())
        
        by_difficulty = {}
        for task in self.tasks.values():
            diff = task.difficulty.value if isinstance(task.difficulty, Difficulty) else task.difficulty
            by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
        
        return {
            "total_tasks": total_tasks,
            "total_attempts": total_attempts,
            "by_difficulty": by_difficulty,
            "topics": self.get_topics(),
            "skills_count": len(self.get_skills())
        }
    
    def _get_default_tasks(self) -> List[Task]:
        """Начальный набор задач."""
        return [
            # === ПРОИЗВОДНЫЕ (easy) ===
            Task(
                id="deriv_001",
                topic="derivatives",
                difficulty=Difficulty.EASY,
                problem="Найдите производную функции $f(x) = x^3$",
                solution="""Используем правило степени: $(x^n)' = n \\cdot x^{n-1}$

$$f'(x) = 3x^{3-1} = 3x^2$$""",
                answer="$3x^2$",
                skills=["power_rule", "derivatives_basic"],
                hints=[
                    "Вспомните правило дифференцирования степенной функции",
                    "Для $x^n$ производная равна $n \\cdot x^{n-1}$",
                    "Здесь $n = 3$, значит производная..."
                ],
                common_mistakes=[
                    "Забывают уменьшить степень на 1",
                    "Путают с интегрированием"
                ]
            ),
            Task(
                id="deriv_002",
                topic="derivatives",
                difficulty=Difficulty.EASY,
                problem="Найдите производную: $f(x) = 5x^2 + 3x - 7$",
                solution="""Дифференцируем каждое слагаемое отдельно:

$$(5x^2)' = 5 \\cdot 2x = 10x$$
$$(3x)' = 3$$
$$(-7)' = 0$$

Итого: $f'(x) = 10x + 3$""",
                answer="$10x + 3$",
                skills=["power_rule", "derivatives_basic"],
                hints=[
                    "Производная суммы равна сумме производных",
                    "Производная константы равна нулю",
                    "$(ax^n)' = a \\cdot n \\cdot x^{n-1}$"
                ],
                common_mistakes=[
                    "Забывают про производную константы",
                    "Ошибки в коэффициентах"
                ]
            ),
            
            # === ПРОИЗВОДНЫЕ (medium) ===
            Task(
                id="deriv_003",
                topic="derivatives", 
                difficulty=Difficulty.MEDIUM,
                problem="Найдите производную: $f(x) = x^2 \\cdot \\sin(x)$",
                solution="""Используем правило произведения: $(uv)' = u'v + uv'$

Пусть $u = x^2$, $v = \\sin(x)$

$u' = 2x$, $v' = \\cos(x)$

$$f'(x) = 2x \\cdot \\sin(x) + x^2 \\cdot \\cos(x)$$""",
                answer="$2x\\sin(x) + x^2\\cos(x)$",
                skills=["product_rule", "trig_derivatives"],
                hints=[
                    "Здесь произведение двух функций — какое правило применить?",
                    "$(uv)' = u'v + uv'$. Что здесь $u$ и $v$?",
                    "Не забудьте, что $(\\sin x)' = \\cos x$"
                ],
                common_mistakes=[
                    "Просто перемножают производные",
                    "Забывают одно из слагаемых"
                ]
            ),
            Task(
                id="deriv_004",
                topic="derivatives",
                difficulty=Difficulty.MEDIUM,
                problem="Найдите производную: $f(x) = \\frac{x^2}{x+1}$",
                solution="""Используем правило частного: $\\left(\\frac{u}{v}\\right)' = \\frac{u'v - uv'}{v^2}$

$u = x^2$, $v = x + 1$
$u' = 2x$, $v' = 1$

$$f'(x) = \\frac{2x(x+1) - x^2 \\cdot 1}{(x+1)^2} = \\frac{2x^2 + 2x - x^2}{(x+1)^2} = \\frac{x^2 + 2x}{(x+1)^2}$$""",
                answer="$\\frac{x^2 + 2x}{(x+1)^2}$",
                skills=["quotient_rule", "derivatives_basic"],
                hints=[
                    "Это дробь — какое правило для дроби?",
                    "Формула: $\\frac{u'v - uv'}{v^2}$",
                    "Не забудьте упростить числитель"
                ],
                common_mistakes=[
                    "Путают порядок в числителе (u'v - uv', не наоборот)",
                    "Забывают возвести знаменатель в квадрат"
                ]
            ),
            
            # === ПРОИЗВОДНЫЕ (hard) ===
            Task(
                id="deriv_005",
                topic="derivatives",
                difficulty=Difficulty.HARD,
                problem="Найдите производную: $f(x) = \\ln(\\sin(x^2))$",
                solution="""Применяем цепное правило трижды (композиция трёх функций):

$f(x) = \\ln(g(x))$, где $g(x) = \\sin(h(x))$, где $h(x) = x^2$

$$f'(x) = \\frac{1}{\\sin(x^2)} \\cdot \\cos(x^2) \\cdot 2x = \\frac{2x \\cos(x^2)}{\\sin(x^2)} = 2x \\cot(x^2)$$""",
                answer="$2x\\cot(x^2)$ или $\\frac{2x\\cos(x^2)}{\\sin(x^2)}$",
                skills=["chain_rule", "trig_derivatives", "derivatives_advanced"],
                hints=[
                    "Здесь три вложенные функции — снаружи внутрь",
                    "$(\\ln u)' = \\frac{u'}{u}$, теперь найдите $u'$",
                    "Не забудьте производную внутреннего $x^2$"
                ],
                common_mistakes=[
                    "Забывают про одну из вложенных функций",
                    "Не доводят цепочку до конца"
                ]
            ),
            
            # === ИНТЕГРАЛЫ (easy) ===
            Task(
                id="integ_001",
                topic="integrals",
                difficulty=Difficulty.EASY,
                problem="Найдите неопределённый интеграл: $\\int x^4 \\, dx$",
                solution="""Используем правило: $\\int x^n \\, dx = \\frac{x^{n+1}}{n+1} + C$

$$\\int x^4 \\, dx = \\frac{x^{4+1}}{4+1} + C = \\frac{x^5}{5} + C$$""",
                answer="$\\frac{x^5}{5} + C$",
                skills=["integrals_basic"],
                hints=[
                    "Интегрирование — обратная операция к дифференцированию",
                    "Для $x^n$ интеграл равен $\\frac{x^{n+1}}{n+1}$",
                    "Не забудьте константу $C$!"
                ],
                common_mistakes=[
                    "Забывают константу интегрирования C",
                    "Ошибки в степени"
                ]
            ),
            
            # === ПРЕДЕЛЫ (easy) ===
            Task(
                id="limit_001",
                topic="limits",
                difficulty=Difficulty.EASY,
                problem="Вычислите предел: $\\lim_{x \\to 2} (x^2 + 3x - 1)$",
                solution="""Функция $f(x) = x^2 + 3x - 1$ непрерывна, поэтому можно подставить:

$$\\lim_{x \\to 2} (x^2 + 3x - 1) = 2^2 + 3 \\cdot 2 - 1 = 4 + 6 - 1 = 9$$""",
                answer="$9$",
                skills=["limits"],
                hints=[
                    "Это полином — какое свойство у полиномов при вычислении пределов?",
                    "Для непрерывных функций можно просто подставить значение",
                    "Подставьте $x = 2$"
                ],
                common_mistakes=[
                    "Усложняют простую задачу",
                    "Арифметические ошибки"
                ]
            ),
            Task(
                id="limit_002",
                topic="limits",
                difficulty=Difficulty.MEDIUM,
                problem="Вычислите предел: $\\lim_{x \\to 0} \\frac{\\sin(x)}{x}$",
                solution="""Это первый замечательный предел:

$$\\lim_{x \\to 0} \\frac{\\sin(x)}{x} = 1$$

Это фундаментальный результат, который доказывается геометрически.""",
                answer="$1$",
                skills=["limits", "trigonometry_basics"],
                hints=[
                    "При $x \\to 0$ и числитель и знаменатель стремятся к 0",
                    "Это называется неопределённость $\\frac{0}{0}$",
                    "Вспомните первый замечательный предел"
                ],
                common_mistakes=[
                    "Думают, что 0/0 = 0 или не определено",
                    "Не знают замечательные пределы"
                ]
            ),
            
            # === ПРОГРАММИРОВАНИЕ (easy) ===
            Task(
                id="prog_001",
                topic="programming",
                difficulty=Difficulty.EASY,
                problem="Напишите функцию на Python, которая возвращает сумму двух чисел.",
                solution="""```python
def add(a, b):
    return a + b
```

Или более кратко:
```python
add = lambda a, b: a + b
```""",
                answer="```python\ndef add(a, b):\n    return a + b\n```",
                skills=["functions_prog", "variables"],
                hints=[
                    "Функция создаётся с помощью `def`",
                    "Функция принимает два параметра",
                    "Используйте `return` для возврата результата"
                ],
                common_mistakes=[
                    "Забывают return",
                    "Путают print и return"
                ]
            ),
            Task(
                id="prog_002",
                topic="programming",
                difficulty=Difficulty.MEDIUM,
                problem="Напишите функцию, которая определяет, является ли число простым.",
                solution="""```python
def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
```

Оптимизация: проверяем делители только до $\\sqrt{n}$.""",
                answer="```python\ndef is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5) + 1):\n        if n % i == 0:\n            return False\n    return True\n```",
                skills=["loops", "conditionals", "algorithms"],
                hints=[
                    "Простое число делится только на 1 и себя",
                    "Достаточно проверить делители до $\\sqrt{n}$",
                    "Не забудьте особые случаи: 0, 1, отрицательные числа"
                ],
                common_mistakes=[
                    "Проверяют делители до n (неэффективно)",
                    "Забывают про случай n < 2",
                    "Неправильно обрабатывают 2"
                ]
            ),
            Task(
                id="prog_003",
                topic="programming",
                difficulty=Difficulty.HARD,
                problem="Напишите функцию для вычисления n-го числа Фибоначчи с мемоизацией.",
                solution="""```python
def fibonacci(n, memo={}):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fibonacci(n-1, memo) + fibonacci(n-2, memo)
    return memo[n]
```

Или с декоратором:
```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
```""",
                answer="Функция с мемоизацией через словарь или @lru_cache",
                skills=["recursion", "algorithms", "data_structures"],
                hints=[
                    "Обычная рекурсия для Фибоначчи очень медленная — почему?",
                    "Мемоизация сохраняет уже вычисленные значения",
                    "Используйте словарь для хранения результатов"
                ],
                common_mistakes=[
                    "Пишут обычную рекурсию без мемоизации",
                    "Неправильная инициализация словаря",
                    "Забывают базовый случай"
                ]
            ),
            
            # === УРАВНЕНИЯ (easy) ===
            Task(
                id="eq_001",
                topic="equations",
                difficulty=Difficulty.EASY,
                problem="Решите уравнение: $2x + 5 = 13$",
                solution="""Переносим 5 вправо:
$$2x = 13 - 5 = 8$$

Делим на 2:
$$x = 4$$""",
                answer="$x = 4$",
                skills=["linear_equations", "arithmetic"],
                hints=[
                    "Нужно изолировать $x$ на одной стороне",
                    "Сначала избавьтесь от +5",
                    "Потом разделите обе части на 2"
                ],
                common_mistakes=[
                    "Знаковые ошибки при переносе",
                    "Забывают делить обе части"
                ]
            ),
            Task(
                id="eq_002",
                topic="equations",
                difficulty=Difficulty.MEDIUM,
                problem="Решите уравнение: $x^2 - 5x + 6 = 0$",
                solution="""Разложим на множители. Ищем числа, дающие в сумме -5, в произведении 6:
$$-2 + (-3) = -5, \\quad (-2) \\cdot (-3) = 6$$

$$(x - 2)(x - 3) = 0$$

$$x_1 = 2, \\quad x_2 = 3$$""",
                answer="$x = 2$ или $x = 3$",
                skills=["quadratic_equations"],
                hints=[
                    "Это квадратное уравнение — какие методы знаете?",
                    "Попробуйте разложить на множители",
                    "Найдите два числа: сумма = 5, произведение = 6"
                ],
                common_mistakes=[
                    "Ошибки в знаках при разложении",
                    "Дают только один корень"
                ]
            )
        ]
