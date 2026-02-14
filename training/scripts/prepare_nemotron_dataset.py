#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Подготовка датасета для дообучения Nemotron-3-Nano-30B-A3B.

Особенности Nemotron:
- Использует <|im_start|>/<|im_end|> chat template (как Qwen)
- Для сохранения reasoning способностей нужен баланс 75%/25%
  (75% с reasoning, 25% без reasoning)
- Токены reasoning: token ID 12 и 13

Использование:
    python training/scripts/prepare_nemotron_dataset.py \
        --input data/training/cerebras_dialogs.jsonl \
        --output data/training/nemotron_ready.jsonl \
        --reasoning-ratio 0.75

    # Проверка формата
    python training/scripts/prepare_nemotron_dataset.py \
        --input data/training/cerebras_dialogs.jsonl \
        --validate-only
"""

import json
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from collections import Counter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class DatasetStats:
    """Статистика датасета."""
    total: int = 0
    with_reasoning: int = 0
    without_reasoning: int = 0
    disciplines: Dict[str, int] = None
    difficulties: Dict[str, int] = None
    personas: Dict[str, int] = None
    avg_turns: float = 0

    def __post_init__(self):
        self.disciplines = {}
        self.difficulties = {}
        self.personas = {}


def format_for_nemotron(conversation: List[Dict], include_reasoning: bool = True) -> List[Dict]:
    """
    Форматирование диалога под Nemotron chat template.

    Nemotron использует формат:
    <|im_start|>system
    {content}<|im_end|>
    <|im_start|>user
    {content}<|im_end|>
    <|im_start|>assistant
    {content}<|im_end|>

    Args:
        conversation: Исходный диалог
        include_reasoning: Включать ли reasoning в ответы

    Returns:
        Отформатированный диалог
    """
    formatted = []

    for msg in conversation:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Для assistant: обрабатываем JSON ответ
        if role == "assistant":
            try:
                # Пробуем распарсить как JSON
                data = json.loads(content)

                if include_reasoning:
                    # С reasoning: сохраняем все поля
                    formatted_content = json.dumps(data, ensure_ascii=False)
                else:
                    # Без reasoning: убираем поле reasoning
                    if "reasoning" in data:
                        del data["reasoning"]
                    formatted_content = json.dumps(data, ensure_ascii=False)

                formatted.append({
                    "role": "assistant",
                    "content": formatted_content
                })

            except json.JSONDecodeError:
                # Если не JSON - оставляем как есть
                formatted.append(msg)
        else:
            # system и user - просто копируем
            formatted.append(msg)

    return formatted


def process_dialog(
    dialog: Dict[str, Any],
    include_reasoning: bool
) -> Dict[str, Any]:
    """
    Обработка одного диалога.

    Args:
        dialog: Исходный диалог
        include_reasoning: Включать ли reasoning

    Returns:
        Обработанный диалог
    """
    conversations = dialog.get("conversations", [])
    metadata = dialog.get("metadata", {})

    # Форматируем под Nemotron
    formatted_conversations = format_for_nemotron(conversations, include_reasoning)

    # Добавляем метаданные о режиме
    metadata["reasoning_mode"] = include_reasoning
    metadata["model_target"] = "nemotron-3-nano-30b-a3b"

    return {
        "conversations": formatted_conversations,
        "metadata": metadata
    }


def load_dataset(input_path: Path) -> List[Dict[str, Any]]:
    """Загрузка датасета из JSONL."""
    dialogs = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                dialog = json.loads(line)
                dialogs.append(dialog)
            except json.JSONDecodeError as e:
                logger.warning(f"Ошибка парсинга строки {line_num}: {e}")

    logger.info(f"Загружено {len(dialogs)} диалогов из {input_path}")
    return dialogs


def save_dataset(dialogs: List[Dict[str, Any]], output_path: Path):
    """Сохранение датасета в JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        for dialog in dialogs:
            f.write(json.dumps(dialog, ensure_ascii=False) + '\n')

    logger.info(f"Сохранено {len(dialogs)} диалогов в {output_path}")


