"""
Code Executor — Безопасное выполнение кода

Песочница для запуска Python кода студентов с:
- Ограничением времени выполнения
- Блокировкой опасных операций
- Захватом stdout/stderr
- Анализом ошибок
"""

import subprocess
import sys
import os
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import ast
import time


class ExecutionStatus(Enum):
    SUCCESS = "success"
    WRONG_ANSWER = "wrong_answer"
    RUNTIME_ERROR = "runtime_error"
    TIME_LIMIT = "time_limit"
    MEMORY_LIMIT = "memory_limit"
    COMPILATION_ERROR = "compilation_error"
    SECURITY_ERROR = "security_error"


@dataclass
class TestCase:
    """Тестовый случай."""
    input: str
    expected_output: str
    is_hidden: bool = False
    description: str = ""


@dataclass
class ExecutionResult:
    """Результат выполнения кода."""
    status: ExecutionStatus
    output: str = ""
    expected: str = ""
    error: str = ""
    execution_time_ms: float = 0
    memory_mb: float = 0
    test_number: int = 0
    
    @property
    def is_correct(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS


@dataclass
class SubmissionResult:
    """Результат проверки решения."""
    passed: int = 0
    total: int = 0
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    results: List[ExecutionResult] = field(default_factory=list)
    first_failed: Optional[ExecutionResult] = None
    
    @property
    def is_accepted(self) -> bool:
        return self.passed == self.total and self.total > 0
    
    @property
    def score(self) -> float:
        return self.passed / self.total if self.total > 0 else 0


# Запрещённые модули
FORBIDDEN_IMPORTS = {
    'os', 'sys', 'subprocess', 'socket', 'requests', 'urllib',
    'http', 'ftplib', 'smtplib', 'telnetlib', 'ssl',
    'ctypes', 'multiprocessing', 'threading',
    'pickle', 'shelve', 'dbm', 'sqlite3',
    'importlib', 'shutil', 'glob', 'pathlib',
}

FORBIDDEN_BUILTINS = {
    '__import__', 'exec', 'eval', 'compile', 'open',
    'breakpoint', 'help', 'credits', 'license', 'exit', 'quit',
}


class CodeSecurityChecker:
    """Проверка безопасности кода перед выполнением."""
    
    @staticmethod
    def check_code(code: str) -> Tuple[bool, str]:
        """
        Проверить код на безопасность.
        
        Returns:
            (is_safe, error_message)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: строка {e.lineno}: {e.msg}"
        
        for node in ast.walk(tree):
            # Проверка импортов
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module in FORBIDDEN_IMPORTS:
                        return False, f"Запрещённый импорт: {module}"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split('.')[0]
                    if module in FORBIDDEN_IMPORTS:
                        return False, f"Запрещённый импорт: {module}"
            
            # Проверка вызовов опасных функций
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in FORBIDDEN_BUILTINS:
                        return False, f"Запрещённая функция: {node.func.id}"
        
        return True, ""


class CodeExecutor:
    """
    Безопасный исполнитель Python кода.
    """
    
    def __init__(
        self,
        timeout_seconds: float = 5.0,
        memory_limit_mb: int = 128
    ):
        self.timeout = timeout_seconds
        self.memory_limit = memory_limit_mb
        self.security_checker = CodeSecurityChecker()
    
    def execute(
        self,
        code: str,
        input_data: str = "",
        timeout: Optional[float] = None
    ) -> ExecutionResult:
        """
        Выполнить код с заданным входом.
        """
        timeout = timeout or self.timeout
        
        # Проверка безопасности
        is_safe, error = self.security_checker.check_code(code)
        if not is_safe:
            return ExecutionResult(
                status=ExecutionStatus.SECURITY_ERROR,
                error=error
            )
        
        # Создаём временный файл с кодом
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            start_time = time.time()
            
            # Запускаем в отдельном процессе
            result = subprocess.run(
                [sys.executable, temp_file],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    **os.environ,
                    'PYTHONDONTWRITEBYTECODE': '1',
                    'PYTHONIOENCODING': 'utf-8'
                }
            )
            
            execution_time = (time.time() - start_time) * 1000  # мс
            
            if result.returncode == 0:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    output=result.stdout.strip(),
                    execution_time_ms=execution_time
                )
            else:
                # Парсим ошибку
                error_text = result.stderr.strip()
                # Убираем путь к временному файлу
                error_text = error_text.replace(temp_file, "solution.py")
                
                return ExecutionResult(
                    status=ExecutionStatus.RUNTIME_ERROR,
                    output=result.stdout.strip(),
                    error=error_text,
                    execution_time_ms=execution_time
                )
                
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                status=ExecutionStatus.TIME_LIMIT,
                error=f"Превышено время выполнения ({timeout} сек)"
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.RUNTIME_ERROR,
                error=str(e)
            )
        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def run_tests(
        self,
        code: str,
        test_cases: List[TestCase],
        stop_on_first_fail: bool = False
    ) -> SubmissionResult:
        """
        Запустить код на наборе тестов.
        """
        result = SubmissionResult(total=len(test_cases))
        
        for i, test in enumerate(test_cases, 1):
            exec_result = self.execute(code, test.input)
            exec_result.test_number = i
            exec_result.expected = test.expected_output
            
            # Сравниваем вывод
            if exec_result.status == ExecutionStatus.SUCCESS:
                if self._compare_output(exec_result.output, test.expected_output):
                    result.passed += 1
                else:
                    exec_result.status = ExecutionStatus.WRONG_ANSWER
                    if result.first_failed is None:
                        result.first_failed = exec_result
                    result.status = ExecutionStatus.WRONG_ANSWER
            else:
                if result.first_failed is None:
                    result.first_failed = exec_result
                result.status = exec_result.status
            
            result.results.append(exec_result)
            
            if stop_on_first_fail and not exec_result.is_correct:
                break
        
        if result.passed == result.total:
            result.status = ExecutionStatus.SUCCESS
        
        return result
    
    def _compare_output(self, actual: str, expected: str) -> bool:
        """Сравнить вывод с ожидаемым."""
        actual_lines = [line.rstrip() for line in actual.strip().split('\n')]
        expected_lines = [line.rstrip() for line in expected.strip().split('\n')]
        return actual_lines == expected_lines


class ErrorAnalyzer:
    """Анализатор ошибок выполнения для подсказок."""
    
    ERROR_PATTERNS = {
        "ZeroDivisionError": {
            "ru": "Деление на ноль",
            "hint": "Проверьте, не делите ли вы на ноль. Добавьте проверку делителя.",
            "example": "if divisor != 0:\n    result = a / divisor"
        },
        "IndexError": {
            "ru": "Выход за границы",
            "hint": "Индекс выходит за границы списка. Проверьте длину перед доступом.",
            "example": "if 0 <= i < len(arr):\n    value = arr[i]"
        },
        "KeyError": {
            "ru": "Ключ не найден",
            "hint": "Ключ не найден в словаре. Используйте .get() или проверку 'in'.",
            "example": "value = d.get(key, default_value)\n# или\nif key in d:\n    value = d[key]"
        },
        "TypeError": {
            "ru": "Ошибка типа",
            "hint": "Несовместимые типы данных. Проверьте типы операндов.",
            "example": "# Преобразуйте типы:\nint(x), str(x), float(x)"
        },
        "ValueError": {
            "ru": "Ошибка значения",
            "hint": "Неверное значение. Проверьте входные данные.",
            "example": "# Проверьте формат:\nif value.isdigit():\n    num = int(value)"
        },
        "RecursionError": {
            "ru": "Бесконечная рекурсия",
            "hint": "Рекурсия не завершается. Проверьте базовый случай.",
            "example": "def func(n):\n    if n <= 1:  # базовый случай!\n        return 1\n    return func(n-1)"
        },
        "NameError": {
            "ru": "Переменная не определена",
            "hint": "Переменная не определена. Проверьте имя и область видимости.",
            "example": "# Определите переменную перед использованием:\nx = 0\nprint(x)"
        },
        "AttributeError": {
            "ru": "Атрибут не найден",
            "hint": "У объекта нет такого атрибута. Проверьте тип объекта.",
            "example": "# Проверьте тип:\nif isinstance(obj, list):\n    obj.append(x)"
        },
        "IndentationError": {
            "ru": "Ошибка отступов",
            "hint": "Неверные отступы. Используйте 4 пробела для каждого уровня.",
            "example": "def func():\n    if True:      # 4 пробела\n        print()   # 8 пробелов"
        },
    }
    
    @classmethod
    def analyze(cls, error: str) -> Dict[str, str]:
        """Проанализировать ошибку и дать подсказку."""
        for pattern, advice in cls.ERROR_PATTERNS.items():
            if pattern in error:
                # Извлекаем номер строки если есть
                line_num = ""
                if "line " in error.lower():
                    try:
                        import re
                        match = re.search(r'line (\d+)', error.lower())
                        if match:
                            line_num = f" (строка {match.group(1)})"
                    except:
                        pass
                
                return {
                    "type": advice["ru"] + line_num,
                    "hint": advice["hint"],
                    "example": advice["example"],
                    "original": error
                }
        
        return {
            "type": "Ошибка выполнения",
            "hint": "Внимательно прочитайте сообщение об ошибке.",
            "example": "",
            "original": error
        }
    
    @classmethod
    def analyze_wrong_answer(
        cls,
        actual: str,
        expected: str,
        test_input: str = ""
    ) -> Dict[str, Any]:
        """Проанализировать неправильный ответ."""
        actual_lines = actual.strip().split('\n') if actual.strip() else []
        expected_lines = expected.strip().split('\n') if expected.strip() else []
        
        hints = []
        
        # Пустой вывод
        if not actual_lines:
            hints.append("Ваша программа ничего не вывела. Добавьте print().")
            return {
                "type": "Нет вывода",
                "hints": hints,
                "diff": None
            }
        
        # Разная длина вывода
        if len(actual_lines) != len(expected_lines):
            hints.append(
                f"Количество строк: {len(actual_lines)}, ожидалось: {len(expected_lines)}"
            )
        
        # Находим первое различие
        diff_line = None
        for i, (a, e) in enumerate(zip(actual_lines, expected_lines)):
            a = a.rstrip()
            e = e.rstrip()
            if a != e:
                diff_line = i + 1
                hints.append(f"Строка {i+1}: получено `{a}`, ожидалось `{e}`")
                
                # Проверяем типичные проблемы
                if a.lower() == e.lower():
                    hints.append("💡 Проверьте регистр букв (заглавные/строчные)")
                elif a.replace(" ", "") == e.replace(" ", ""):
                    hints.append("💡 Лишние или недостающие пробелы")
                elif a.replace(",", ".") == e or a.replace(".", ",") == e:
                    hints.append("💡 Проверьте разделитель дробной части (точка/запятая)")
                
                break
        
        return {
            "type": "Неверный ответ",
            "hints": hints,
            "diff_line": diff_line,
            "actual_preview": actual_lines[:3],
            "expected_preview": expected_lines[:3]
        }
