#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Агент Верификатор - контроль качества ответов репетитора.

Проверяет:
- Отсутствие утечки ответов
- Валидность JSON формата
- Соблюдение сократического метода
- Использование LaTeX для формул
- Ответы на русском языке
"""

import json
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class QualityIssue(Enum):
    """Типы проблем качества."""
    ANSWER_LEAK = "answer_leak"           # Утечка ответа
    INVALID_JSON = "invalid_json"         # Невалидный JSON
    MISSING_QUESTION = "missing_question"  # Нет вопроса в ответе
    WRONG_MOVE = "wrong_move"             # Неподходящий ход
    NO_LATEX = "no_latex"                 # Нет LaTeX для формул
    WRONG_LANGUAGE = "wrong_language"     # Не русский язык
    TOO_DIRECT = "too_direct"             # Слишком прямое объяснение
    TOO_LONG = "too_long"                 # Слишком длинный ответ
    TOO_SHORT = "too_short"               # Слишком короткий ответ
    INAPPROPRIATE_TONE = "inappropriate"   # Неподходящий тон


class Severity(Enum):
    """Серьёзность проблемы."""
    CRITICAL = "critical"   # Блокирует ответ
    WARNING = "warning"     # Предупреждение
    INFO = "info"           # Информационное


@dataclass
class QualityCheck:
    """Результат одной проверки качества."""
    issue: QualityIssue
    severity: Severity
    message: str
    location: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class VerificationResult:
    """Результат верификации ответа."""
    is_valid: bool
    score: float  # 0.0 - 1.0
    checks: List[QualityCheck] = field(default_factory=list)
    corrected_response: Optional[str] = None

    @property
    def critical_issues(self) -> List[QualityCheck]:
        """Критические проблемы."""
        return [c for c in self.checks if c.severity == Severity.CRITICAL]

    @property
    def warnings(self) -> List[QualityCheck]:
        """Предупреждения."""
        return [c for c in self.checks if c.severity == Severity.WARNING]

    def summary(self) -> str:
        """Краткое описание результата."""
        if self.is_valid:
            return f"✅ Ответ валиден (score: {self.score:.2f})"
        else:
            issues = ", ".join([c.issue.value for c in self.critical_issues])
            return f"❌ Ответ невалиден: {issues}"


class VerifierAgent:
    """
    Агент для верификации качества ответов репетитора.

    Особенности:
    - Многоуровневая проверка (правила + LLM)
    - Детекция утечки ответов
    - Проверка сократического метода
    - Оценка качества с score
    """

    # Паттерны для детекции утечки ответов (ENHANCED)
    ANSWER_LEAK_PATTERNS = [
        # Прямые указания на ответ
        r'ответ[:\s]+[=]?\s*\$?-?\d+',           # "ответ: 5" или "ответ: $5$"
        r'равн[оа]\s+\$?-?\d+',                   # "равно 5"
        r'получ[аие][ем]\s+\$?-?\d+',             # "получаем 5"
        r'итого[:\s]+\$?-?\d+',                   # "итого: 5"
        r'результат[:\s]+\$?-?\d+',               # "результат: 5"
        r'x\s*=\s*-?\d+(?:\.\d+)?(?!\s*[+\-*/])',  # "x = 5" (не часть уравнения)
        r'решение[:\s]+\$?-?\d+',                 # "решение: 5"
        # Новые паттерны для stricter detection
        r'правильн(?:ый|о)\s+(?:ответ|решение)',  # "правильный ответ"
        r'верн(?:о|ый)[:\s]+\$?-?\d+',            # "верно: 5"
        r'значит[,\s]+\$?-?\d+',                  # "значит, 5"
        r'следовательно[,\s]+\$?x?\s*=\s*-?\d+',  # "следовательно, x = 5"
        r'ответ\s+(?:будет|составит|равен)',      # "ответ будет"
        r'(?:корень|корни)\s*[:=]\s*\$?-?\d+',    # "корень: 5"
        r'в\s+итоге\s+\$?-?\d+',                  # "в итоге 5"
        r'окончательн(?:о|ый)\s+\$?-?\d+',        # "окончательно 5"
        # English patterns (fallback)
        r'the\s+answer\s+is\s+\$?-?\d+',          # "the answer is 5"
        r'solution\s*[:=]\s*\$?-?\d+',            # "solution: 5"
    ]

    # Паттерны формул, которые выглядят как решения
    SOLUTION_REVEAL_PATTERNS = [
        r'подставляя.*получ(?:аем|им)\s+\$?-?\d+',  # "подставляя, получаем 5"
        r'(?:упрощ|сокращ)ая.*=\s*\$?-?\d+$',       # "упрощая...= 5"
        r'раскрыва[яв].*=\s*\$?-?\d+',              # "раскрывая...= 5"
    ]

    # Паттерны вопросов
    QUESTION_PATTERNS = [
        r'\?$',                              # Заканчивается на ?
        r'\?["\']?\s*$',                     # ? с кавычками
        r'можешь\s+ли',                      # "можешь ли"
        r'как\s+ты\s+думаешь',               # "как ты думаешь"
        r'что\s+(?:будет|получится)',        # "что будет/получится"
        r'почему',                           # "почему"
        r'какой\s+(?:шаг|этап)',             # "какой шаг"
    ]

    # Паттерны для LaTeX
    MATH_INDICATORS = [
        r'\d+[+\-*/^]\d+',                   # Арифметика
        r'[xyz]\s*[+\-*/^=]',                # Переменные
        r'уравнен',                          # "уравнение"
        r'формул',                           # "формула"
        r'выражен',                          # "выражение"
        r'производн',                        # "производная"
        r'интеграл',                         # "интеграл"
        r'корн[яеь]',                        # "корень"
        r'степен',                           # "степень"
        r'дроб',                             # "дробь"
    ]

    # Допустимые ходы
    VALID_MOVES = {
        "scaffolding", "problematize", "rectify",
        "encourage", "hint", "tell", "clarify", "summarize"
    }

    # Лимиты длины ответа
    MIN_RESPONSE_LENGTH = 20
    MAX_RESPONSE_LENGTH = 1000

    def __init__(self, llm_client=None, strict_mode: bool = False):
        """
        Инициализация верификатора.

        Args:
            llm_client: Клиент LLM для сложных проверок (опционально)
            strict_mode: Строгий режим (все предупреждения = критические)
        """
        self.llm = llm_client
        self.strict_mode = strict_mode

        # Компилируем регулярные выражения
        self.answer_leak_re = [re.compile(p, re.IGNORECASE) for p in self.ANSWER_LEAK_PATTERNS]
        self.solution_reveal_re = [re.compile(p, re.IGNORECASE) for p in self.SOLUTION_REVEAL_PATTERNS]
        self.question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]
        self.math_re = [re.compile(p, re.IGNORECASE) for p in self.MATH_INDICATORS]

        logger.info("VerifierAgent инициализирован", extra={"strict_mode": strict_mode})

    def verify(
        self,
        response: str,
        problem: Optional[str] = None,
        correct_answer: Optional[str] = None,
        move_type: Optional[str] = None
    ) -> VerificationResult:
        """
        Полная верификация ответа репетитора.

        Args:
            response: Ответ репетитора (строка или JSON)
            problem: Текст задачи (для контекста)
            correct_answer: Правильный ответ (для детекции утечки)
            move_type: Ожидаемый тип хода

        Returns:
            VerificationResult с оценкой и списком проблем
        """
        checks: List[QualityCheck] = []

        # 1. Проверка JSON формата
        json_check, parsed_data = self._check_json_format(response)
        if json_check:
            checks.append(json_check)

        # Извлекаем message для дальнейших проверок
        message = self._extract_message(response, parsed_data)
        actual_move = self._extract_move(parsed_data)

        # 2. Проверка утечки ответов
        leak_check = self._check_answer_leak(message, correct_answer)
        if leak_check:
            checks.append(leak_check)

        # 3. Проверка наличия вопроса (для сократического метода)
        question_check = self._check_has_question(message, actual_move)
        if question_check:
            checks.append(question_check)

        # 4. Проверка типа хода
        if move_type:
            move_check = self._check_move_type(actual_move, move_type)
            if move_check:
                checks.append(move_check)

        # 5. Проверка использования LaTeX
        latex_check = self._check_latex_usage(message)
        if latex_check:
            checks.append(latex_check)

        # 6. Проверка языка
        lang_check = self._check_language(message)
        if lang_check:
            checks.append(lang_check)

        # 7. Проверка длины
        length_check = self._check_length(message)
        if length_check:
            checks.append(length_check)

        # 8. Проверка на слишком прямое объяснение
        direct_check = self._check_too_direct(message, actual_move)
        if direct_check:
            checks.append(direct_check)

        # Вычисляем итоговый score
        score = self._calculate_score(checks)

        # Определяем валидность
        critical_count = len([c for c in checks if c.severity == Severity.CRITICAL])
        is_valid = critical_count == 0

        result = VerificationResult(
            is_valid=is_valid,
            score=score,
            checks=checks
        )

        logger.debug(
            "Верификация завершена",
            extra={
                "is_valid": is_valid,
                "score": score,
                "critical_issues": critical_count,
                "total_checks": len(checks)
            }
        )

        return result

    def _check_json_format(self, response: str) -> Tuple[Optional[QualityCheck], Optional[dict]]:
        """Проверка валидности JSON формата."""
        # Если строка не похожа на JSON, это не ошибка
        if not response.strip().startswith('{'):
            return None, None

        try:
            data = json.loads(response)

            # Проверяем наличие обязательных полей
            if "move" not in data:
                return QualityCheck(
                    issue=QualityIssue.INVALID_JSON,
                    severity=Severity.WARNING,
                    message="JSON не содержит поле 'move'",
                    suggestion="Добавьте поле 'move' с типом хода"
                ), data

            if "message" not in data:
                return QualityCheck(
                    issue=QualityIssue.INVALID_JSON,
                    severity=Severity.WARNING,
                    message="JSON не содержит поле 'message'",
                    suggestion="Добавьте поле 'message' с текстом ответа"
                ), data

            # Проверяем валидность хода
            if data["move"] not in self.VALID_MOVES:
                return QualityCheck(
                    issue=QualityIssue.WRONG_MOVE,
                    severity=Severity.WARNING,
                    message=f"Неизвестный тип хода: {data['move']}",
                    suggestion=f"Используйте один из: {', '.join(self.VALID_MOVES)}"
                ), data

            return None, data

        except json.JSONDecodeError as e:
            return QualityCheck(
                issue=QualityIssue.INVALID_JSON,
                severity=Severity.CRITICAL if self.strict_mode else Severity.WARNING,
                message=f"Невалидный JSON: {str(e)}",
                location=f"позиция {e.pos}",
                suggestion="Проверьте синтаксис JSON"
            ), None

    def _check_answer_leak(
        self,
        message: str,
        correct_answer: Optional[str]
    ) -> Optional[QualityCheck]:
        """Проверка на утечку ответа (ENHANCED)."""
        # Проверяем по основным паттернам
        for pattern in self.answer_leak_re:
            match = pattern.search(message)
            if match:
                return QualityCheck(
                    issue=QualityIssue.ANSWER_LEAK,
                    severity=Severity.CRITICAL,
                    message="Обнаружена возможная утечка ответа",
                    location=match.group(),
                    suggestion="Замените прямой ответ на наводящий вопрос"
                )

        # Проверяем паттерны раскрытия решения
        for pattern in self.solution_reveal_re:
            match = pattern.search(message)
            if match:
                return QualityCheck(
                    issue=QualityIssue.ANSWER_LEAK,
                    severity=Severity.CRITICAL,
                    message="Обнаружено раскрытие полного решения",
                    location=match.group(),
                    suggestion="Не показывайте конечный результат вычислений"
                )

        # Если известен правильный ответ, проверяем его наличие
        if correct_answer:
            # Очищаем ответ от пробелов и приводим к строке
            clean_answer = str(correct_answer).strip()

            # Проверяем точное вхождение числа
            if re.search(rf'\b{re.escape(clean_answer)}\b', message):
                # Но не в контексте вопроса или примера
                context_before = message[:message.find(clean_answer)]
                safe_contexts = [
                    'например', 'допустим', 'если', 'пусть', 'подставим',
                    'что если', 'а что если', 'предположим', 'представь'
                ]
                if not any(word in context_before.lower()[-50:] for word in safe_contexts):
                    return QualityCheck(
                        issue=QualityIssue.ANSWER_LEAK,
                        severity=Severity.CRITICAL,
                        message=f"Ответ '{clean_answer}' обнаружен в тексте",
                        suggestion="Не давайте прямой ответ, используйте наводящие вопросы"
                    )

            # Проверяем также варианты записи ответа
            answer_variants = self._generate_answer_variants(clean_answer)
            for variant in answer_variants:
                if variant in message.lower():
                    # Проверяем контекст
                    idx = message.lower().find(variant)
                    context = message[max(0, idx-50):idx]
                    safe_contexts = ['например', 'допустим', 'если', 'пусть']
                    if not any(word in context.lower() for word in safe_contexts):
                        return QualityCheck(
                            issue=QualityIssue.ANSWER_LEAK,
                            severity=Severity.CRITICAL,
                            message=f"Вариант ответа '{variant}' обнаружен в тексте",
                            suggestion="Не давайте прямой ответ, используйте наводящие вопросы"
                        )

        return None

    def _generate_answer_variants(self, answer: str) -> List[str]:
        """Generate possible variants of the answer for stricter checking."""
        variants = [answer.lower()]

        # Try to parse as number
        try:
            num = float(answer)
            # Integer form
            if num == int(num):
                variants.append(str(int(num)))
            # Decimal form
            variants.append(f"{num:.2f}")
            # Negative form
            if num > 0:
                variants.append(f"-{num}")
        except ValueError:
            pass

        # Fraction variants
        if '/' in answer:
            parts = answer.split('/')
            if len(parts) == 2:
                try:
                    result = float(parts[0]) / float(parts[1])
                    variants.append(f"{result:.4f}")
                except:
                    pass

        return variants

    def _check_has_question(
        self,
        message: str,
        move_type: Optional[str]
    ) -> Optional[QualityCheck]:
        """Проверка наличия вопроса (сократический метод)."""
        # Для хода "tell" вопрос не обязателен
        if move_type == "tell":
            return None

        # Для "encourage" тоже не всегда нужен вопрос
        if move_type == "encourage" and '!' in message:
            return None

        # Проверяем наличие вопроса
        has_question = any(pattern.search(message) for pattern in self.question_re)

        if not has_question:
            return QualityCheck(
                issue=QualityIssue.MISSING_QUESTION,
                severity=Severity.WARNING,
                message="Ответ не содержит вопроса",
                suggestion="Добавьте наводящий вопрос для вовлечения ученика"
            )

        return None

    def _check_move_type(
        self,
        actual_move: Optional[str],
        expected_move: str
    ) -> Optional[QualityCheck]:
        """Проверка соответствия типа хода ожидаемому."""
        if actual_move is None:
            return None

        if actual_move != expected_move:
            # Некоторые замены допустимы
            compatible_moves = {
                "scaffolding": {"hint", "clarify"},
                "hint": {"scaffolding"},
                "encourage": {"scaffolding"},
                "rectify": {"problematize", "clarify"}
            }

            if expected_move in compatible_moves and actual_move in compatible_moves[expected_move]:
                return None

            return QualityCheck(
                issue=QualityIssue.WRONG_MOVE,
                severity=Severity.INFO,
                message=f"Тип хода '{actual_move}' отличается от ожидаемого '{expected_move}'",
                suggestion=f"Рассмотрите использование хода '{expected_move}'"
            )

        return None

    def _check_latex_usage(self, message: str) -> Optional[QualityCheck]:
        """Проверка использования LaTeX для математических формул."""
        # Проверяем, есть ли математический контент
        has_math = any(pattern.search(message) for pattern in self.math_re)

        if not has_math:
            return None

        # Проверяем наличие LaTeX
        has_latex = '$' in message or '\\(' in message or '\\[' in message

        if not has_latex:
            return QualityCheck(
                issue=QualityIssue.NO_LATEX,
                severity=Severity.INFO,
                message="Математические выражения не оформлены в LaTeX",
                suggestion="Оберните формулы в $...$ для лучшего отображения"
            )

        return None

    def _check_language(self, message: str) -> Optional[QualityCheck]:
        """Проверка языка ответа."""
        # Простая эвристика: считаем кириллические символы
        cyrillic_count = len(re.findall(r'[а-яА-ЯёЁ]', message))
        latin_count = len(re.findall(r'[a-zA-Z]', message))

        # Если латиницы больше (исключая LaTeX), возможно не русский
        # LaTeX содержит много латиницы, поэтому исключаем контент в $...$
        message_without_latex = re.sub(r'\$[^$]+\$', '', message)
        latin_in_text = len(re.findall(r'[a-zA-Z]', message_without_latex))

        if latin_in_text > cyrillic_count and cyrillic_count < 10:
            return QualityCheck(
                issue=QualityIssue.WRONG_LANGUAGE,
                severity=Severity.WARNING,
                message="Ответ может быть не на русском языке",
                suggestion="Убедитесь, что ответ написан на русском"
            )

        return None

    def _check_length(self, message: str) -> Optional[QualityCheck]:
        """Проверка длины ответа."""
        length = len(message)

        if length < self.MIN_RESPONSE_LENGTH:
            return QualityCheck(
                issue=QualityIssue.TOO_SHORT,
                severity=Severity.WARNING,
                message=f"Ответ слишком короткий ({length} символов)",
                suggestion=f"Расширьте ответ, минимум {self.MIN_RESPONSE_LENGTH} символов"
            )

        if length > self.MAX_RESPONSE_LENGTH:
            return QualityCheck(
                issue=QualityIssue.TOO_LONG,
                severity=Severity.INFO,
                message=f"Ответ очень длинный ({length} символов)",
                suggestion="Рассмотрите разбиение на несколько сообщений"
            )

        return None

    def _check_too_direct(
        self,
        message: str,
        move_type: Optional[str]
    ) -> Optional[QualityCheck]:
        """Проверка на слишком прямое объяснение."""
        # Для "tell" прямое объяснение допустимо
        if move_type == "tell":
            return None

        # Паттерны прямых объяснений
        direct_patterns = [
            r'нужно\s+(?:просто\s+)?сделать',
            r'(?:ты\s+)?должен\s+',
            r'правильный\s+(?:способ|метод|подход)',
            r'делай\s+так[:\s]',
            r'вот\s+как\s+это\s+делается',
            r'формула[:\s]+',
            r'алгоритм[:\s]+',
        ]

        for pattern in direct_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return QualityCheck(
                    issue=QualityIssue.TOO_DIRECT,
                    severity=Severity.WARNING,
                    message="Ответ содержит слишком прямое указание",
                    suggestion="Переформулируйте как наводящий вопрос"
                )

        return None

    def _extract_message(self, response: str, parsed_data: Optional[dict]) -> str:
        """Извлечение текста сообщения."""
        if parsed_data and "message" in parsed_data:
            return parsed_data["message"]
        return response

    def _extract_move(self, parsed_data: Optional[dict]) -> Optional[str]:
        """Извлечение типа хода."""
        if parsed_data and "move" in parsed_data:
            return parsed_data["move"]
        return None

    def _calculate_score(self, checks: List[QualityCheck]) -> float:
        """Вычисление итогового score качества."""
        if not checks:
            return 1.0

        # Веса для разных уровней серьёзности
        weights = {
            Severity.CRITICAL: 0.4,
            Severity.WARNING: 0.15,
            Severity.INFO: 0.05
        }

        penalty = sum(weights[c.severity] for c in checks)

        return max(0.0, 1.0 - penalty)

    def verify_batch(
        self,
        responses: List[str],
        problems: Optional[List[str]] = None,
        answers: Optional[List[str]] = None
    ) -> List[VerificationResult]:
        """
        Верификация батча ответов.

        Args:
            responses: Список ответов
            problems: Список задач
            answers: Список правильных ответов

        Returns:
            Список результатов верификации
        """
        results = []

        for i, response in enumerate(responses):
            problem = problems[i] if problems else None
            answer = answers[i] if answers else None

            result = self.verify(response, problem, answer)
            results.append(result)

        return results

    def get_statistics(self, results: List[VerificationResult]) -> Dict[str, Any]:
        """
        Статистика по результатам верификации.

        Args:
            results: Список результатов

        Returns:
            Словарь со статистикой
        """
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        avg_score = sum(r.score for r in results) / total if total > 0 else 0

        # Подсчёт проблем по типам
        issue_counts: Dict[str, int] = {}
        for result in results:
            for check in result.checks:
                issue_name = check.issue.value
                issue_counts[issue_name] = issue_counts.get(issue_name, 0) + 1

        return {
            "total": total,
            "valid": valid,
            "valid_rate": valid / total if total > 0 else 0,
            "average_score": avg_score,
            "issue_counts": issue_counts,
            "most_common_issue": max(issue_counts, key=issue_counts.get) if issue_counts else None
        }


# Фабричная функция
def create_verifier(strict_mode: bool = False) -> VerifierAgent:
    """
    Создание верификатора.

    Args:
        strict_mode: Строгий режим проверки

    Returns:
        Экземпляр VerifierAgent
    """
    return VerifierAgent(strict_mode=strict_mode)


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    verifier = create_verifier()

    # Тестовые примеры
    test_cases = [
        # Хороший ответ
        '{"move": "scaffolding", "message": "Давай разберём это уравнение. Что нам нужно сделать, чтобы найти $x$?"}',

        # Утечка ответа
        '{"move": "tell", "message": "Ответ: 5. Теперь ты понял?"}',

        # Нет вопроса
        '{"move": "scaffolding", "message": "Перенеси 5 на другую сторону уравнения."}',

        # Невалидный JSON
        '{"move": "hint", "message": "Подумай о знаке"',

        # Хороший ответ без JSON
        "Отлично! Ты верно определил, что нужно перенести число. А что происходит со знаком при переносе?"
    ]

    print("=== Тестирование Верификатора ===\n")

    for i, response in enumerate(test_cases, 1):
        print(f"--- Тест {i} ---")
        print(f"Ответ: {response[:80]}...")

        result = verifier.verify(response, correct_answer="5")
        print(f"Результат: {result.summary()}")

        if result.checks:
            print("Проблемы:")
            for check in result.checks:
                print(f"  - [{check.severity.value}] {check.issue.value}: {check.message}")

        print()
