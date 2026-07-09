"""
MITS Knowledge Graph

Skill graph with prerequisites for Learning Path Optimization.
Contains 40+ skills with prerequisite relationships.
"""

from typing import Dict, List, Set

from src.data.schemas import SkillNode

# ═══════════════════════════════════════════════════════════════════════════
# SKILL GRAPH DEFINITION
# ═══════════════════════════════════════════════════════════════════════════

SKILL_GRAPH: Dict[str, Dict] = {
    # ─────────────────────────────────────────────────────────────
    # Basic Math Skills
    # ─────────────────────────────────────────────────────────────
    "arithmetic": {
        "name": "Arithmetic",
        "name_ru": "Арифметика",
        "prerequisites": [],
        "difficulty": 0.1,
        "estimated_time_hours": 2.0,
        "category": "math"
    },
    "fractions": {
        "name": "Fractions",
        "name_ru": "Дроби",
        "prerequisites": ["arithmetic"],
        "difficulty": 0.2,
        "estimated_time_hours": 3.0,
        "category": "math"
    },
    "decimals": {
        "name": "Decimals",
        "name_ru": "Десятичные дроби",
        "prerequisites": ["arithmetic"],
        "difficulty": 0.2,
        "estimated_time_hours": 2.0,
        "category": "math"
    },
    "percentages": {
        "name": "Percentages",
        "name_ru": "Проценты",
        "prerequisites": ["fractions", "decimals"],
        "difficulty": 0.25,
        "estimated_time_hours": 2.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Algebra
    # ─────────────────────────────────────────────────────────────
    "variables": {
        "name": "Variables and Expressions",
        "name_ru": "Переменные и выражения",
        "prerequisites": ["arithmetic"],
        "difficulty": 0.25,
        "estimated_time_hours": 3.0,
        "category": "math"
    },
    "linear_equations": {
        "name": "Linear Equations",
        "name_ru": "Линейные уравнения",
        "prerequisites": ["variables"],
        "difficulty": 0.3,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "linear_inequalities": {
        "name": "Linear Inequalities",
        "name_ru": "Линейные неравенства",
        "prerequisites": ["linear_equations"],
        "difficulty": 0.35,
        "estimated_time_hours": 3.0,
        "category": "math"
    },
    "systems_of_equations": {
        "name": "Systems of Equations",
        "name_ru": "Системы уравнений",
        "prerequisites": ["linear_equations"],
        "difficulty": 0.4,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "quadratic_equations": {
        "name": "Quadratic Equations",
        "name_ru": "Квадратные уравнения",
        "prerequisites": ["linear_equations"],
        "difficulty": 0.45,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "factoring": {
        "name": "Factoring",
        "name_ru": "Разложение на множители",
        "prerequisites": ["quadratic_equations"],
        "difficulty": 0.5,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "polynomials": {
        "name": "Polynomials",
        "name_ru": "Многочлены",
        "prerequisites": ["factoring"],
        "difficulty": 0.55,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "rational_expressions": {
        "name": "Rational Expressions",
        "name_ru": "Рациональные выражения",
        "prerequisites": ["fractions", "polynomials"],
        "difficulty": 0.6,
        "estimated_time_hours": 4.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Trigonometry
    # ─────────────────────────────────────────────────────────────
    "trig_basics": {
        "name": "Trigonometric Basics",
        "name_ru": "Основы тригонометрии",
        "prerequisites": ["fractions", "quadratic_equations"],
        "difficulty": 0.45,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "trig_identities": {
        "name": "Trigonometric Identities",
        "name_ru": "Тригонометрические тождества",
        "prerequisites": ["trig_basics"],
        "difficulty": 0.55,
        "estimated_time_hours": 6.0,
        "category": "math"
    },
    "trig_equations": {
        "name": "Trigonometric Equations",
        "name_ru": "Тригонометрические уравнения",
        "prerequisites": ["trig_identities"],
        "difficulty": 0.6,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "inverse_trig": {
        "name": "Inverse Trigonometric Functions",
        "name_ru": "Обратные тригонометрические функции",
        "prerequisites": ["trig_identities"],
        "difficulty": 0.65,
        "estimated_time_hours": 4.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Functions
    # ─────────────────────────────────────────────────────────────
    "functions_basics": {
        "name": "Functions Basics",
        "name_ru": "Основы функций",
        "prerequisites": ["linear_equations"],
        "difficulty": 0.4,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "function_transformations": {
        "name": "Function Transformations",
        "name_ru": "Преобразования функций",
        "prerequisites": ["functions_basics"],
        "difficulty": 0.5,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "exponential_functions": {
        "name": "Exponential Functions",
        "name_ru": "Показательные функции",
        "prerequisites": ["functions_basics"],
        "difficulty": 0.55,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "logarithms": {
        "name": "Logarithms",
        "name_ru": "Логарифмы",
        "prerequisites": ["exponential_functions"],
        "difficulty": 0.6,
        "estimated_time_hours": 5.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Calculus - Limits & Continuity
    # ─────────────────────────────────────────────────────────────
    "limits_intuition": {
        "name": "Limits Intuition",
        "name_ru": "Интуитивное понимание пределов",
        "prerequisites": ["functions_basics", "rational_expressions"],
        "difficulty": 0.6,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "limits_formal": {
        "name": "Formal Limits",
        "name_ru": "Формальное определение предела",
        "prerequisites": ["limits_intuition"],
        "difficulty": 0.65,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "limits_techniques": {
        "name": "Limit Calculation Techniques",
        "name_ru": "Методы вычисления пределов",
        "prerequisites": ["limits_formal"],
        "difficulty": 0.7,
        "estimated_time_hours": 6.0,
        "category": "math"
    },
    "continuity": {
        "name": "Continuity",
        "name_ru": "Непрерывность",
        "prerequisites": ["limits_formal"],
        "difficulty": 0.65,
        "estimated_time_hours": 4.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Calculus - Derivatives
    # ─────────────────────────────────────────────────────────────
    "derivatives_definition": {
        "name": "Derivative Definition",
        "name_ru": "Определение производной",
        "prerequisites": ["limits_techniques"],
        "difficulty": 0.7,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "derivatives_basic": {
        "name": "Basic Derivatives",
        "name_ru": "Основные производные",
        "prerequisites": ["derivatives_definition"],
        "difficulty": 0.7,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "power_rule": {
        "name": "Power Rule",
        "name_ru": "Правило степени",
        "prerequisites": ["derivatives_basic"],
        "difficulty": 0.7,
        "estimated_time_hours": 2.0,
        "category": "math"
    },
    "product_rule": {
        "name": "Product Rule",
        "name_ru": "Правило произведения",
        "prerequisites": ["derivatives_basic"],
        "difficulty": 0.75,
        "estimated_time_hours": 3.0,
        "category": "math"
    },
    "quotient_rule": {
        "name": "Quotient Rule",
        "name_ru": "Правило частного",
        "prerequisites": ["product_rule"],
        "difficulty": 0.75,
        "estimated_time_hours": 3.0,
        "category": "math"
    },
    "chain_rule": {
        "name": "Chain Rule",
        "name_ru": "Правило цепочки",
        "prerequisites": ["product_rule"],
        "difficulty": 0.8,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "trig_derivatives": {
        "name": "Trigonometric Derivatives",
        "name_ru": "Производные тригонометрических функций",
        "prerequisites": ["chain_rule", "trig_identities"],
        "difficulty": 0.8,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "implicit_differentiation": {
        "name": "Implicit Differentiation",
        "name_ru": "Неявное дифференцирование",
        "prerequisites": ["chain_rule"],
        "difficulty": 0.85,
        "estimated_time_hours": 4.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Calculus - Applications of Derivatives
    # ─────────────────────────────────────────────────────────────
    "extrema": {
        "name": "Extrema (Min/Max)",
        "name_ru": "Экстремумы",
        "prerequisites": ["chain_rule"],
        "difficulty": 0.8,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "optimization": {
        "name": "Optimization Problems",
        "name_ru": "Задачи на оптимизацию",
        "prerequisites": ["extrema"],
        "difficulty": 0.85,
        "estimated_time_hours": 6.0,
        "category": "math"
    },
    "related_rates": {
        "name": "Related Rates",
        "name_ru": "Связанные скорости",
        "prerequisites": ["implicit_differentiation"],
        "difficulty": 0.85,
        "estimated_time_hours": 5.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Calculus - Integrals
    # ─────────────────────────────────────────────────────────────
    "antiderivatives": {
        "name": "Antiderivatives",
        "name_ru": "Первообразные",
        "prerequisites": ["derivatives_basic"],
        "difficulty": 0.75,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "definite_integrals": {
        "name": "Definite Integrals",
        "name_ru": "Определённые интегралы",
        "prerequisites": ["antiderivatives"],
        "difficulty": 0.8,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "fundamental_theorem": {
        "name": "Fundamental Theorem of Calculus",
        "name_ru": "Основная теорема анализа",
        "prerequisites": ["definite_integrals"],
        "difficulty": 0.8,
        "estimated_time_hours": 4.0,
        "category": "math"
    },
    "substitution": {
        "name": "Integration by Substitution",
        "name_ru": "Интегрирование заменой",
        "prerequisites": ["fundamental_theorem"],
        "difficulty": 0.85,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "integration_by_parts": {
        "name": "Integration by Parts",
        "name_ru": "Интегрирование по частям",
        "prerequisites": ["substitution"],
        "difficulty": 0.85,
        "estimated_time_hours": 5.0,
        "category": "math"
    },
    "trig_integrals": {
        "name": "Trigonometric Integrals",
        "name_ru": "Тригонометрические интегралы",
        "prerequisites": ["integration_by_parts", "trig_identities"],
        "difficulty": 0.9,
        "estimated_time_hours": 6.0,
        "category": "math"
    },

    # ─────────────────────────────────────────────────────────────
    # Programming Skills
    # ─────────────────────────────────────────────────────────────
    "python_basics": {
        "name": "Python Basics",
        "name_ru": "Основы Python",
        "prerequisites": [],
        "difficulty": 0.2,
        "estimated_time_hours": 10.0,
        "category": "programming"
    },
    "control_flow": {
        "name": "Control Flow",
        "name_ru": "Управляющие конструкции",
        "prerequisites": ["python_basics"],
        "difficulty": 0.3,
        "estimated_time_hours": 5.0,
        "category": "programming"
    },
    "functions_prog": {
        "name": "Functions (Programming)",
        "name_ru": "Функции (программирование)",
        "prerequisites": ["control_flow"],
        "difficulty": 0.35,
        "estimated_time_hours": 5.0,
        "category": "programming"
    },
    "data_structures": {
        "name": "Data Structures",
        "name_ru": "Структуры данных",
        "prerequisites": ["functions_prog"],
        "difficulty": 0.5,
        "estimated_time_hours": 8.0,
        "category": "programming"
    },
    "recursion": {
        "name": "Recursion",
        "name_ru": "Рекурсия",
        "prerequisites": ["functions_prog"],
        "difficulty": 0.6,
        "estimated_time_hours": 6.0,
        "category": "programming"
    },
    "sorting_algorithms": {
        "name": "Sorting Algorithms",
        "name_ru": "Алгоритмы сортировки",
        "prerequisites": ["data_structures", "recursion"],
        "difficulty": 0.6,
        "estimated_time_hours": 6.0,
        "category": "programming"
    },
    "search_algorithms": {
        "name": "Search Algorithms",
        "name_ru": "Алгоритмы поиска",
        "prerequisites": ["data_structures"],
        "difficulty": 0.55,
        "estimated_time_hours": 5.0,
        "category": "programming"
    },
    "complexity_analysis": {
        "name": "Complexity Analysis",
        "name_ru": "Анализ сложности",
        "prerequisites": ["sorting_algorithms"],
        "difficulty": 0.7,
        "estimated_time_hours": 6.0,
        "category": "programming"
    },
    "dynamic_programming": {
        "name": "Dynamic Programming",
        "name_ru": "Динамическое программирование",
        "prerequisites": ["recursion", "complexity_analysis"],
        "difficulty": 0.85,
        "estimated_time_hours": 10.0,
        "category": "programming"
    },
    "oop_basics": {
        "name": "OOP Basics",
        "name_ru": "Основы ООП",
        "prerequisites": ["functions_prog"],
        "difficulty": 0.5,
        "estimated_time_hours": 8.0,
        "category": "programming"
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# SKILL-ERROR MAPPING (for Counterfactual Explanations)
# ═══════════════════════════════════════════════════════════════════════════

SKILL_ERROR_MAPPING: Dict[str, Dict] = {
    "product_rule": {
        "error_patterns": [
            r"\(fg\)'\s*=\s*f'g'",
            r"производная произведения.*=.*производная.*\*.*производная",
            "forgot product rule",
        ],
        "counterfactual_template": "Если бы ты применил правило произведения (fg)' = f'g + fg', то получил бы {correct} вместо {wrong}.",
        "prerequisite_skills": ["derivatives_basic"],
    },
    "chain_rule": {
        "error_patterns": [
            r"d/dx\s*f\(g\(x\)\)\s*=\s*f'\(g\(x\)\)",
            r"не учёл внутреннюю функцию",
            "forgot chain rule",
            "missing inner derivative",
        ],
        "counterfactual_template": "Если бы ты применил правило цепочки d/dx[f(g(x))] = f'(g(x)) · g'(x), то получил бы {correct} вместо {wrong}.",
        "prerequisite_skills": ["product_rule", "derivatives_basic"],
    },
    "quotient_rule": {
        "error_patterns": [
            r"\(f/g\)'\s*=\s*f'/g'",
            r"производная частного.*неверно",
        ],
        "counterfactual_template": "Если бы ты применил правило частного (f/g)' = (f'g - fg')/g², то получил бы {correct} вместо {wrong}.",
        "prerequisite_skills": ["product_rule"],
    },
    "trig_identities": {
        "error_patterns": [
            r"sin\(a\+b\)\s*=\s*sin\(a\)\s*\+\s*sin\(b\)",
            r"cos\(a\+b\)\s*=\s*cos\(a\)\s*\+\s*cos\(b\)",
            r"sin².*\+.*cos².*≠.*1",
        ],
        "counterfactual_template": "Если бы ты использовал тригонометрическое тождество sin(a+b) = sin(a)cos(b) + cos(a)sin(b), то получил бы {correct}.",
        "prerequisite_skills": ["trig_basics"],
    },
    "substitution": {
        "error_patterns": [
            r"интеграл.*без замены",
            r"забыл поменять пределы",
            "missing du",
        ],
        "counterfactual_template": "Если бы ты сделал замену u = {substitution}, то интеграл упростился бы до {simplified}.",
        "prerequisite_skills": ["antiderivatives", "chain_rule"],
    },
    "integration_by_parts": {
        "error_patterns": [
            r"интеграл.*произведения.*без.*частей",
            "wrong choice for u and dv",
        ],
        "counterfactual_template": "Если бы ты применил интегрирование по частям с u = {u} и dv = {dv}, то получил бы {correct}.",
        "prerequisite_skills": ["substitution", "product_rule"],
    },
    "limits_techniques": {
        "error_patterns": [
            r"0/0.*без.*лопиталя",
            r"предел.*подстановкой.*неопределённость",
        ],
        "counterfactual_template": "Если бы ты применил правило Лопиталя при неопределённости {indeterminate}, то получил бы {correct}.",
        "prerequisite_skills": ["limits_formal", "derivatives_basic"],
    },
    "factoring": {
        "error_patterns": [
            r"не разложил.*на множители",
            r"квадратное.*без.*разложения",
        ],
        "counterfactual_template": "Если бы ты разложил {expression} на множители как {factored}, то решение упростилось бы.",
        "prerequisite_skills": ["quadratic_equations"],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_skill_node(skill_id: str) -> SkillNode:
    """Get a SkillNode object for a skill."""
    if skill_id not in SKILL_GRAPH:
        raise ValueError(f"Unknown skill: {skill_id}")

    data = SKILL_GRAPH[skill_id]
    return SkillNode(
        skill_id=skill_id,
        name=data["name"],
        name_ru=data.get("name_ru", data["name"]),
        prerequisites=data.get("prerequisites", []),
        difficulty=data.get("difficulty", 0.5),
        estimated_time_hours=data.get("estimated_time_hours", 2.0),
        category=data.get("category", "math"),
    )


def get_all_prerequisites(skill_id: str, visited: Set[str] = None) -> Set[str]:
    """Get all transitive prerequisites for a skill."""
    if visited is None:
        visited = set()

    if skill_id in visited:
        return visited

    if skill_id not in SKILL_GRAPH:
        return visited

    visited.add(skill_id)
    for prereq in SKILL_GRAPH[skill_id].get("prerequisites", []):
        get_all_prerequisites(prereq, visited)

    return visited - {skill_id}  # Don't include the skill itself


def get_skill_name_ru(skill_id: str) -> str:
    """Get Russian name for a skill."""
    if skill_id in SKILL_GRAPH:
        return SKILL_GRAPH[skill_id].get("name_ru", skill_id)
    return skill_id


def get_skills_by_category(category: str) -> List[str]:
    """Get all skills in a category."""
    return [
        skill_id
        for skill_id, data in SKILL_GRAPH.items()
        if data.get("category") == category
    ]
