#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Фильтрация диалогов для обучения MITS.

Проверяет:
- Валидность JSON в ответах ассистента
- Наличие полей move и message
- Отсутствие смешения языков (китайский, испанский и т.д.)
- Сократический метод (не начинается с tell)
- Минимальное количество ходов

Использование:
    python training/scripts/filter_dialogs.py \
        --input data/training/cerebras_dialogs.jsonl \
        --output data/training/filtered_dialogs.jsonl \
        --min-turns 4
"""

import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class FilterStats:
    """Статистика фильтрации."""
    total: int = 0
    passed: int = 0
    invalid_json: int = 0
    missing_fields: int = 0
    language_mix: int = 0
    starts_with_tell: int = 0
    too_few_turns: int = 0


# Паттерны для определения нежелательных символов/языков
NON_RUSSIAN_PATTERNS = [
    r'[\u4e00-\u9fff]',  # Китайский
    r'[\u3040-\u309f]',  # Хирагана
    r'[\u30a0-\u30ff]',  # Катакана
    r'[\uac00-\ud7af]',  # Корейский
    # Испанские/французские слова (частые ошибки LLM)
    r'\b(puedes|puede|qué|cómo|está|avoir|être|comme)\b',
]


def check_language_purity(text: str) -> bool:
    """
    Проверка на смешение языков.

    Returns:
        True если текст чистый (без смешения), False если есть проблемы
    """
    for pattern in NON_RUSSIAN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    return True


def validate_assistant_response(content: str) -> Tuple[bool, str]:
    """
    Валидация ответа ассистента.

    Returns:
        (is_valid, error_message)
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"

    if "move" not in data:
        return False, "Missing 'move' field"

    if "message" not in data:
        return False, "Missing 'message' field"

    valid_moves = {"scaffolding", "problematize", "rectify", "encourage", "hint", "tell"}
    if data["move"] not in valid_moves:
        return False, f"Invalid move: {data['move']}"

    return True, ""


def filter_dialog(dialog: Dict[str, Any], min_turns: int = 4) -> Tuple[bool, str]:
    """
    Фильтрация одного диалога.

    Returns:
        (passed, rejection_reason)
    """
    conversations = dialog.get("conversations", [])

    # Проверка минимального количества ходов
    if len(conversations) < min_turns:
        return False, "too_few_turns"

    # Счётчик ответов ассистента
    assistant_count = 0
    first_assistant_move = None

    for msg in conversations:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Проверка языка во всех сообщениях
        if not check_language_purity(content):
            return False, "language_mix"

        if role == "assistant":
            assistant_count += 1

            # Валидация JSON ответа
            is_valid, error = validate_assistant_response(content)
            if not is_valid:
                if "Invalid JSON" in error:
                    return False, "invalid_json"
                else:
                    return False, "missing_fields"

            # Запоминаем первый ход ассистента
            if first_assistant_move is None:
                try:
                    data = json.loads(content)
                    first_assistant_move = data.get("move", "")
                except:
                    pass

    # Проверка сократического метода - не должен начинаться с tell
    if first_assistant_move == "tell":
        return False, "starts_with_tell"

    return True, ""


def filter_dataset(
    input_path: Path,
    output_path: Path,
    min_turns: int = 4
) -> FilterStats:
    """
    Фильтрация датасета.

    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения отфильтрованных данных
        min_turns: Минимальное количество сообщений в диалоге

    Returns:
        Статистика фильтрации
    """
    stats = FilterStats()
    filtered_dialogs = []

    # Загрузка
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                dialog = json.loads(line)
                stats.total += 1
            except json.JSONDecodeError:
                logger.warning(f"Ошибка парсинга строки {line_num}")
                stats.invalid_json += 1
                continue

            # Фильтрация
            passed, reason = filter_dialog(dialog, min_turns)

            if passed:
                stats.passed += 1
                filtered_dialogs.append(dialog)
            else:
                # Обновляем статистику по причине отклонения
                if reason == "invalid_json":
                    stats.invalid_json += 1
                elif reason == "missing_fields":
                    stats.missing_fields += 1
                elif reason == "language_mix":
                    stats.language_mix += 1
                elif reason == "starts_with_tell":
                    stats.starts_with_tell += 1
                elif reason == "too_few_turns":
                    stats.too_few_turns += 1

    # Сохранение
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for dialog in filtered_dialogs:
            f.write(json.dumps(dialog, ensure_ascii=False) + '\n')

    return stats


def print_stats(stats: FilterStats, input_path: Path, output_path: Path):
    """Вывод статистики фильтрации."""
    print(f"\n{'='*60}")
    print("РЕЗУЛЬТАТЫ ФИЛЬТРАЦИИ")
    print(f"{'='*60}")
    print(f"Входной файл:      {input_path}")
    print(f"Выходной файл:     {output_path}")
    print(f"{'='*60}")
    print(f"Всего диалогов:    {stats.total}")
    print(f"Прошло фильтр:     {stats.passed} ({100*stats.passed/max(1,stats.total):.1f}%)")
    print(f"{'='*60}")
    print("Причины отклонения:")
    print(f"  Невалидный JSON:   {stats.invalid_json}")
    print(f"  Отсутствие полей:  {stats.missing_fields}")
    print(f"  Смешение языков:   {stats.language_mix}")
    print(f"  Начинается с tell: {stats.starts_with_tell}")
    print(f"  Мало ходов:        {stats.too_few_turns}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Фильтрация диалогов для обучения MITS"
    )
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Путь к исходному датасету'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Путь для сохранения (по умолчанию: input_filtered.jsonl)'
    )
    parser.add_argument(
        '--min-turns',
        type=int,
        default=4,
        help='Минимальное количество сообщений в диалоге'
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Ошибка: файл не найден: {input_path}")
        return 1

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem}_filtered.jsonl"

    logger.info(f"Фильтрация {input_path}...")
    stats = filter_dataset(input_path, output_path, args.min_turns)
    print_stats(stats, input_path, output_path)

    return 0


if __name__ == "__main__":
    exit(main())
