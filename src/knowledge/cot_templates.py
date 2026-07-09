"""
Chain-of-Thought (CoT) Templates for MITS.

Feature 010: CoT prompting for improved reasoning quality.

Russian language templates for:
- Mathematical problem solving
- Error analysis
- Step-by-step guidance
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Load configuration
try:
    from src.config import settings
    COT_ENABLED = getattr(settings, 'COT_ENABLED', True)
    COT_MIN_DIFFICULTY = getattr(settings, 'COT_MIN_DIFFICULTY', 'medium')
except ImportError:
    COT_ENABLED = True
    COT_MIN_DIFFICULTY = 'medium'


class Difficulty(Enum):
    """Task difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    @classmethod
    def from_string(cls, value: str) -> "Difficulty":
        """Convert string to Difficulty."""
        value_lower = value.lower()
        for d in cls:
            if d.value == value_lower:
                return d
        return cls.MEDIUM

    def __ge__(self, other: "Difficulty") -> bool:
        order = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD]
        return order.index(self) >= order.index(other)


class CoTType(Enum):
    """Types of Chain-of-Thought prompts."""
    PROBLEM_SOLVING = "problem_solving"
    ERROR_ANALYSIS = "error_analysis"
    CONCEPT_EXPLANATION = "concept_explanation"
    VERIFICATION = "verification"
    SCAFFOLDING = "scaffolding"


@dataclass
class CoTTemplate:
    """A Chain-of-Thought template."""
    id: str
    type: CoTType
    name_ru: str
    template: str
    min_difficulty: Difficulty = Difficulty.MEDIUM
    topics: List[str] = None

    def __post_init__(self):
        if self.topics is None:
            self.topics = []


# ═══════════════════════════════════════════════════════════════════════════════
# RUSSIAN COT TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

