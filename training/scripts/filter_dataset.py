#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт фильтрации качества диалогов для MITS.

Проверяет:
- Валидность JSON формата ответов репетитора
- Наличие сократических вопросов (не прямых ответов)
- Отсутствие утечки ответов
- Правильность русского языка
- Минимальное количество реплик
- Разнообразие педагогических ходов

Использование:
    python training/scripts/filter_dataset.py \
        --input data/training/cerebras_dialogs.jsonl \
        --output data/training/filtered_dialogs.jsonl \
        --min-quality 0.7
"""

import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class QualityIssue(Enum):
    """Типы проблем качества."""
    INVALID_JSON = "invalid_json"
    NO_QUESTION = "no_question"
    ANSWER_LEAK = "answer_leak"
    TOO_SHORT = "too_short"
    NO_MOVE = "no_move"
    WRONG_LANGUAGE = "wrong_language"
    MISSING_LATEX = "missing_latex"
    DIRECT_ANSWER = "direct_answer"
    REPETITIVE = "repetitive"


@dataclass
class QualityCheck:
    """Результат проверки качества диалога."""
    is_valid: bool
    score: float  # 0.0 - 1.0
    issues: List[QualityIssue] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FilterStats:
    """Статистика фильтрации."""
    total_input: int = 0
    passed: int = 0
    failed: int = 0
    issues_count: Dict[str, int] = field(default_factory=dict)
    avg_quality: float = 0.0

    def add_issue(self, issue: QualityIssue):
        key = issue.value
        self.issues_count[key] = self.issues_count.get(key, 0) + 1


class DialogQualityFilter:
    """
    Фильтр качества сократических диалогов.

    Проверяет соответствие диалога требованиям:
    - Сократический метод (вопросы, не ответы)
    - Правильный JSON формат
    - Русский язык
    - Отсутствие прямых ответов
    """

    # Паттерны для детекции прямых ответов
    DIRECT_ANSWER_PATTERNS = [
        r'ответ\s*(есть|равен|будет|=)\s*',
        r'правильный ответ',
        r'решение\s*[:=]',
        r'получаем\s*[:=]\s*\d',
        r'итого\s*[:=]\s*\d',
        r'значит,?\s*x\s*=\s*\d',
    ]

    # Паттерны для детекции вопросов
    QUESTION_PATTERNS = [
        r'\?$',
        r'\?["\']?$',
        r'как ты думаешь',
        r'что ты думаешь',
        r'можешь ли ты',
        r'попробуй',
        r'подумай',
        r'как считаешь',
        r'что получится',
        r'какой результат',
    ]

    # Педагогические ходы
    VALID_MOVES = {'scaffolding', 'problematize', 'rectify', 'encourage', 'hint', 'tell'}

    # Русские буквы для проверки языка
    CYRILLIC_PATTERN = re.compile(r'[а-яА-ЯёЁ]')

    def __init__(
        self,
        min_turns: int = 4,
        min_quality: float = 0.6,
        require_questions: bool = True,
        check_latex: bool = True,
        max_tell_ratio: float = 0.3
    ):
        """
        Инициализация фильтра.

        Args:
            min_turns: Минимальное количество реплик
            min_quality: Минимальный порог качества (0-1)
            require_questions: Требовать вопросы в ответах репетитора
            check_latex: Проверять наличие LaTeX в математике
            max_tell_ratio: Максимальная доля ходов "tell"
        """
        self.min_turns = min_turns
        self.min_quality = min_quality
        self.require_questions = require_questions
        self.check_latex = check_latex
        self.max_tell_ratio = max_tell_ratio

        # Компилируем паттерны
        self.direct_answer_re = [re.compile(p, re.IGNORECASE) for p in self.DIRECT_ANSWER_PATTERNS]
        self.question_re = [re.compile(p, re.IGNORECASE) for p in self.QUESTION_PATTERNS]

    def check_dialog(self, dialog: Dict[str, Any]) -> QualityCheck:
        """
        Полная проверка качества диалога.

        Args:
            dialog: Диалог в формате {"conversations": [...], "metadata": {...}}

        Returns:
            QualityCheck с результатами
        """
        issues = []
        details = {}
        scores = []

        conversations = dialog.get("conversations", [])
        metadata = dialog.get("metadata", {})

        # 1. Проверка минимальной длины
        if len(conversations) < self.min_turns:
            issues.append(QualityIssue.TOO_SHORT)
            details["turn_count"] = len(conversations)
            scores.append(0.3)
        else:
            scores.append(1.0)

        # 2. Анализ ответов ассистента
        assistant_msgs = [
            msg for msg in conversations
            if msg.get("role") == "assistant"
        ]

        if not assistant_msgs:
            return QualityCheck(
                is_valid=False,
                score=0.0,
                issues=[QualityIssue.TOO_SHORT],
                details={"error": "no_assistant_messages"}
            )

        # Статистика по ходам
        moves = []
        questions_count = 0
        direct_answers_count = 0
        json_valid_count = 0
        russian_count = 0

        for msg in assistant_msgs:
            content = msg.get("content", "")

            # Проверка JSON
            try:
                data = json.loads(content)
                json_valid_count += 1

                move = data.get("move", "")
                message = data.get("message", "")

                if move in self.VALID_MOVES:
                    moves.append(move)

                # Проверка на вопрос
                if self._has_question(message):
                    questions_count += 1

                # Проверка на прямой ответ
                if self._has_direct_answer(message):
                    direct_answers_count += 1

                # Проверка русского языка
                if self._is_russian(message):
                    russian_count += 1

            except json.JSONDecodeError:
                # Не JSON - проверяем как текст
                if self._has_question(content):
                    questions_count += 1
                if self._has_direct_answer(content):
                    direct_answers_count += 1
                if self._is_russian(content):
                    russian_count += 1

        # 3. Оценка JSON валидности
        json_ratio = json_valid_count / len(assistant_msgs) if assistant_msgs else 0
        if json_ratio < 0.8:
            issues.append(QualityIssue.INVALID_JSON)
        details["json_valid_ratio"] = json_ratio
        scores.append(json_ratio)

        # 4. Оценка сократического метода (вопросы)
        question_ratio = questions_count / len(assistant_msgs) if assistant_msgs else 0
        if self.require_questions and question_ratio < 0.5:
            issues.append(QualityIssue.NO_QUESTION)
        details["question_ratio"] = question_ratio
        scores.append(min(1.0, question_ratio * 1.5))  # Бонус за вопросы

        # 5. Оценка отсутствия прямых ответов
        direct_ratio = direct_answers_count / len(assistant_msgs) if assistant_msgs else 0
        if direct_ratio > 0.2:
            issues.append(QualityIssue.DIRECT_ANSWER)
        details["direct_answer_ratio"] = direct_ratio
        scores.append(1.0 - direct_ratio)

        # 6. Оценка русского языка
        russian_ratio = russian_count / len(assistant_msgs) if assistant_msgs else 0
        if russian_ratio < 0.9:
            issues.append(QualityIssue.WRONG_LANGUAGE)
        details["russian_ratio"] = russian_ratio
        scores.append(russian_ratio)

        # 7. Оценка разнообразия ходов
        tell_count = moves.count("tell")
        tell_ratio = tell_count / len(moves) if moves else 0
        if tell_ratio > self.max_tell_ratio:
            issues.append(QualityIssue.ANSWER_LEAK)
        details["tell_ratio"] = tell_ratio
        details["moves"] = moves
        scores.append(1.0 - tell_ratio)

        # 8. Проверка LaTeX для математики (если применимо)
        discipline = metadata.get("discipline", "math")
        if self.check_latex and discipline == "math":
            has_latex = any(
                "$" in msg.get("content", "") or "\\(" in msg.get("content", "")
                for msg in conversations
            )
            if not has_latex:
                issues.append(QualityIssue.MISSING_LATEX)
                scores.append(0.8)  # Небольшой штраф
            else:
                scores.append(1.0)

        # Итоговая оценка
        final_score = sum(scores) / len(scores) if scores else 0.0
        is_valid = final_score >= self.min_quality and QualityIssue.ANSWER_LEAK not in issues

        return QualityCheck(
            is_valid=is_valid,
            score=final_score,
            issues=issues,
            details=details
        )

    def _has_question(self, text: str) -> bool:
        """Проверка наличия вопроса в тексте."""
        for pattern in self.question_re:
            if pattern.search(text):
                return True
        return False

    def _has_direct_answer(self, text: str) -> bool:
        """Проверка наличия прямого ответа."""
        for pattern in self.direct_answer_re:
            if pattern.search(text):
                return True
        return False

    def _is_russian(self, text: str) -> bool:
        """Проверка русского языка (хотя бы 30% кириллицы)."""
        if not text:
            return False
        cyrillic_count = len(self.CYRILLIC_PATTERN.findall(text))
        alpha_count = sum(1 for c in text if c.isalpha())
        if alpha_count == 0:
            return True  # Формулы без букв
        return cyrillic_count / alpha_count > 0.3


def filter_dataset(
    input_path: Path,
    output_path: Path,
    min_quality: float = 0.7,
    save_rejected: bool = True
) -> FilterStats:
    """
    Фильтрация датасета диалогов.

    Args:
        input_path: Путь к входному JSONL файлу
        output_path: Путь к выходному JSONL файлу
        min_quality: Минимальный порог качества
        save_rejected: Сохранять отклонённые диалоги

    Returns:
        Статистика фильтрации
    """
    filter_obj = DialogQualityFilter(min_quality=min_quality)
    stats = FilterStats()

    passed_dialogs = []
    rejected_dialogs = []
    quality_scores = []

    logger.info(f"Чтение файла: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                dialog = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Строка {line_num}: ошибка JSON - {e}")
                stats.failed += 1
                stats.add_issue(QualityIssue.INVALID_JSON)
                continue

            stats.total_input += 1

            # Проверка качества
            check = filter_obj.check_dialog(dialog)
            quality_scores.append(check.score)

            if check.is_valid:
                # Добавляем метаданные качества
                dialog["quality"] = {
                    "score": round(check.score, 3),
                    "checked_at": datetime.now().isoformat()
                }
                passed_dialogs.append(dialog)
                stats.passed += 1
            else:
                stats.failed += 1
                for issue in check.issues:
                    stats.add_issue(issue)

                if save_rejected:
                    dialog["quality"] = {
                        "score": round(check.score, 3),
                        "issues": [i.value for i in check.issues],
                        "details": check.details
                    }
                    rejected_dialogs.append(dialog)

            if stats.total_input % 100 == 0:
                logger.info(
                    f"Обработано: {stats.total_input} | "
                    f"Прошло: {stats.passed} | "
                    f"Отклонено: {stats.failed}"
                )

    # Средняя оценка качества
    stats.avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    # Сохранение результатов
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for dialog in passed_dialogs:
            f.write(json.dumps(dialog, ensure_ascii=False) + '\n')

    logger.info(f"Сохранено {len(passed_dialogs)} диалогов в {output_path}")

    # Сохранение отклонённых
    if save_rejected and rejected_dialogs:
        rejected_path = output_path.with_suffix('.rejected.jsonl')
        with open(rejected_path, 'w', encoding='utf-8') as f:
            for dialog in rejected_dialogs:
                f.write(json.dumps(dialog, ensure_ascii=False) + '\n')
        logger.info(f"Сохранено {len(rejected_dialogs)} отклонённых в {rejected_path}")

    return stats


def print_stats(stats: FilterStats):
    """Вывод статистики фильтрации."""
    print(f"\n{'='*50}")
    print("СТАТИСТИКА ФИЛЬТРАЦИИ")
    print(f"{'='*50}")
    print(f"Всего на входе:    {stats.total_input}")
    print(f"Прошло фильтр:     {stats.passed} ({stats.passed/stats.total_input*100:.1f}%)" if stats.total_input else "Прошло: 0")
    print(f"Отклонено:         {stats.failed} ({stats.failed/stats.total_input*100:.1f}%)" if stats.total_input else "Отклонено: 0")
    print(f"Средняя оценка:    {stats.avg_quality:.3f}")
    print(f"\nПроблемы:")
    for issue, count in sorted(stats.issues_count.items(), key=lambda x: -x[1]):
        print(f"  {issue}: {count}")
    print(f"{'='*50}\n")


def main():
    """CLI для фильтрации датасета."""
    parser = argparse.ArgumentParser(
        description="Фильтрация качества диалогов MITS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Базовая фильтрация
  python filter_dataset.py \\
      --input data/training/cerebras_dialogs.jsonl \\
      --output data/training/filtered_dialogs.jsonl

  # Строгая фильтрация
  python filter_dataset.py \\
      --input data/training/raw_dialogs.jsonl \\
      --output data/training/high_quality.jsonl \\
      --min-quality 0.8 \\
      --require-questions \\
      --no-answer-leaks

  # Анализ без сохранения
  python filter_dataset.py \\
      --input data/training/dialogs.jsonl \\
      --output /dev/null \\
      --analyze-only
        """
    )

    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Входной JSONL файл'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        required=True,
        help='Выходной JSONL файл'
    )
    parser.add_argument(
        '--min-quality',
        type=float,
        default=0.7,
        help='Минимальный порог качества (0-1, default: 0.7)'
    )
    parser.add_argument(
        '--require-questions',
        action='store_true',
        default=True,
        help='Требовать вопросы в ответах репетитора'
    )
    parser.add_argument(
        '--no-answer-leaks',
        action='store_true',
        default=True,
        help='Отклонять диалоги с утечкой ответов'
    )
    parser.add_argument(
        '--save-rejected',
        action='store_true',
        default=True,
        help='Сохранять отклонённые диалоги в .rejected.jsonl'
    )
    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Только анализ, без сохранения'
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Ошибка: файл не найден - {input_path}")
        return 1

    print(f"\n{'='*50}")
    print("ФИЛЬТРАЦИЯ ДИАЛОГОВ MITS")
    print(f"{'='*50}")
    print(f"Входной файл:      {input_path}")
    print(f"Выходной файл:     {output_path}")
    print(f"Мин. качество:     {args.min_quality}")
    print(f"{'='*50}\n")

    stats = filter_dataset(
        input_path=input_path,
        output_path=output_path,
        min_quality=args.min_quality,
        save_rejected=args.save_rejected
    )

    print_stats(stats)

    return 0 if stats.passed > 0 else 1


if __name__ == "__main__":
    exit(main())
