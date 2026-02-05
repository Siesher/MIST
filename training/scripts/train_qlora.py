#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт QLoRA дообучения для MITS.

Дообучает LLM на сократических диалогах с использованием:
- QLoRA (4-bit квантование + LoRA адаптеры)
- Gradient checkpointing для экономии VRAM
- 8-bit оптимизатор

Требования:
    pip install transformers peft bitsandbytes accelerate datasets trl

Использование:
    python training/scripts/train_qlora.py \
        --config training/configs/qlora_rtx2080.yaml

    # Или с переопределением параметров:
    python training/scripts/train_qlora.py \
        --config training/configs/qlora_rtx2080.yaml \
        --epochs 5 \
        --output outputs/mits-v2
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Проверка зависимостей
MISSING_DEPS = []
try:
    import torch
except ImportError:
    MISSING_DEPS.append("torch")

try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
        Trainer,
    )
except ImportError:
    MISSING_DEPS.append("transformers")

try:
    from peft import (
        LoraConfig,
        get_peft_model,
        prepare_model_for_kbit_training,
        TaskType,
    )
except ImportError:
    MISSING_DEPS.append("peft")

try:
    from datasets import load_dataset, Dataset
except ImportError:
    MISSING_DEPS.append("datasets")

try:
    from trl import SFTTrainer, DataCollatorForCompletionOnlyLM
except ImportError:
    MISSING_DEPS.append("trl")

if MISSING_DEPS:
    print(f"Ошибка: отсутствуют зависимости: {', '.join(MISSING_DEPS)}")
    print("Установите: pip install transformers peft bitsandbytes accelerate datasets trl")
    sys.exit(1)


def load_config(config_path: str) -> Dict[str, Any]:
    """Загрузка конфигурации из YAML."""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    return config


def format_conversation_qwen(example: Dict) -> str:
    """
    Форматирование диалога для Qwen3 chat template.

    Qwen3 формат:
    <|im_start|>system
    {system_prompt}<|im_end|>
    <|im_start|>user
    {user_message}<|im_end|>
    <|im_start|>assistant
    {assistant_response}<|im_end|>
    """
    conversations = example.get("conversations", [])
    formatted_parts = []

    for msg in conversations:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role in ["system", "user", "assistant"]:
            formatted_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")

    return "\n".join(formatted_parts)


def format_conversation_generic(example: Dict) -> str:
    """
    Универсальное форматирование для других моделей (Phi, SmolLM и др.)

    Формат:
    <|system|>
    {system_prompt}
    <|user|>
    {user_message}
    <|assistant|>
    {assistant_response}
    """
    conversations = example.get("conversations", [])
    formatted_parts = []

    for msg in conversations:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            formatted_parts.append(f"<|system|>\n{content}")
        elif role == "user":
            formatted_parts.append(f"<|user|>\n{content}")
        elif role == "assistant":
            formatted_parts.append(f"<|assistant|>\n{content}")

    return "\n".join(formatted_parts)


def format_conversation(example: Dict, model_name: str = "") -> str:
    """
    Автоматический выбор формата диалога по модели.

    Args:
        example: Пример с диалогом
        model_name: Имя модели для определения формата

    Returns:
        Отформатированный текст
    """
    model_lower = model_name.lower()

    # Qwen3 использует im_start/im_end формат
    if "qwen" in model_lower:
        return format_conversation_qwen(example)

    # Для остальных моделей - универсальный формат
    return format_conversation_generic(example)


def load_training_data(config: Dict) -> Dataset:
    """Загрузка и подготовка данных для обучения."""
    data_config = config.get("data", {})
    model_config = config.get("model", {})
    train_file = data_config.get("train_file")
    model_name = model_config.get("name", "")

    if not train_file or not Path(train_file).exists():
        raise FileNotFoundError(f"Файл данных не найден: {train_file}")

    logger.info(f"Загрузка данных из {train_file}")

    # Загружаем JSONL
    dataset = load_dataset("json", data_files=train_file, split="train")

    logger.info(f"Загружено примеров: {len(dataset)}")

    # Форматируем диалоги (с учетом модели)
    def format_example(example):
        example["text"] = format_conversation(example, model_name)
        return example

    dataset = dataset.map(format_example)

    # Разделение на train/eval
    test_split = data_config.get("test_split", 0.1)
    if test_split > 0:
        split_dataset = dataset.train_test_split(test_size=test_split, seed=42)
        train_dataset = split_dataset["train"]
        eval_dataset = split_dataset["test"]
    else:
        train_dataset = dataset
        eval_dataset = None

    logger.info(f"Train: {len(train_dataset)}, Eval: {len(eval_dataset) if eval_dataset else 0}")

    return train_dataset, eval_dataset


