#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инкрементальная генерация диалогов с сохранением после каждого диалога.
Устойчива к прерываниям - можно продолжить с места остановки.

Использование:
    python training/scripts/generate_incremental.py \
        --output data/training/dialogs.jsonl \
        --dialogs-per-combo 3
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
import logging
import sys

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.scripts.cerebras_dialog_generator import (
    CerebrasDialogGenerator,
    DialogConfig,
    Discipline,
    StudentPersona,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def count_existing_dialogs(output_path: Path) -> int:
    """Подсчёт существующих диалогов в файле."""
    if not output_path.exists():
        return 0

    count = 0
    with open(output_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def get_completed_combinations(output_path: Path) -> set:
    """Получение уже сгенерированных комбинаций."""
    completed = set()

    if not output_path.exists():
        return completed

    with open(output_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                dialog = json.loads(line)
                meta = dialog.get("metadata", {})
                key = (
                    meta.get("discipline", ""),
                    meta.get("topic", ""),
                    meta.get("difficulty", ""),
                    meta.get("persona", ""),
                    meta.get("combo_index", 0)
                )
                completed.add(key)
            except:
                pass

    return completed


def append_dialog(dialog: dict, output_path: Path):
    """Добавление диалога в файл."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(dialog, ensure_ascii=False) + '\n')


def generate_incremental(
    output_path: Path,
    disciplines: list = None,
    dialogs_per_combo: int = 3,
    model: str = None
):
    """
    Инкрементальная генерация с сохранением после каждого диалога.

    Args:
        output_path: Путь к файлу для сохранения
        disciplines: Список дисциплин (по умолчанию все)
        dialogs_per_combo: Диалогов на комбинацию
        model: Модель Cerebras
    """
    generator = CerebrasDialogGenerator(model=model)

    if disciplines is None:
        disciplines = list(Discipline)

    difficulties = ["easy", "medium", "hard"]
    personas = list(StudentPersona)

    # Загружаем уже сгенерированные комбинации
    completed = get_completed_combinations(output_path)
    existing_count = count_existing_dialogs(output_path)

    logger.info(f"Найдено {existing_count} существующих диалогов")
    logger.info(f"Продолжаем генерацию...")

    # Подсчёт общего количества
    total_combos = 0
    for disc in disciplines:
        topics = list(generator.DISCIPLINE_TOPICS.get(disc, {}).keys())
        total_combos += len(topics) * len(difficulties) * len(personas) * dialogs_per_combo

    generated = 0
    skipped = 0
    failed = 0

    print(f"\n{'='*60}")
    print("ИНКРЕМЕНТАЛЬНАЯ ГЕНЕРАЦИЯ ДИАЛОГОВ")
    print(f"{'='*60}")
    print(f"Дисциплины:        {[d.value for d in disciplines]}")
    print(f"Диалогов/комбо:    {dialogs_per_combo}")
    print(f"Всего комбинаций:  {total_combos}")
    print(f"Уже сгенерировано: {existing_count}")
    print(f"Выходной файл:     {output_path}")
    print(f"{'='*60}\n")

    current = 0

    for disc in disciplines:
        topics = list(generator.DISCIPLINE_TOPICS.get(disc, {}).keys())

        for topic in topics:
            for difficulty in difficulties:
                for persona in personas:
                    for combo_idx in range(dialogs_per_combo):
                        current += 1

                        # Проверяем, не сгенерирован ли уже
                        key = (disc.value, topic, difficulty, persona.value, combo_idx)
                        if key in completed:
                            skipped += 1
                            continue

                        logger.info(
                            f"[{current}/{total_combos}] {disc.value}:{topic} | "
                            f"{difficulty} | {persona.value} | #{combo_idx+1}"
                        )

                        config = DialogConfig(
                            discipline=disc,
                            topic=topic,
                            difficulty=difficulty,
                            persona=persona
                        )

                        dialog = generator.generate_dialog(config)

                        if dialog:
                            # Добавляем индекс комбинации в метаданные
                            dialog["metadata"]["combo_index"] = combo_idx

                            # Сразу сохраняем
                            append_dialog(dialog, output_path)
                            generated += 1
                            logger.info(f"  -> Сохранено ({generated} новых)")
                        else:
                            failed += 1
                            logger.warning(f"  -> Не удалось сгенерировать")

    # Итоговая статистика
    print(f"\n{'='*60}")
    print("РЕЗУЛЬТАТЫ ГЕНЕРАЦИИ")
    print(f"{'='*60}")
    print(f"Новых диалогов:    {generated}")
    print(f"Пропущено (уже есть): {skipped}")
    print(f"Не удалось:        {failed}")
    print(f"Всего в файле:     {existing_count + generated}")
    print(f"Успешность:        {100*generated/(generated+failed):.1f}%" if (generated+failed) > 0 else "N/A")
    print(f"{'='*60}\n")

    return generated


def main():
    parser = argparse.ArgumentParser(
        description="Инкрементальная генерация диалогов (устойчива к прерываниям)"
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='data/training/dialogs_incremental.jsonl',
        help='Путь к выходному файлу'
    )
    parser.add_argument(
        '--discipline',
        type=str,
        default='all',
        help='Дисциплина или "all" для всех'
    )
    parser.add_argument(
        '--dialogs-per-combo',
        type=int,
        default=3,
        help='Количество диалогов на комбинацию'
    )
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Модель Cerebras'
    )

    args = parser.parse_args()

    output_path = Path(args.output)

    if args.discipline.lower() == 'all':
        disciplines = list(Discipline)
    else:
        disciplines = [Discipline(args.discipline.lower())]

    generate_incremental(
        output_path=output_path,
        disciplines=disciplines,
        dialogs_per_combo=args.dialogs_per_combo,
        model=args.model
    )


if __name__ == "__main__":
    main()