def calculate_stats(dialogs: List[Dict[str, Any]]) -> DatasetStats:
    """Расчёт статистики датасета."""
    stats = DatasetStats()
    stats.total = len(dialogs)

    total_turns = 0

    for dialog in dialogs:
        metadata = dialog.get("metadata", {})
        conversations = dialog.get("conversations", [])

        # Считаем reasoning mode
        if metadata.get("reasoning_mode", True):
            stats.with_reasoning += 1
        else:
            stats.without_reasoning += 1

        # Считаем дисциплины
        discipline = metadata.get("discipline", "unknown")
        stats.disciplines[discipline] = stats.disciplines.get(discipline, 0) + 1

        # Считаем сложности
        difficulty = metadata.get("difficulty", "unknown")
        stats.difficulties[difficulty] = stats.difficulties.get(difficulty, 0) + 1

        # Считаем персоны
        persona = metadata.get("persona", "unknown")
        stats.personas[persona] = stats.personas.get(persona, 0) + 1

        # Считаем повороты
        total_turns += len(conversations)

    stats.avg_turns = total_turns / len(dialogs) if dialogs else 0

    return stats


def print_stats(stats: DatasetStats):
    """Вывод статистики."""
    print(f"\n{'='*60}")
    print("СТАТИСТИКА ДАТАСЕТА")
    print(f"{'='*60}")
    print(f"Всего диалогов:       {stats.total}")
    print(f"С reasoning:          {stats.with_reasoning} ({100*stats.with_reasoning/stats.total:.1f}%)")
    print(f"Без reasoning:        {stats.without_reasoning} ({100*stats.without_reasoning/stats.total:.1f}%)")
    print(f"Среднее кол-во ходов: {stats.avg_turns:.1f}")

    print(f"\nПо дисциплинам:")
    for disc, count in sorted(stats.disciplines.items(), key=lambda x: -x[1]):
        print(f"  {disc}: {count} ({100*count/stats.total:.1f}%)")

    print(f"\nПо сложности:")
    for diff, count in sorted(stats.difficulties.items()):
        print(f"  {diff}: {count} ({100*count/stats.total:.1f}%)")

    print(f"\nПо персонам:")
    for pers, count in sorted(stats.personas.items(), key=lambda x: -x[1]):
        print(f"  {pers}: {count} ({100*count/stats.total:.1f}%)")

    print(f"{'='*60}\n")


def validate_dialog(dialog: Dict[str, Any]) -> List[str]:
    """
    Валидация диалога.

    Returns:
        Список ошибок (пустой если всё ок)
    """
    errors = []

    # Проверяем наличие conversations
    if "conversations" not in dialog:
        errors.append("Отсутствует поле 'conversations'")
        return errors

    conversations = dialog["conversations"]

    if not isinstance(conversations, list):
        errors.append("'conversations' должен быть списком")
        return errors

    if len(conversations) < 3:
        errors.append(f"Слишком мало сообщений: {len(conversations)}")

    # Проверяем роли
    roles = [msg.get("role") for msg in conversations]

    if "system" not in roles:
        errors.append("Отсутствует system сообщение")

    if "user" not in roles:
        errors.append("Отсутствует user сообщение")

    if "assistant" not in roles:
        errors.append("Отсутствует assistant сообщение")

    # Проверяем формат assistant ответов
    for i, msg in enumerate(conversations):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            try:
                data = json.loads(content)
                if "move" not in data:
                    errors.append(f"Сообщение {i}: отсутствует 'move'")
                if "message" not in data:
                    errors.append(f"Сообщение {i}: отсутствует 'message'")
            except json.JSONDecodeError:
                errors.append(f"Сообщение {i}: невалидный JSON в assistant")

    return errors


def prepare_dataset(
    input_path: Path,
    output_path: Path,
    reasoning_ratio: float = 0.75,
    shuffle: bool = True,
    validate: bool = True
) -> DatasetStats:
    """
    Подготовка датасета для Nemotron.

    Args:
        input_path: Путь к исходному датасету
        output_path: Путь для сохранения
        reasoning_ratio: Доля примеров с reasoning (0.0-1.0)
        shuffle: Перемешивать ли датасет
        validate: Валидировать ли диалоги

    Returns:
        Статистика датасета
    """
    logger.info(f"Загрузка датасета из {input_path}")
    dialogs = load_dataset(input_path)

    if not dialogs:
        logger.error("Датасет пуст!")
        return DatasetStats()

    # Валидация
    if validate:
        logger.info("Валидация диалогов...")
        valid_dialogs = []
        invalid_count = 0

        for dialog in dialogs:
            errors = validate_dialog(dialog)
            if errors:
                invalid_count += 1
                if invalid_count <= 5:  # Показываем первые 5 ошибок
                    logger.warning(f"Невалидный диалог: {errors}")
            else:
                valid_dialogs.append(dialog)

        if invalid_count > 0:
            logger.warning(f"Отфильтровано {invalid_count} невалидных диалогов")

        dialogs = valid_dialogs

    # Перемешивание
    if shuffle:
        random.shuffle(dialogs)

    # Определяем какие диалоги будут с reasoning
    n_with_reasoning = int(len(dialogs) * reasoning_ratio)
    reasoning_flags = [True] * n_with_reasoning + [False] * (len(dialogs) - n_with_reasoning)
    random.shuffle(reasoning_flags)

    # Обрабатываем диалоги
    logger.info(f"Обработка {len(dialogs)} диалогов (reasoning ratio: {reasoning_ratio:.0%})")
    processed_dialogs = []

    for dialog, include_reasoning in zip(dialogs, reasoning_flags):
        processed = process_dialog(dialog, include_reasoning)
        processed_dialogs.append(processed)

    # Сохраняем
    save_dataset(processed_dialogs, output_path)

    # Считаем статистику
    stats = calculate_stats(processed_dialogs)

    return stats