def create_model_and_tokenizer(config: Dict):
    """Создание модели и токенизатора с QLoRA."""
    model_config = config.get("model", {})
    quant_config = config.get("quantization", {})
    lora_config = config.get("lora", {})

    model_name = model_config.get("name", "Qwen/Qwen2.5-7B-Instruct")
    logger.info(f"Загрузка модели: {model_name}")

    # BitsAndBytes конфигурация для 4-bit квантования
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=quant_config.get("load_in_4bit", True),
        bnb_4bit_compute_dtype=getattr(torch, quant_config.get("bnb_4bit_compute_dtype", "bfloat16")),
        bnb_4bit_quant_type=quant_config.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_use_double_quant=quant_config.get("bnb_4bit_use_double_quant", True),
    )

    # Загрузка модели
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=model_config.get("trust_remote_code", True),
        torch_dtype=getattr(torch, model_config.get("torch_dtype", "bfloat16")),
    )

    # Подготовка для k-bit обучения
    model = prepare_model_for_kbit_training(model)

    # LoRA конфигурация
    peft_config = LoraConfig(
        r=lora_config.get("r", 32),
        lora_alpha=lora_config.get("lora_alpha", 64),
        lora_dropout=lora_config.get("lora_dropout", 0.05),
        bias=lora_config.get("bias", "none"),
        target_modules=lora_config.get("target_modules", [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"
        ]),
        task_type=TaskType.CAUSAL_LM,
    )

    # Применение LoRA
    model = get_peft_model(model, peft_config)

    # Вывод информации о параметрах
    trainable, total = model.get_nb_trainable_parameters()
    logger.info(f"Обучаемые параметры: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # Токенизатор
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=model_config.get("trust_remote_code", True),
    )

    # Настройка токенизатора
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    return model, tokenizer


def create_training_args(config: Dict) -> TrainingArguments:
    """Создание аргументов обучения."""
    training_config = config.get("training", {})
    output_config = config.get("output", {})

    output_dir = output_config.get("output_dir", "outputs/mits-tutor")

    return TrainingArguments(
        output_dir=output_dir,

        # Batch size
        per_device_train_batch_size=training_config.get("per_device_train_batch_size", 1),
        per_device_eval_batch_size=training_config.get("per_device_eval_batch_size", 1),
        gradient_accumulation_steps=training_config.get("gradient_accumulation_steps", 16),

        # Оптимизатор
        learning_rate=training_config.get("learning_rate", 2e-4),
        weight_decay=training_config.get("weight_decay", 0.01),
        lr_scheduler_type=training_config.get("lr_scheduler_type", "cosine"),
        warmup_ratio=training_config.get("warmup_ratio", 0.03),
        optim=training_config.get("optim", "paged_adamw_8bit"),

        # Эпохи
        num_train_epochs=training_config.get("num_train_epochs", 3),
        max_steps=training_config.get("max_steps", -1),

        # Память
        gradient_checkpointing=training_config.get("gradient_checkpointing", True),
        fp16=training_config.get("fp16", False),
        bf16=training_config.get("bf16", True),

        # Логирование
        logging_steps=training_config.get("logging_steps", 10),
        logging_first_step=training_config.get("logging_first_step", True),
        report_to=["tensorboard"],

        # Сохранение
        save_steps=training_config.get("save_steps", 500),
        save_total_limit=training_config.get("save_total_limit", 3),

        # Оценка
        eval_strategy=training_config.get("eval_strategy", "steps"),
        eval_steps=training_config.get("eval_steps", 500),

        # Seed
        seed=training_config.get("seed", 42),

        # Прочее
        remove_unused_columns=False,
        dataloader_num_workers=config.get("hardware", {}).get("dataloader_num_workers", 2),
    )