COT_TEMPLATES: Dict[str, CoTTemplate] = {
    # ─────────────────────────────────────────────────────────────────────────────
    # Problem Solving Templates
    # ─────────────────────────────────────────────────────────────────────────────
    "solve_step_by_step": CoTTemplate(
        id="solve_step_by_step",
        type=CoTType.PROBLEM_SOLVING,
        name_ru="Пошаговое решение",
        template="""Давай разберём эту задачу по шагам:

**Шаг 1: Понимание задачи**
- Что дано: {given}
- Что требуется найти: {find}
- Какие формулы/методы могут понадобиться: {methods}

**Шаг 2: Планирование решения**
- Подумай, какой первый шаг нужно сделать
- Какие промежуточные результаты понадобятся

**Шаг 3: Выполнение**
- Теперь попробуй выполнить первый шаг
- Что у тебя получилось?

Какой первый шаг ты бы сделал?""",
        min_difficulty=Difficulty.MEDIUM,
        topics=["general"]
    ),

    "derivative_cot": CoTTemplate(
        id="derivative_cot",
        type=CoTType.PROBLEM_SOLVING,
        name_ru="Нахождение производной",
        template="""Чтобы найти производную, давай рассуждать пошагово:

**1. Анализ функции**
- Определи тип функции: {function_type}
- Есть ли сложная композиция функций?
- Нужно ли применять правило цепочки?

**2. Выбор метода**
- Если есть произведение → правило произведения: (fg)' = f'g + fg'
- Если есть частное → правило частного: (f/g)' = (f'g - fg')/g²
- Если есть композиция → правило цепочки: (f(g(x)))' = f'(g(x)) · g'(x)

**3. Применение правила**
- Запиши, что является внешней функцией
- Запиши, что является внутренней функцией
- Примени соответствующее правило

Какой тип функции у тебя и какое правило нужно применить?""",
        min_difficulty=Difficulty.MEDIUM,
        topics=["derivatives", "calculus"]
    ),

    "integral_cot": CoTTemplate(
        id="integral_cot",
        type=CoTType.PROBLEM_SOLVING,
        name_ru="Вычисление интеграла",
        template="""Чтобы вычислить интеграл, подумаем пошагово:

**1. Анализ подынтегрального выражения**
- Какого типа функция под интегралом?
- Есть ли очевидная первообразная?

**2. Выбор метода**
- Табличный интеграл → применяем формулу напрямую
- Есть внутренняя функция → метод замены: u = g(x), du = g'(x)dx
- Произведение функций → интегрирование по частям: ∫u·dv = uv - ∫v·du

**3. Выполнение**
- Если замена: определи u и найди du
- Если по частям: выбери u и dv (LIATE правило)

Какой метод ты бы выбрал для этого интеграла?""",
        min_difficulty=Difficulty.MEDIUM,
        topics=["integrals", "calculus"]
    ),

    "limit_cot": CoTTemplate(
        id="limit_cot",
        type=CoTType.PROBLEM_SOLVING,
        name_ru="Вычисление предела",
        template="""Давай найдём этот предел пошагово:

**1. Прямая подстановка**
- Попробуем подставить значение напрямую
- Получили число? Это и есть ответ!
- Получили неопределённость? Продолжаем анализ

**2. Определение типа неопределённости**
- 0/0 → можно применить правило Лопиталя или упростить
- ∞/∞ → правило Лопиталя или деление на старшую степень
- ∞ - ∞ → приведение к общему знаменателю
- 0 · ∞ → преобразование в дробь

**3. Применение метода**
- Лопиталь: дифференцируем числитель и знаменатель отдельно
- Упрощение: разложи и сократи

Какая неопределённость у тебя получилась при подстановке?""",
        min_difficulty=Difficulty.MEDIUM,
        topics=["limits", "calculus"]
    ),

    "equation_cot": CoTTemplate(
        id="equation_cot",
        type=CoTType.PROBLEM_SOLVING,
        name_ru="Решение уравнения",
        template="""Чтобы решить уравнение, давай действовать по плану:

**1. Классификация уравнения**
- Линейное: ax + b = 0
- Квадратное: ax² + bx + c = 0
- Показательное: aˣ = b
- Тригонометрическое: sin(x) = a и т.д.

**2. Выбор метода**
- Линейное → изолируем x
- Квадратное → дискриминант или разложение
- Показательное → логарифмирование
- Тригонометрическое → обратные функции + период

**3. Проверка**
- Подставь ответ в исходное уравнение
- Обе части равны? Отлично!

К какому типу относится твоё уравнение?""",
        min_difficulty=Difficulty.EASY,
        topics=["equations", "algebra"]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # Error Analysis Templates
    # ─────────────────────────────────────────────────────────────────────────────
    "error_analysis_cot": CoTTemplate(
        id="error_analysis_cot",
        type=CoTType.ERROR_ANALYSIS,
        name_ru="Анализ ошибки",
        template="""Давай разберём, где произошла ошибка:

**1. Проверка шагов**
- Посмотрим на твоё решение по шагам
- На каком шаге результат стал отличаться от ожидаемого?

**2. Типичные ошибки**
- Знаковые ошибки при раскрытии скобок
- Забытый коэффициент при дифференцировании
- Неправильное применение правила
- Арифметическая ошибка

**3. Исправление**
- Вернись к шагу, где произошла ошибка
- Выполни его заново, внимательно следя за деталями

Можешь показать мне свои промежуточные шаги?""",
        min_difficulty=Difficulty.EASY,
        topics=["general"]
    ),

    "chain_rule_error": CoTTemplate(
        id="chain_rule_error",
        type=CoTType.ERROR_ANALYSIS,
        name_ru="Ошибка в правиле цепочки",
        template="""Похоже, здесь проблема с правилом цепочки. Давай разберём:

**Правило цепочки:**
(f(g(x)))' = f'(g(x)) · g'(x)

**Типичные ошибки:**
1. Забыли умножить на производную внутренней функции g'(x)
2. Взяли производную внутренней функции по другой переменной
3. Перепутали порядок: нужно f'(g(x)), а не f'(x)

**Проверка:**
- Что у тебя внешняя функция f?
- Что внутренняя функция g?
- Чему равна g'(x)?

Попробуй ещё раз, помня про производную внутренней функции!""",
        min_difficulty=Difficulty.MEDIUM,
        topics=["derivatives", "chain_rule"]
    ),

    # ─────────────────────────────────────────────────────────────────────────────
    # Scaffolding Templates
    # ─────────────────────────────────────────────────────────────────────────────
    "gentle_scaffolding": CoTTemplate(
        id="gentle_scaffolding",
        type=CoTType.SCAFFOLDING,
        name_ru="Мягкое направление",
        template="""Хороший ход мысли! Давай разовьём эту идею:

**Ты начал правильно:**
- {correct_part}

**Следующий шаг:**
- Подумай: {hint}
- Какой метод здесь подойдёт?

**Вопрос для размышления:**
{question}

Попробуй продолжить с этой подсказкой!""",
        min_difficulty=Difficulty.EASY,
        topics=["general"]
    ),

    "stuck_scaffolding": CoTTemplate(
        id="stuck_scaffolding",
        type=CoTType.SCAFFOLDING,
        name_ru="Помощь при затруднении",
        template="""Вижу, что задача вызывает затруднения. Давай подойдём иначе:

**Упростим задачу:**
- Начнём с более простого случая: {simple_case}
- Что мы знаем точно: {known}

**Ключевой вопрос:**
{key_question}

**Подсказка:**
{hint}

Попробуй ответить на ключевой вопрос, и это поможет двигаться дальше!""",
        min_difficulty=Difficulty.EASY,
        topics=["general"]
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# COT MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class CoTManager:
    """
    Manager for Chain-of-Thought templates.

    Selects appropriate CoT template based on:
    - Problem type/topic
    - Difficulty level
    - Student state (stuck, error, progressing)
    """

    def __init__(self, enabled: bool = None):
        self.enabled = enabled if enabled is not None else COT_ENABLED
        self.min_difficulty = Difficulty.from_string(COT_MIN_DIFFICULTY)

        logger.info(
            f"CoTManager initialized: enabled={self.enabled}, "
            f"min_difficulty={self.min_difficulty.value}"
        )

    def should_use_cot(
        self,
        difficulty: str,
        force: bool = False
    ) -> bool:
        """
        Check if CoT should be used for this task.

        Args:
            difficulty: Task difficulty (easy/medium/hard)
            force: Force use regardless of difficulty

        Returns:
            True if CoT should be used
        """
        if not self.enabled:
            return False

        if force:
            return True

        task_difficulty = Difficulty.from_string(difficulty)
        return task_difficulty >= self.min_difficulty

    def get_template(
        self,
        template_id: str
    ) -> Optional[CoTTemplate]:
        """Get template by ID."""
        return COT_TEMPLATES.get(template_id)

    def select_template(
        self,
        topic: str,
        cot_type: CoTType = CoTType.PROBLEM_SOLVING,
        difficulty: str = "medium"
    ) -> Optional[CoTTemplate]:
        """
        Select best template for given context.

        Args:
            topic: Math topic
            cot_type: Type of CoT needed
            difficulty: Task difficulty

        Returns:
            Best matching template or None
        """
        task_difficulty = Difficulty.from_string(difficulty)

        # Find matching templates
        candidates = []
        for template in COT_TEMPLATES.values():
            # Check type match
            if template.type != cot_type:
                continue

            # Check difficulty
            if task_difficulty < template.min_difficulty:
                continue

            # Check topic match
            topic_match = (
                not template.topics or
                "general" in template.topics or
                any(t in topic.lower() for t in template.topics)
            )

            if topic_match:
                candidates.append(template)

        if not candidates:
            # Return general template as fallback
            return COT_TEMPLATES.get("solve_step_by_step")

        # Prefer topic-specific over general
        for template in candidates:
            if "general" not in template.topics:
                return template

        return candidates[0]

    def format_template(
        self,
        template: CoTTemplate,
        variables: Dict[str, str]
    ) -> str:
        """
        Format template with variables.

        Args:
            template: Template to format
            variables: Variables to substitute

        Returns:
            Formatted template string
        """
        result = template.template

        for key, value in variables.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, value)

        # Remove unfilled placeholders
        import re
        result = re.sub(r'\{[^}]+\}', '', result)

        return result

    def get_problem_solving_cot(
        self,
        topic: str,
        given: str = "",
        find: str = "",
        methods: str = ""
    ) -> str:
        """
        Get problem-solving CoT for a topic.

        Args:
            topic: Math topic
            given: What is given
            find: What to find
            methods: Suggested methods

        Returns:
            Formatted CoT prompt
        """
        # Try topic-specific template first
        topic_templates = {
            "derivatives": "derivative_cot",
            "integrals": "integral_cot",
            "limits": "limit_cot",
            "equations": "equation_cot",
        }

        template_id = None
        for key, tid in topic_templates.items():
            if key in topic.lower():
                template_id = tid
                break

        template = self.get_template(template_id) if template_id else None
        if not template:
            template = self.get_template("solve_step_by_step")

        return self.format_template(template, {
            "given": given or "условие задачи",
            "find": find or "результат",
            "methods": methods or "стандартные методы",
        })

    def get_error_analysis_cot(
        self,
        error_type: Optional[str] = None
    ) -> str:
        """
        Get error analysis CoT.

        Args:
            error_type: Type of error (e.g., "chain_rule")

        Returns:
            Formatted CoT prompt for error analysis
        """
        if error_type == "chain_rule":
            template = self.get_template("chain_rule_error")
        else:
            template = self.get_template("error_analysis_cot")

        return template.template if template else ""

    def get_scaffolding_cot(
        self,
        is_stuck: bool = False,
        correct_part: str = "",
        hint: str = "",
        question: str = ""
    ) -> str:
        """
        Get scaffolding CoT.

        Args:
            is_stuck: Student is stuck
            correct_part: What they did correctly
            hint: Hint to give
            question: Question to ask

        Returns:
            Formatted scaffolding prompt
        """
        template_id = "stuck_scaffolding" if is_stuck else "gentle_scaffolding"
        template = self.get_template(template_id)

        return self.format_template(template, {
            "correct_part": correct_part or "начальная идея",
            "hint": hint or "подумай о методе решения",
            "question": question or "Что ты уже знаешь о этом типе задач?",
            "simple_case": "простой пример",
            "known": "базовые формулы",
            "key_question": question or "Какой первый шаг нужно сделать?",
        })


# Global instance
_cot_manager: Optional[CoTManager] = None


def get_cot_manager() -> CoTManager:
    """Get or create global CoT manager."""
    global _cot_manager
    if _cot_manager is None:
        _cot_manager = CoTManager()
    return _cot_manager


def should_use_cot(difficulty: str) -> bool:
    """Check if CoT should be used."""
    return get_cot_manager().should_use_cot(difficulty)


def get_cot_prompt(
    topic: str,
    difficulty: str = "medium",
    cot_type: str = "problem_solving"
) -> str:
    """
    Convenience function to get CoT prompt.

    Args:
        topic: Math topic
        difficulty: Task difficulty
        cot_type: Type of CoT

    Returns:
        CoT prompt string
    """
    manager = get_cot_manager()

    if not manager.should_use_cot(difficulty):
        return ""

    type_map = {
        "problem_solving": CoTType.PROBLEM_SOLVING,
        "error_analysis": CoTType.ERROR_ANALYSIS,
        "scaffolding": CoTType.SCAFFOLDING,
    }

    cot_enum = type_map.get(cot_type, CoTType.PROBLEM_SOLVING)
    template = manager.select_template(topic, cot_enum, difficulty)

    if template:
        return template.template

    return ""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== CoT Templates Demo ===\n")

    manager = CoTManager()

    # Test problem solving
    print("Problem Solving CoT for derivatives:")
    print(manager.get_problem_solving_cot("derivatives"))

    print("\n" + "="*50 + "\n")

    # Test error analysis
    print("Chain rule error CoT:")
    print(manager.get_error_analysis_cot("chain_rule"))

    print("\n" + "="*50 + "\n")

    # Test scaffolding
    print("Scaffolding CoT:")
    print(manager.get_scaffolding_cot(
        is_stuck=True,
        hint="Попробуй применить формулу производной произведения"
    ))
