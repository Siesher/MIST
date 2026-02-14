#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI скрипт оценки качества модели репетитора.

Использование:
    python evaluation/evaluate_model.py --test-set data/test_dialogs.jsonl
    python evaluation/evaluate_model.py --model phi4-mini --compare-teacher nemotron:30b
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.metrics import (
    TutorEvaluator,
    EvaluationResult,
    compare_models,
    print_comparison,
    load_test_dialogs
)

logger = logging.getLogger(__name__)


def generate_responses_from_model(
    model_name: str,
    dialogs: List[Dict[str, Any]],
    use_orchestrator: bool = True
) -> List[str]:
    """
    Генерация ответов модели для тестовых диалогов.

    Args:
        model_name: Имя модели (пресет или путь)
        dialogs: Список тестовых диалогов
        use_orchestrator: Использовать оркестратор агентов

    Returns:
        Список ответов модели
    """
    responses = []

    if use_orchestrator:
        try:
            from src.agents.orchestrator import create_orchestrator, TurnContext
            from src.inference.model_manager import get_model_manager, ModelPurpose

            # Получаем модель
            manager = get_model_manager()
            llm_client = manager.get_model(
                purpose=ModelPurpose.TUTOR,
                preset=model_name
            )

            # Создаём оркестратор
            orchestrator = create_orchestrator(llm_client, mode="full", verify=False)

            for dialog in dialogs:
                # Извлекаем данные из диалога
                conversations = dialog.get("conversations", [])
                metadata = dialog.get("metadata", {})

                # Находим последний ввод пользователя
                problem = ""
                student_input = ""
                history = []

                for msg in conversations:
                    role = msg.get("role", "")
                    content = msg.get("content", "")

                    if role == "system":
                        continue
                    elif role == "user":
                        if "Задача:" in content:
                            problem = content
                        student_input = content
                    elif role == "assistant":
                        history.append(msg)

                # Создаём контекст
                context = TurnContext(
                    problem=problem or student_input,
                    student_input=student_input,
                    topic=metadata.get("topic"),
                    history=history
                )

                # Генерируем ответ
                result = orchestrator.process_turn(context)
                responses.append(result.to_json())

        except ImportError as e:
            logger.warning(f"Не удалось загрузить оркестратор: {e}")
            logger.warning("Используем прямую генерацию через LLM")
            use_orchestrator = False

    if not use_orchestrator:
        # Прямая генерация через LLM
        try:
            from src.models.llm_client import LLMClient

            client = LLMClient(model=model_name)

            for dialog in dialogs:
                conversations = dialog.get("conversations", [])

                # Собираем промпт
                prompt_parts = []
                system_prompt = None

                for msg in conversations:
                    role = msg.get("role", "")
                    content = msg.get("content", "")

                    if role == "system":
                        system_prompt = content
                    elif role == "user":
                        prompt_parts.append(f"Ученик: {content}")

                response = client.generate(
                    prompt="\n".join(prompt_parts),
                    system_prompt=system_prompt,
                    temperature=0.7
                )
                responses.append(response)

        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            raise

    return responses


def extract_reference_responses(dialogs: List[Dict[str, Any]]) -> List[str]:
    """
    Извлечение эталонных ответов из диалогов.

    Args:
        dialogs: Список диалогов

    Returns:
        Список эталонных ответов assistant
    """
    responses = []

    for dialog in dialogs:
        conversations = dialog.get("conversations", [])

        # Берём последний ответ assistant
        last_assistant = None
        for msg in conversations:
            if msg.get("role") == "assistant":
                last_assistant = msg.get("content", "")

        if last_assistant:
            responses.append(last_assistant)
        else:
            responses.append("")

    return responses


def run_evaluation(
    test_file: str,
    model_name: Optional[str] = None,
    compare_teacher: Optional[str] = None,
    output_file: Optional[str] = None,
    limit: Optional[int] = None
) -> EvaluationResult:
    """
    Запуск оценки модели.

    Args:
        test_file: Путь к файлу с тестовыми диалогами
        model_name: Имя модели для оценки (если None - оценка эталонов)
        compare_teacher: Имя модели-учителя для сравнения
        output_file: Файл для сохранения результатов
        limit: Ограничение количества диалогов

    Returns:
        EvaluationResult с метриками
    """
    # Загружаем тестовые диалоги
    logger.info(f"Загрузка тестовых диалогов из {test_file}")
    dialogs = load_test_dialogs(test_file)

    if limit:
        dialogs = dialogs[:limit]

    logger.info(f"Загружено диалогов: {len(dialogs)}")

    # Создаём оценщик
    evaluator = TutorEvaluator()

    # Извлекаем правильные ответы (если есть в метаданных)
    correct_answers = []
    for dialog in dialogs:
        metadata = dialog.get("metadata", {})
        correct_answers.append(metadata.get("answer", None))

    if model_name:
        # Генерируем ответы модели
        logger.info(f"Генерация ответов модели: {model_name}")
        student_responses = generate_responses_from_model(model_name, dialogs)
    else:
        # Оцениваем эталонные ответы из датасета
        logger.info("Оценка эталонных ответов из датасета")
        student_responses = extract_reference_responses(dialogs)

    # Оценка
    logger.info("Оценка ответов...")
    student_result = evaluator.evaluate_batch(
        student_responses,
        correct_answers=correct_answers if any(correct_answers) else None
    )

    # Вывод результатов
    student_result.print_report()

    # Сравнение с учителем
    if compare_teacher:
        logger.info(f"Генерация ответов учителя: {compare_teacher}")
        teacher_responses = generate_responses_from_model(compare_teacher, dialogs)

        teacher_result = evaluator.evaluate_batch(
            teacher_responses,
            correct_answers=correct_answers if any(correct_answers) else None
        )

        comparison = compare_models(teacher_result, student_result)
        print_comparison(comparison)

    # Сохранение результатов
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        results = {
            'model': model_name or 'reference',
            'test_file': test_file,
            'num_dialogs': len(dialogs),
            'metrics': student_result.to_dict()
        }

        if compare_teacher:
            results['teacher'] = compare_teacher
            results['comparison'] = comparison

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"Результаты сохранены в {output_file}")

    return student_result


def main():
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description="Оценка качества модели сократического репетитора"
    )

    parser.add_argument(
        '--test-set',
        type=str,
        required=True,
        help='Путь к файлу с тестовыми диалогами (JSONL)'
    )

    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Модель для оценки (пресет или имя Ollama). Если не указано - оценка эталонов.'
    )

    parser.add_argument(
        '--compare-teacher',
        type=str,
        default=None,
        help='Модель-учитель для сравнения'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Файл для сохранения результатов (JSON)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Ограничение количества диалогов'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Подробный вывод'
    )

    args = parser.parse_args()

    # Настройка логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Проверка файла
    if not Path(args.test_set).exists():
        logger.error(f"Файл не найден: {args.test_set}")
        sys.exit(1)

    # Запуск оценки
    try:
        run_evaluation(
            test_file=args.test_set,
            model_name=args.model,
            compare_teacher=args.compare_teacher,
            output_file=args.output,
            limit=args.limit
        )
    except Exception as e:
        logger.error(f"Ошибка при оценке: {e}")
        if args.verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
