"""
Code Analyzer — Статический анализ кода студента

Анализирует код на:
- Стилистические проблемы
- Потенциальные ошибки
- Неоптимальные паттерны
- Сложность алгоритма
"""

import ast
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class IssueLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUGGESTION = "suggestion"


@dataclass
class CodeIssue:
    """Проблема в коде."""
    level: IssueLevel
    line: int
    message: str
    suggestion: str = ""
    code_snippet: str = ""


@dataclass
class ComplexityAnalysis:
    """Анализ сложности."""
    time_complexity: str
    space_complexity: str
    explanation: str
    has_recursion: bool = False
    has_nested_loops: bool = False
    loop_depth: int = 0


@dataclass
class CodeMetrics:
    """Метрики кода."""
    lines_of_code: int
    functions: int
    classes: int
    imports: int
    comments: int
    max_nesting: int
    cyclomatic_complexity: int


class CodeAnalyzer:
    """Анализатор Python кода."""

    # Паттерны неоптимального кода
    ANTIPATTERNS = [
        {
            "pattern": r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(",
            "message": "Используйте enumerate() вместо range(len())",
            "suggestion": "for i, item in enumerate(lst):",
            "level": IssueLevel.SUGGESTION
        },
        {
            "pattern": r"==\s*True|==\s*False",
            "message": "Избыточное сравнение с True/False",
            "suggestion": "Используйте: if condition: или if not condition:",
            "level": IssueLevel.SUGGESTION
        },
        {
            "pattern": r"except\s*:",
            "message": "Слишком широкий except — ловит все исключения",
            "suggestion": "Указывайте конкретный тип: except ValueError:",
            "level": IssueLevel.WARNING
        },
        {
            "pattern": r"\.append\([^)]+\)\s*$",
            "message": "Возможно, list comprehension будет эффективнее",
            "suggestion": "[x for x in items if condition]",
            "level": IssueLevel.INFO
        },
        {
            "pattern": r"if\s+\w+\s*==\s*\[\]|if\s+\w+\s*==\s*\"\"",
            "message": "Используйте 'if not lst:' для проверки пустоты",
            "suggestion": "if not my_list: или if not my_string:",
            "level": IssueLevel.SUGGESTION
        },
        {
            "pattern": r"print\s*\([^)]*\)\s*$",
            "message": "print() внутри функции — возможно, лучше return",
            "level": IssueLevel.INFO
        },
    ]

    # Паттерны потенциальных ошибок
    ERROR_PATTERNS = [
        {
            "pattern": r"=\s*\[\]\s*\*\s*\d+",
            "message": "Создание списка списков через * создаёт ссылки на один объект!",
            "suggestion": "Используйте: [[0] * n for _ in range(m)]",
            "level": IssueLevel.ERROR
        },
        {
            "pattern": r"def\s+\w+\s*\([^)]*=\s*\[\]",
            "message": "Мутабельный аргумент по умолчанию — опасно!",
            "suggestion": "Используйте None и создавайте внутри: if arg is None: arg = []",
            "level": IssueLevel.ERROR
        },
        {
            "pattern": r"global\s+",
            "message": "Использование global — плохая практика",
            "suggestion": "Передавайте значения через параметры и return",
            "level": IssueLevel.WARNING
        },
    ]

    def __init__(self):
        self.issues: List[CodeIssue] = []

    def analyze(self, code: str) -> Dict[str, Any]:
        """
        Полный анализ кода.
        
        Returns:
            {
                "issues": List[CodeIssue],
                "metrics": CodeMetrics,
                "complexity": ComplexityAnalysis,
                "summary": str
            }
        """
        self.issues = []

        # Базовые проверки
        self._check_patterns(code)

        # AST анализ
        try:
            tree = ast.parse(code)
            self._analyze_ast(tree, code)
            metrics = self._compute_metrics(tree, code)
            complexity = self._analyze_complexity(tree)
        except SyntaxError as e:
            self.issues.append(CodeIssue(
                level=IssueLevel.ERROR,
                line=e.lineno or 0,
                message=f"Синтаксическая ошибка: {e.msg}",
                suggestion="Проверьте синтаксис: скобки, кавычки, двоеточия"
            ))
            metrics = self._empty_metrics(code)
            complexity = self._empty_complexity()

        summary = self._generate_summary(metrics, complexity)

        return {
            "issues": self.issues,
            "metrics": metrics,
            "complexity": complexity,
            "summary": summary
        }

    def _check_patterns(self, code: str):
        """Проверка паттернов в коде."""
        lines = code.split('\n')

        for patterns in [self.ANTIPATTERNS, self.ERROR_PATTERNS]:
            for p in patterns:
                for i, line in enumerate(lines, 1):
                    if re.search(p["pattern"], line):
                        self.issues.append(CodeIssue(
                            level=p["level"],
                            line=i,
                            message=p["message"],
                            suggestion=p.get("suggestion", ""),
                            code_snippet=line.strip()
                        ))

    def _analyze_ast(self, tree: ast.AST, code: str):
        """AST анализ."""
        lines = code.split('\n')

        for node in ast.walk(tree):
            # Проверка неиспользуемых переменных в циклах
            if isinstance(node, ast.For):
                if isinstance(node.target, ast.Name):
                    var_name = node.target.id
                    if var_name.startswith('_'):
                        continue
                    # Проверяем, используется ли переменная в теле
                    body_names = {n.id for n in ast.walk(node)
                                  if isinstance(n, ast.Name) and n.id == var_name}
                    if len(body_names) <= 1:  # Только в определении
                        self.issues.append(CodeIssue(
                            level=IssueLevel.INFO,
                            line=node.lineno,
                            message=f"Переменная '{var_name}' не используется в цикле",
                            suggestion="Используйте _ для неиспользуемых переменных"
                        ))

            # Проверка пустых except
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    self.issues.append(CodeIssue(
                        level=IssueLevel.WARNING,
                        line=node.lineno,
                        message="Пустой except ловит все исключения, включая KeyboardInterrupt",
                        suggestion="Используйте except Exception: для обычных ошибок"
                    ))

            # Проверка сравнения с None
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    if isinstance(op, (ast.Eq, ast.NotEq)):
                        for comp in node.comparators:
                            if isinstance(comp, ast.Constant) and comp.value is None:
                                self.issues.append(CodeIssue(
                                    level=IssueLevel.SUGGESTION,
                                    line=node.lineno,
                                    message="Используйте 'is None' вместо '== None'",
                                    suggestion="if x is None: или if x is not None:"
                                ))

            # Проверка рекурсии без базового случая
            if isinstance(node, ast.FunctionDef):
                has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
                has_recursive_call = any(
                    isinstance(n, ast.Call) and
                    isinstance(n.func, ast.Name) and
                    n.func.id == node.name
                    for n in ast.walk(node)
                )

                if has_recursive_call:
                    # Проверяем наличие условного return
                    has_base_case = any(
                        isinstance(n, ast.If) and
                        any(isinstance(child, ast.Return) for child in ast.walk(n))
                        for n in ast.walk(node)
                    )

                    if not has_base_case:
                        self.issues.append(CodeIssue(
                            level=IssueLevel.WARNING,
                            line=node.lineno,
                            message=f"Рекурсивная функция '{node.name}' без явного базового случая",
                            suggestion="Добавьте условие выхода: if n <= 1: return ..."
                        ))

    def _compute_metrics(self, tree: ast.AST, code: str) -> CodeMetrics:
        """Вычисление метрик кода."""
        lines = code.split('\n')

        # Подсчёт строк кода (без пустых и комментариев)
        loc = sum(1 for line in lines if line.strip() and not line.strip().startswith('#'))

        # Подсчёт комментариев
        comments = sum(1 for line in lines if line.strip().startswith('#'))

        # AST метрики
        functions = sum(1 for _ in ast.walk(tree) if isinstance(_, ast.FunctionDef))
        classes = sum(1 for _ in ast.walk(tree) if isinstance(_, ast.ClassDef))
        imports = sum(1 for _ in ast.walk(tree) if isinstance(_, (ast.Import, ast.ImportFrom)))

        # Максимальная вложенность
        max_nesting = self._compute_max_nesting(tree)

        # Цикломатическая сложность
        cyclomatic = self._compute_cyclomatic(tree)

        return CodeMetrics(
            lines_of_code=loc,
            functions=functions,
            classes=classes,
            imports=imports,
            comments=comments,
            max_nesting=max_nesting,
            cyclomatic_complexity=cyclomatic
        )

    def _compute_max_nesting(self, tree: ast.AST) -> int:
        """Вычисление максимальной вложенности."""
        def get_depth(node, current=0):
            max_depth = current
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                    max_depth = max(max_depth, get_depth(child, current + 1))
                else:
                    max_depth = max(max_depth, get_depth(child, current))
            return max_depth

        return get_depth(tree)

    def _compute_cyclomatic(self, tree: ast.AST) -> int:
        """Вычисление цикломатической сложности."""
        complexity = 1  # Базовая сложность

        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1

        return complexity

    def _analyze_complexity(self, tree: ast.AST) -> ComplexityAnalysis:
        """Анализ сложности алгоритма."""
        has_recursion = False
        has_nested_loops = False
        max_loop_depth = 0

        # Поиск рекурсии
        function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in function_names:
                    has_recursion = True

        # Анализ циклов
        def analyze_loops(node, depth=0):
            nonlocal max_loop_depth, has_nested_loops

            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.For, ast.While)):
                    new_depth = depth + 1
                    max_loop_depth = max(max_loop_depth, new_depth)
                    if new_depth >= 2:
                        has_nested_loops = True
                    analyze_loops(child, new_depth)
                else:
                    analyze_loops(child, depth)

        analyze_loops(tree)

        # Определение сложности
        if has_recursion:
            time_complexity = "O(?) — требуется анализ рекурсии"
            explanation = "Код содержит рекурсию. Сложность зависит от глубины и ветвления."
        elif max_loop_depth == 0:
            time_complexity = "O(1)"
            explanation = "Нет циклов — константная сложность."
        elif max_loop_depth == 1:
            time_complexity = "O(n)"
            explanation = "Один уровень циклов — линейная сложность."
        elif max_loop_depth == 2:
            time_complexity = "O(n²)"
            explanation = "Вложенные циклы — квадратичная сложность."
        else:
            time_complexity = f"O(n^{max_loop_depth})"
            explanation = f"Глубина вложенности {max_loop_depth} — полиномиальная сложность."

        # Пространственная сложность (упрощённо)
        has_list_creation = any(
            isinstance(node, ast.ListComp) or
            (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'list')
            for node in ast.walk(tree)
        )

        space_complexity = "O(n)" if has_list_creation else "O(1)"

        return ComplexityAnalysis(
            time_complexity=time_complexity,
            space_complexity=space_complexity,
            explanation=explanation,
            has_recursion=has_recursion,
            has_nested_loops=has_nested_loops,
            loop_depth=max_loop_depth
        )

    def _empty_metrics(self, code: str) -> CodeMetrics:
        """Пустые метрики при ошибке парсинга."""
        lines = code.split('\n')
        return CodeMetrics(
            lines_of_code=len([l for l in lines if l.strip()]),
            functions=0, classes=0, imports=0, comments=0,
            max_nesting=0, cyclomatic_complexity=1
        )

    def _empty_complexity(self) -> ComplexityAnalysis:
        """Пустой анализ сложности при ошибке."""
        return ComplexityAnalysis(
            time_complexity="?",
            space_complexity="?",
            explanation="Невозможно проанализировать из-за синтаксической ошибки"
        )

    def _generate_summary(self, metrics: CodeMetrics, complexity: ComplexityAnalysis) -> str:
        """Генерация текстового резюме."""
        summary = []

        # Сложность
        summary.append(f"⏱️ **Временная сложность:** {complexity.time_complexity}")
        summary.append(f"💾 **Пространственная сложность:** {complexity.space_complexity}")

        # Особенности
        if complexity.has_recursion:
            summary.append("🔄 Использует рекурсию")
        if complexity.has_nested_loops:
            summary.append(f"🔁 Вложенные циклы (глубина: {complexity.loop_depth})")

        # Метрики
        summary.append("\n📊 **Метрики:**")
        summary.append(f"   • Строк кода: {metrics.lines_of_code}")
        summary.append(f"   • Функций: {metrics.functions}")
        summary.append(f"   • Цикломатическая сложность: {metrics.cyclomatic_complexity}")

        # Проблемы
        errors = [i for i in self.issues if i.level == IssueLevel.ERROR]
        warnings = [i for i in self.issues if i.level == IssueLevel.WARNING]
        suggestions = [i for i in self.issues if i.level == IssueLevel.SUGGESTION]

        if errors:
            summary.append(f"\n❌ **Ошибки:** {len(errors)}")
        if warnings:
            summary.append(f"⚠️ **Предупреждения:** {len(warnings)}")
        if suggestions:
            summary.append(f"💡 **Рекомендации:** {len(suggestions)}")

        return "\n".join(summary)

    def get_formatted_issues(self) -> str:
        """Форматированный список проблем."""
        if not self.issues:
            return "✅ Проблем не обнаружено"

        output = []

        for issue in sorted(self.issues, key=lambda x: (x.line, x.level.value)):
            emoji = {
                IssueLevel.ERROR: "❌",
                IssueLevel.WARNING: "⚠️",
                IssueLevel.SUGGESTION: "💡",
                IssueLevel.INFO: "ℹ️"
            }[issue.level]

            output.append(f"{emoji} **Строка {issue.line}:** {issue.message}")

            if issue.suggestion:
                output.append(f"   → {issue.suggestion}")

            if issue.code_snippet:
                output.append(f"   `{issue.code_snippet[:60]}`")

        return "\n".join(output)


