#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Метрики оценки качества сократического репетитора MITS.

Метрики:
- JSON validity: Валидность формата ответа
- Move accuracy: Точность выбора типа хода
- Socratic score: Процент ответов с вопросами
- Tell rate: Частота прямых объяснений (чем меньше, тем лучше)
- LaTeX usage: Использование математических формул
- Russian rate: Ответы на русском языке
- Answer leak rate: Частота утечки ответов
"""

import json
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ResponseMetrics:
    """Метрики одного ответа."""
    is_valid_json: bool = False
    has_move: bool = False
    has_message: bool = False
    move_type: Optional[str] = None
    has_question: bool = False
    has_latex: bool = False
    is_russian: bool = True
    has_answer_leak: bool = False
    response_length: int = 0
    is_too_direct: bool = False


@dataclass
class EvaluationResult:
    """Результаты оценки батча ответов."""
    total_responses: int = 0
    json_validity_rate: float = 0.0
    move_accuracy_rate: float = 0.0
    socratic_score: float = 0.0  # % ответов с вопросами
    tell_rate: float = 0.0       # % ответов с move=tell
    latex_usage_rate: float = 0.0
    russian_rate: float = 0.0
    answer_leak_rate: float = 0.0
    avg_response_length: float = 0.0

    # Распределение ходов
    move_distribution: Dict[str, int] = field(default_factory=dict)

    # Детальные метрики
    individual_metrics: List[ResponseMetrics] = field(default_factory=list)

    def print_report(self):
        """Вывод отчёта по метрикам."""
        print("\n" + "=" * 60)
        print("ОТЧЁТ ПО ОЦЕНКЕ КАЧЕСТВА РЕПЕТИТОРА")
        print("=" * 60)

        print(f"\nВсего ответов: {self.total_responses}")

        print("\n--- Основные метрики ---")
        print(f"JSON validity:      {self.json_validity_rate * 100:.1f}%")
        print(f"Move accuracy:      {self.move_accuracy_rate * 100:.1f}%")
        print(f"Socratic score:     {self.socratic_score * 100:.1f}%")
        print(f"Tell rate:          {self.tell_rate * 100:.1f}% (цель: <15%)")
        print(f"LaTeX usage:        {self.latex_usage_rate * 100:.1f}%")
        print(f"Russian rate:       {self.russian_rate * 100:.1f}%")
        print(f"Answer leak rate:   {self.answer_leak_rate * 100:.1f}% (цель: 0%)")

        print(f"\nСредняя длина ответа: {self.avg_response_length:.0f} символов")

        if self.move_distribution:
            print("\n--- Распределение ходов ---")
            total_moves = sum(self.move_distribution.values())
            for move, count in sorted(self.move_distribution.items(),
                                      key=lambda x: x[1], reverse=True):
                pct = count / total_moves * 100 if total_moves > 0 else 0
                print(f"  {move}: {count} ({pct:.1f}%)")

        # Итоговая оценка
        score = self._calculate_overall_score()
        print(f"\n{'=' * 60}")
        print(f"ИТОГОВЫЙ SCORE: {score:.2f}/1.00")
        print(self._get_verdict(score))
        print("=" * 60)

    def _calculate_overall_score(self) -> float:
        """Вычисление итогового score."""
        weights = {
            'json_validity': 0.15,
            'socratic': 0.25,
            'tell_penalty': 0.15,
            'latex': 0.10,
            'russian': 0.10,
            'no_leak': 0.25
        }

        score = (
            weights['json_validity'] * self.json_validity_rate +
            weights['socratic'] * self.socratic_score +
            weights['tell_penalty'] * (1.0 - self.tell_rate) +
            weights['latex'] * self.latex_usage_rate +
            weights['russian'] * self.russian_rate +
            weights['no_leak'] * (1.0 - self.answer_leak_rate)
        )

        return min(1.0, max(0.0, score))

    def _get_verdict(self, score: float) -> str:
        """Вердикт по score."""
        if score >= 0.9:
            return "Отлично! Репетитор работает на высоком уровне."
        elif score >= 0.8:
            return "Хорошо. Есть небольшие области для улучшения."
        elif score >= 0.7:
            return "Удовлетворительно. Требуется доработка."
        elif score >= 0.5:
            return "Ниже ожиданий. Значительные проблемы с качеством."
        else:
            return "Критично! Требуется серьёзная переработка."

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            'total_responses': self.total_responses,
            'json_validity_rate': self.json_validity_rate,
            'move_accuracy_rate': self.move_accuracy_rate,
            'socratic_score': self.socratic_score,
            'tell_rate': self.tell_rate,
            'latex_usage_rate': self.latex_usage_rate,
            'russian_rate': self.russian_rate,
            'answer_leak_rate': self.answer_leak_rate,
            'avg_response_length': self.avg_response_length,
            'move_distribution': self.move_distribution,
            'overall_score': self._calculate_overall_score()
        }


class TutorEvaluator:
    """
    Оценщик качества ответов репетитора.

    Анализирует ответы по множеству метрик для определения
    соответствия сократическому методу обучения.
    """

    VALID_MOVES = {
        "scaffolding", "problematize", "rectify",
        "encourage", "hint", "tell", "clarify", "summarize"
    }

    QUESTION_PATTERNS = [
        r'\?$',
        r'\?["\']?\s*$',
        r'\?\s*$',
        r'можешь\s+ли',
        r'как\s+ты\s+думаешь',
        r'что\s+(?:будет|получится|нужно)',
        r'почему',
        r'какой\s+(?:шаг|этап|результат)',
        r'попробу[йе]',
        r'подумай',
    ]

    ANSWER_LEAK_PATTERNS = [
        r'ответ[:\s]+[=]?\s*-?\d+',
        r'равн[оа]\s+-?\d+',
        r'получ[аие][ем]\s+-?\d+',
        r'итого[:\s]+-?\d+',
        r'результат[:\s]+-?\d+',
        r'x\s*=\s*-?\d+(?:\.\d+)?(?!\s*[+\-*/])',
        r'решение[:\s]+-?\d+',
    ]

    def __init__(self):
        """Инициализация оценщика."""
        self.question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]
        self.leak_re = [re.compile(p, re.IGNORECASE) for p in self.ANSWER_LEAK_PATTERNS]

    def evaluate_single(
        self,
        response: str,
        expected_move: Optional[str] = None,
        correct_answer: Optional[str] = None
    ) -> ResponseMetrics:
        """
        Оценка одного ответа.

        Args:
            response: Ответ репетитора
            expected_move: Ожидаемый тип хода
            correct_answer: Правильный ответ (для проверки утечки)

        Returns:
            ResponseMetrics с детальными метриками
        """
        metrics = ResponseMetrics()
        metrics.response_length = len(response)

        # 1. Проверка JSON
        parsed_data = self._parse_json(response)
        metrics.is_valid_json = parsed_data is not None

        if parsed_data:
            metrics.has_move = "move" in parsed_data
            metrics.has_message = "message" in parsed_data
            metrics.move_type = parsed_data.get("move")
            message = parsed_data.get("message", "")
        else:
            message = response

        # 2. Проверка наличия вопроса
        metrics.has_question = self._has_question(message)

        # 3. Проверка LaTeX
        metrics.has_latex = '$' in message or '\\(' in message

        # 4. Проверка языка
        metrics.is_russian = self._is_russian(message)

        # 5. Проверка утечки ответа
        metrics.has_answer_leak = self._has_answer_leak(message, correct_answer)

        # 6. Проверка на слишком прямое объяснение
        metrics.is_too_direct = self._is_too_direct(message, metrics.move_type)

        return metrics

    def evaluate_batch(
        self,
        responses: List[str],
        expected_moves: Optional[List[str]] = None,
        correct_answers: Optional[List[str]] = None
    ) -> EvaluationResult:
        """
        Оценка батча ответов.

        Args:
            responses: Список ответов
            expected_moves: Список ожидаемых ходов
            correct_answers: Список правильных ответов

        Returns:
            EvaluationResult с агрегированными метриками
        """
        if not responses:
            return EvaluationResult()

        individual_metrics = []
        move_counts: Dict[str, int] = {}

        for i, response in enumerate(responses):
            expected = expected_moves[i] if expected_moves else None
            answer = correct_answers[i] if correct_answers else None

            metrics = self.evaluate_single(response, expected, answer)
            individual_metrics.append(metrics)

            # Подсчёт ходов
            if metrics.move_type:
                move_counts[metrics.move_type] = move_counts.get(metrics.move_type, 0) + 1

        # Агрегация метрик
        total = len(individual_metrics)

        result = EvaluationResult(
            total_responses=total,
            json_validity_rate=sum(1 for m in individual_metrics if m.is_valid_json) / total,
            move_accuracy_rate=self._calculate_move_accuracy(individual_metrics, expected_moves),
            socratic_score=sum(1 for m in individual_metrics if m.has_question) / total,
            tell_rate=move_counts.get("tell", 0) / total,
            latex_usage_rate=sum(1 for m in individual_metrics if m.has_latex) / total,
            russian_rate=sum(1 for m in individual_metrics if m.is_russian) / total,
            answer_leak_rate=sum(1 for m in individual_metrics if m.has_answer_leak) / total,
            avg_response_length=sum(m.response_length for m in individual_metrics) / total,
            move_distribution=move_counts,
            individual_metrics=individual_metrics
        )

        return result

    def _parse_json(self, response: str) -> Optional[Dict]:
        """Парсинг JSON из ответа."""
        try:
            if response.strip().startswith('{'):
                return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Попробуем извлечь JSON из текста
        try:
            start = response.find('{')
            end = response.rfind('}')
            if start != -1 and end > start:
                return json.loads(response[start:end + 1])
        except json.JSONDecodeError:
            pass

        return None

    def _has_question(self, message: str) -> bool:
        """Проверка наличия вопроса."""
        return any(pattern.search(message) for pattern in self.question_re)

    def _is_russian(self, message: str) -> bool:
        """Проверка языка."""
        # Удаляем LaTeX
        message_clean = re.sub(r'\$[^$]+\$', '', message)

        cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', message_clean))
        latin = len(re.findall(r'[a-zA-Z]', message_clean))

        # Если кириллицы мало и латиницы много - скорее всего не русский
        if cyrillic < 5 and latin > cyrillic:
            return False

        return True

    def _has_answer_leak(self, message: str, correct_answer: Optional[str]) -> bool:
        """Проверка на утечку ответа."""
        # Проверка по паттернам
        for pattern in self.leak_re:
            if pattern.search(message):
                return True

        # Проверка конкретного ответа
        if correct_answer:
            clean_answer = str(correct_answer).strip()
            # Ищем число вне контекста примера
            pattern = rf'\b{re.escape(clean_answer)}\b'
            match = re.search(pattern, message)
            if match:
                # Проверяем контекст
                before = message[:match.start()]
                if not any(word in before.lower()[-50:] for word in
                          ['например', 'допустим', 'если', 'пусть', 'подставим']):
                    return True

        return False

    def _is_too_direct(self, message: str, move_type: Optional[str]) -> bool:
        """Проверка на слишком прямое объяснение."""
        if move_type == "tell":
            return False

        direct_patterns = [
            r'нужно\s+(?:просто\s+)?сделать',
            r'правильный\s+(?:способ|метод)',
            r'делай\s+так[:\s]',
            r'вот\s+как\s+это\s+делается',
        ]

        for pattern in direct_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True

        return False

    def _calculate_move_accuracy(
        self,
        metrics: List[ResponseMetrics],
        expected_moves: Optional[List[str]]
    ) -> float:
        """Вычисление точности выбора хода."""
        if not expected_moves:
            # Без ожидаемых ходов считаем только валидность
            valid_moves = sum(1 for m in metrics
                            if m.move_type and m.move_type in self.VALID_MOVES)
            return valid_moves / len(metrics) if metrics else 0.0

        correct = 0
        for m, expected in zip(metrics, expected_moves):
            if m.move_type == expected:
                correct += 1
            # Допускаем похожие ходы
            elif self._are_compatible_moves(m.move_type, expected):
                correct += 0.5

        return correct / len(metrics) if metrics else 0.0

    def _are_compatible_moves(self, actual: Optional[str], expected: str) -> bool:
        """Проверка совместимости ходов."""
        if not actual:
            return False

        compatible = {
            "scaffolding": {"hint", "clarify"},
            "hint": {"scaffolding"},
            "encourage": {"scaffolding"},
            "rectify": {"problematize", "clarify"}
        }

        return actual in compatible.get(expected, set())


def compare_models(
    teacher_result: EvaluationResult,
    student_result: EvaluationResult
) -> Dict[str, Any]:
    """
    Сравнение результатов учителя и ученика.

    Args:
        teacher_result: Результаты модели-учителя
        student_result: Результаты модели-ученика

    Returns:
        Словарь со сравнительным анализом
    """
    comparison = {
        'metrics': {},
        'summary': {}
    }

    metrics_to_compare = [
        ('json_validity_rate', 'higher'),
        ('socratic_score', 'higher'),
        ('tell_rate', 'lower'),
        ('latex_usage_rate', 'higher'),
        ('russian_rate', 'higher'),
        ('answer_leak_rate', 'lower')
    ]

    wins = 0
    losses = 0

    for metric, direction in metrics_to_compare:
        teacher_val = getattr(teacher_result, metric)
        student_val = getattr(student_result, metric)

        diff = student_val - teacher_val
        relative_diff = diff / teacher_val if teacher_val > 0 else 0

        is_better = (direction == 'higher' and diff > 0) or \
                   (direction == 'lower' and diff < 0)

        comparison['metrics'][metric] = {
            'teacher': teacher_val,
            'student': student_val,
            'diff': diff,
            'relative_diff_pct': relative_diff * 100,
            'is_better': is_better
        }

        if is_better:
            wins += 1
        elif diff != 0:
            losses += 1

    # Итоговые scores
    teacher_score = teacher_result._calculate_overall_score()
    student_score = student_result._calculate_overall_score()

    comparison['summary'] = {
        'teacher_score': teacher_score,
        'student_score': student_score,
        'score_ratio': student_score / teacher_score if teacher_score > 0 else 0,
        'wins': wins,
        'losses': losses,
        'meets_target': student_score >= teacher_score * 0.9  # 90% от учителя
    }

    return comparison


def print_comparison(comparison: Dict[str, Any]):
    """Вывод сравнительного анализа."""
    print("\n" + "=" * 70)
    print("СРАВНЕНИЕ МОДЕЛЕЙ: УЧИТЕЛЬ vs УЧЕНИК")
    print("=" * 70)

    print("\n--- Метрики ---")
    for metric, data in comparison['metrics'].items():
        status = "+" if data['is_better'] else "-"
        print(f"{metric}:")
        print(f"  Учитель: {data['teacher']:.3f}")
        print(f"  Ученик:  {data['student']:.3f} {status}")
        print(f"  Разница: {data['diff']:+.3f} ({data['relative_diff_pct']:+.1f}%)")
        print()

    summary = comparison['summary']
    print("--- Итого ---")
    print(f"Score учителя: {summary['teacher_score']:.3f}")
    print(f"Score ученика: {summary['student_score']:.3f}")
    print(f"Соотношение:   {summary['score_ratio']:.1%}")
    print(f"Побед/поражений: {summary['wins']}/{summary['losses']}")

    if summary['meets_target']:
        print("\nЦЕЛЬ ДОСТИГНУТА: Ученик достиг 90%+ от качества учителя")
    else:
        print("\nЦЕЛЬ НЕ ДОСТИГНУТА: Требуется доработка")


def load_test_dialogs(file_path: str) -> List[Dict[str, Any]]:
    """Загрузка тестовых диалогов из JSONL файла."""
    dialogs = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                dialogs.append(json.loads(line))
    return dialogs


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    evaluator = TutorEvaluator()

    # Тестовые ответы
    test_responses = [
        # Хороший ответ
        '{"move": "scaffolding", "message": "Давай разберём это уравнение $2x + 5 = 13$ по шагам. Что нам нужно сделать, чтобы оставить $x$ в одиночестве?"}',

        # Хороший ответ с hint
        '{"move": "hint", "message": "Подумай, какое число мешает нам выделить $x$. Как его можно убрать?"}',

        # Ответ с tell (допустимо, но снижает score)
        '{"move": "tell", "message": "Когда мы переносим число на другую сторону уравнения, знак меняется на противоположный."}',

        # Плохой ответ - утечка
        '{"move": "scaffolding", "message": "Правильно! Теперь получаем $x = 4$. Молодец!"}',

        # Невалидный JSON
        '{"move": "hint", message: без кавычек}',

        # Нет вопроса
        '{"move": "scaffolding", "message": "Перенеси 5 на другую сторону."}',
    ]

    print("=== Тест оценщика ===\n")

    # Оценка батча
    result = evaluator.evaluate_batch(
        test_responses,
        correct_answers=["4", "4", "4", "4", "4", "4"]
    )

    result.print_report()

    # Сохранение результатов
    print("\nРезультаты в JSON:")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