def main():
    """CLI для подготовки датасета."""
    parser = argparse.ArgumentParser(
        description="Подготовка датасета для дообучения Nemotron",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Стандартная подготовка (75% reasoning)
  python prepare_nemotron_dataset.py \\
      --input data/training/cerebras_dialogs.jsonl \\
      --output data/training/nemotron_ready.jsonl

  # Изменить баланс reasoning
  python prepare_nemotron_dataset.py \\
      --input data/training/cerebras_dialogs.jsonl \\
      --output data/training/nemotron_ready.jsonl \\
      --reasoning-ratio 0.8

  # Только валидация
  python prepare_nemotron_dataset.py \\
      --input data/training/cerebras_dialogs.jsonl \\
      --validate-only

  # Показать статистику существующего датасета
  python prepare_nemotron_dataset.py \\
      --input data/training/nemotron_ready.jsonl \\
      --stats-only
        """
    )

    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Путь к исходному датасету (JSONL)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Путь для сохранения (по умолчанию: input_nemotron.jsonl)'
    )
    parser.add_argument(
        '--reasoning-ratio',
        type=float,
        default=0.75,
        help='Доля примеров с reasoning (0.0-1.0, по умолчанию 0.75)'
    )
    parser.add_argument(
        '--no-shuffle',
        action='store_true',
        help='Не перемешивать датасет'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Пропустить валидацию'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Только валидация без обработки'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Только показать статистику'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Seed для воспроизводимости'
    )

    args = parser.parse_args()

    random.seed(args.seed)

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Ошибка: файл не найден: {input_path}")
        return 1

    # Режим только статистики
    if args.stats_only:
        dialogs = load_dataset(input_path)
        stats = calculate_stats(dialogs)
        print_stats(stats)
        return 0

    # Режим только валидации
    if args.validate_only:
        dialogs = load_dataset(input_path)

        print(f"\nВалидация {len(dialogs)} диалогов...")

        valid = 0
        invalid = 0
        all_errors = []

        for i, dialog in enumerate(dialogs):
            errors = validate_dialog(dialog)
            if errors:
                invalid += 1
                all_errors.append((i, errors))
            else:
                valid += 1

        print(f"\nРезультаты валидации:")
        print(f"  Валидных:     {valid} ({100*valid/len(dialogs):.1f}%)")
        print(f"  Невалидных:   {invalid} ({100*invalid/len(dialogs):.1f}%)")

        if all_errors and invalid <= 10:
            print(f"\nОшибки:")
            for idx, errors in all_errors[:10]:
                print(f"  Диалог {idx}: {errors}")

        return 0 if invalid == 0 else 1

    # Определяем output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem}_nemotron.jsonl"

    # Обработка
    print(f"\n{'='*60}")
    print("ПОДГОТОВКА ДАТАСЕТА ДЛЯ NEMOTRON")
    print(f"{'='*60}")
    print(f"Вход:              {input_path}")
    print(f"Выход:             {output_path}")
    print(f"Reasoning ratio:   {args.reasoning_ratio:.0%}")
    print(f"Shuffle:           {not args.no_shuffle}")
    print(f"Validate:          {not args.no_validate}")
    print(f"{'='*60}\n")

    stats = prepare_dataset(
        input_path=input_path,
        output_path=output_path,
        reasoning_ratio=args.reasoning_ratio,
        shuffle=not args.no_shuffle,
        validate=not args.no_validate
    )

    print_stats(stats)

    print(f"Готово! Датасет сохранён в: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