def train(config: Dict):
    """Основной цикл обучения."""
    logger.info("="*50)
    logger.info("MITS QLoRA Training")
    logger.info("="*50)

    # Проверка CUDA
    if not torch.cuda.is_available():
        logger.warning("CUDA не доступна! Обучение будет очень медленным.")
    else:
        logger.info(f"CUDA: {torch.cuda.get_device_name(0)}")
        logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    # Загрузка данных
    train_dataset, eval_dataset = load_training_data(config)

    # Создание модели
    model, tokenizer = create_model_and_tokenizer(config)

    # Аргументы обучения
    training_args = create_training_args(config)

    # Настройка для completion-only обучения
    data_config = config.get("data", {})
    if data_config.get("completion_only", True):
        response_template = data_config.get("response_template", "<|assistant|>")
        collator = DataCollatorForCompletionOnlyLM(
            response_template=response_template,
            tokenizer=tokenizer,
        )
    else:
        collator = None

    # SFT Trainer
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        dataset_text_field="text",
        max_seq_length=config.get("training", {}).get("max_seq_length", 1024),
        data_collator=collator,
        packing=False,
    )

    # Запуск обучения
    logger.info("Начало обучения...")
    start_time = datetime.now()

    train_result = trainer.train()

    # Сохранение модели
    output_dir = config.get("output", {}).get("output_dir", "outputs/mits-tutor")
    final_dir = Path(output_dir) / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    # Статистика
    elapsed = datetime.now() - start_time
    logger.info("="*50)
    logger.info("ОБУЧЕНИЕ ЗАВЕРШЕНО")
    logger.info("="*50)
    logger.info(f"Время: {elapsed}")
    logger.info(f"Модель сохранена: {final_dir}")

    # Метрики
    if train_result.metrics:
        logger.info("Метрики:")
        for key, value in train_result.metrics.items():
            logger.info(f"  {key}: {value}")

    return trainer


def main():
    """CLI для запуска обучения."""
    parser = argparse.ArgumentParser(
        description="QLoRA дообучение MITS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:

  # Стандартное обучение
  python train_qlora.py --config training/configs/qlora_rtx2080.yaml

  # С переопределением параметров
  python train_qlora.py \\
      --config training/configs/qlora_rtx2080.yaml \\
      --epochs 5 \\
      --lr 1e-4 \\
      --output outputs/mits-v2

  # Тестовый запуск (1 эпоха, 100 шагов)
  python train_qlora.py \\
      --config training/configs/qlora_rtx2080.yaml \\
      --max-steps 100 \\
      --output outputs/test-run
        """
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        required=True,
        help='Путь к YAML конфигурации'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=None,
        help='Переопределить количество эпох'
    )
    parser.add_argument(
        '--lr',
        type=float,
        default=None,
        help='Переопределить learning rate'
    )
    parser.add_argument(
        '--max-steps',
        type=int,
        default=None,
        help='Переопределить max_steps (-1 для отключения)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Переопределить output_dir'
    )
    parser.add_argument(
        '--data',
        type=str,
        default=None,
        help='Переопределить путь к данным'
    )

    args = parser.parse_args()

    # Загрузка конфигурации
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Ошибка: конфигурация не найдена - {config_path}")
        return 1

    config = load_config(str(config_path))

    # Переопределение параметров из CLI
    if args.epochs:
        config.setdefault("training", {})["num_train_epochs"] = args.epochs

    if args.lr:
        config.setdefault("training", {})["learning_rate"] = args.lr

    if args.max_steps is not None:
        config.setdefault("training", {})["max_steps"] = args.max_steps

    if args.output:
        config.setdefault("output", {})["output_dir"] = args.output

    if args.data:
        config.setdefault("data", {})["train_file"] = args.data

    # Вывод конфигурации
    print(f"\n{'='*50}")
    print("КОНФИГУРАЦИЯ ОБУЧЕНИЯ")
    print(f"{'='*50}")
    print(f"Модель:            {config.get('model', {}).get('name')}")
    print(f"Данные:            {config.get('data', {}).get('train_file')}")
    print(f"Эпохи:             {config.get('training', {}).get('num_train_epochs')}")
    print(f"Learning rate:     {config.get('training', {}).get('learning_rate')}")
    print(f"LoRA r:            {config.get('lora', {}).get('r')}")
    print(f"Output:            {config.get('output', {}).get('output_dir')}")
    print(f"{'='*50}\n")

    # Запуск обучения
    try:
        trainer = train(config)
        return 0
    except Exception as e:
        logger.error(f"Ошибка обучения: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