class SolutionComparer:
    """Сравнение решения студента с эталонным."""

    @staticmethod
    def compare(student_code: str, reference_code: str) -> Dict[str, Any]:
        """
        Сравнить два решения.
        
        Returns:
            {
                "similarity": float (0-1),
                "student_complexity": str,
                "reference_complexity": str,
                "is_optimal": bool,
                "feedback": str
            }
        """
        analyzer = CodeAnalyzer()

        student_analysis = analyzer.analyze(student_code)
        analyzer.issues = []
        reference_analysis = analyzer.analyze(reference_code)

        student_cx = student_analysis["complexity"]
        reference_cx = reference_analysis["complexity"]

        # Сравнение сложности (упрощённо)
        complexity_order = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n²)", "O(n³)", "O(2^n)"]

        def get_order(cx: str) -> int:
            for i, c in enumerate(complexity_order):
                if c in cx:
                    return i
            return len(complexity_order)

        student_order = get_order(student_cx.time_complexity)
        reference_order = get_order(reference_cx.time_complexity)

        is_optimal = student_order <= reference_order

        # Обратная связь
        if is_optimal:
            feedback = "✅ Ваше решение оптимально по сложности!"
        elif student_order == reference_order + 1:
            feedback = "⚠️ Решение работает, но можно оптимизировать на один порядок."
        else:
            feedback = f"❌ Решение неоптимально. Эталон: {reference_cx.time_complexity}, ваше: {student_cx.time_complexity}"

        return {
            "student_complexity": student_cx.time_complexity,
            "reference_complexity": reference_cx.time_complexity,
            "is_optimal": is_optimal,
            "feedback": feedback,
            "student_metrics": student_analysis["metrics"],
            "reference_metrics": reference_analysis["metrics"]
        }
