#!/usr/bin/env python3
"""
MITS SFT Training Script

QLoRA fine-tuning of student model on synthetic tutoring dialogs.
Designed for Google Colab A100 or local RTX 4090/3090.

Usage:
    python training/scripts/train_sft.py --config training/configs/qlora_config.yaml
    python training/scripts/train_sft.py --config training/configs/qlora_config.yaml --preset colab_a100
"""

import argparse
import os
import json
from pathlib import Path
from typing import Optional
import yaml

import torch
from datasets import load_dataset, Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer, DataCollatorForCompletionOnlyLM

import structlog

# Setup logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)
logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

def load_config(config_path: str, preset: Optional[str] = None) -> dict:
    """Load training configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Apply preset if specified
    if preset and preset in config.get('presets', {}):
        preset_config = config['presets'][preset]
        logger.info("applying_preset", preset=preset)

        # Merge preset into config
        for key, value in preset_config.items():
            if isinstance(value, dict):
                if key not in config:
                    config[key] = {}
                config[key].update(value)
            else:
                # Put in training section
                if 'training' not in config:
                    config['training'] = {}
                config['training'][key] = value

    return config


# ═══════════════════════════════════════════════════════════════════════════
# Model Setup
# ═══════════════════════════════════════════════════════════════════════════

def setup_model_and_tokenizer(config: dict):
    """
    Setup model with QLoRA configuration.

    Returns:
        (model, tokenizer) tuple
    """
    model_config = config['model']
    quant_config = config['quantization']
    lora_config = config['lora']

    logger.info("loading_model", model=model_config['name'])

    # Quantization config for 4-bit
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=quant_config['load_in_4bit'],
        bnb_4bit_compute_dtype=getattr(torch, quant_config['bnb_4bit_compute_dtype']),
        bnb_4bit_quant_type=quant_config['bnb_4bit_quant_type'],
        bnb_4bit_use_double_quant=quant_config['bnb_4bit_use_double_quant']
    )

    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_config['name'],
        quantization_config=bnb_config,
        device_map=model_config.get('device_map', 'auto'),
        trust_remote_code=model_config.get('trust_remote_code', True),
        torch_dtype=getattr(torch, model_config.get('torch_dtype', 'bfloat16')),
        attn_implementation=model_config.get('attn_implementation', None)
    )

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        model_config['name'],
        trust_remote_code=True
    )

    # Set pad token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # Prepare for k-bit training
    model = prepare_model_for_kbit_training(model)

    # Setup LoRA
    peft_config = LoraConfig(
        r=lora_config['r'],
        lora_alpha=lora_config['lora_alpha'],
        target_modules=lora_config['target_modules'],
        lora_dropout=lora_config['lora_dropout'],
        bias=lora_config['bias'],
        task_type=lora_config['task_type']
    )

    # Apply LoRA
    model = get_peft_model(model, peft_config)

    # Print trainable parameters
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(
        "model_loaded",
        trainable_params=f"{trainable_params:,}",
        total_params=f"{total_params:,}",
        trainable_pct=f"{100 * trainable_params / total_params:.2f}%"
    )

    return model, tokenizer


# ═══════════════════════════════════════════════════════════════════════════
# Dataset
# ═══════════════════════════════════════════════════════════════════════════

def load_training_dataset(config: dict, tokenizer) -> tuple:
    """
    Load and prepare training dataset.

    Returns:
        (train_dataset, eval_dataset) tuple
    """
    dataset_config = config['dataset']

    train_path = dataset_config['train_path']
    eval_path = dataset_config.get('eval_path')

    logger.info("loading_dataset", train=train_path, eval=eval_path)

    # Load datasets
    train_dataset = load_dataset('json', data_files=train_path, split='train')

    eval_dataset = None
    if eval_path and Path(eval_path).exists():
        eval_dataset = load_dataset('json', data_files=eval_path, split='train')

    logger.info(
        "dataset_loaded",
        train_size=len(train_dataset),
        eval_size=len(eval_dataset) if eval_dataset else 0
    )

    return train_dataset, eval_dataset


def format_chat_example(example, tokenizer):
    """Format a single example using chat template."""
    conversations = example['conversations']

    # Apply chat template
    text = tokenizer.apply_chat_template(
        conversations,
        tokenize=False,
        add_generation_prompt=False
    )

    return {"text": text}


# ═══════════════════════════════════════════════════════════════════════════
# Training
# ═══════════════════════════════════════════════════════════════════════════

def create_trainer(
    model,
    tokenizer,
    train_dataset,
    eval_dataset,
    config: dict
) -> SFTTrainer:
    """Create SFTTrainer with configuration."""

    training_config = config['training']
    dataset_config = config['dataset']

    # Format datasets
    train_dataset = train_dataset.map(
        lambda x: format_chat_example(x, tokenizer),
        remove_columns=train_dataset.column_names
    )

    if eval_dataset:
        eval_dataset = eval_dataset.map(
            lambda x: format_chat_example(x, tokenizer),
            remove_columns=eval_dataset.column_names
        )

    # Training arguments
    training_args = TrainingArguments(
        output_dir=training_config['output_dir'],
        num_train_epochs=training_config.get('num_train_epochs', 3),
        max_steps=training_config.get('max_steps', -1),
        per_device_train_batch_size=training_config.get('per_device_train_batch_size', 4),
        per_device_eval_batch_size=training_config.get('per_device_eval_batch_size', 4),
        gradient_accumulation_steps=training_config.get('gradient_accumulation_steps', 4),
        learning_rate=training_config.get('learning_rate', 2e-4),
        lr_scheduler_type=training_config.get('lr_scheduler_type', 'cosine'),
        warmup_ratio=training_config.get('warmup_ratio', 0.1),
        weight_decay=training_config.get('weight_decay', 0.01),
        max_grad_norm=training_config.get('max_grad_norm', 1.0),
        optim=training_config.get('optim', 'paged_adamw_8bit'),
        fp16=training_config.get('fp16', False),
        bf16=training_config.get('bf16', True),
        save_strategy=training_config.get('save_strategy', 'steps'),
        save_steps=training_config.get('save_steps', 200),
        save_total_limit=training_config.get('save_total_limit', 3),
        load_best_model_at_end=training_config.get('load_best_model_at_end', True),
        eval_strategy=training_config.get('eval_strategy', 'steps') if eval_dataset else 'no',
        eval_steps=training_config.get('eval_steps', 200) if eval_dataset else None,
        logging_steps=training_config.get('logging_steps', 10),
        logging_first_step=training_config.get('logging_first_step', True),
        report_to=training_config.get('report_to', 'none'),
        run_name=training_config.get('run_name', 'mits-tutor-distill'),
        gradient_checkpointing=training_config.get('gradient_checkpointing', True),
        gradient_checkpointing_kwargs=training_config.get(
            'gradient_checkpointing_kwargs',
            {"use_reentrant": False}
        ),
    )

    # Response template for completion-only training
    # Only compute loss on assistant responses
    response_template = dataset_config.get('response_template', '<|im_start|>assistant\n')

    collator = DataCollatorForCompletionOnlyLM(
        response_template=response_template,
        tokenizer=tokenizer
    )

    # Create trainer
    trainer = SFTTrainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=collator,
        args=training_args,
        max_seq_length=training_config.get('max_seq_length', 4096),
        packing=training_config.get('packing', False),
    )

    return trainer


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(description="MITS QLoRA SFT Training")

    parser.add_argument(
        '--config',
        type=str,
        default='training/configs/qlora_config.yaml',
        help='Path to training config YAML'
    )
    parser.add_argument(
        '--preset',
        type=str,
        choices=['colab_a100', 'rtx_4090', 'rtx_3090', 'rtx_2080'],
        default=None,
        help='Hardware preset to use'
    )
    parser.add_argument(
        '--train-data',
        type=str,
        default=None,
        help='Override path to training data'
    )
    parser.add_argument(
        '--eval-data',
        type=str,
        default=None,
        help='Override path to eval data'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Override output directory'
    )
    parser.add_argument(
        '--wandb-project',
        type=str,
        default=None,
        help='W&B project name (enables W&B logging)'
    )
    parser.add_argument(
        '--resume',
        type=str,
        default=None,
        help='Path to checkpoint to resume from'
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # Load config
    config = load_config(args.config, args.preset)

    # Apply CLI overrides
    if args.train_data:
        config['dataset']['train_path'] = args.train_data
    if args.eval_data:
        config['dataset']['eval_path'] = args.eval_data
    if args.output_dir:
        config['training']['output_dir'] = args.output_dir
    if args.wandb_project:
        config['training']['report_to'] = 'wandb'
        os.environ['WANDB_PROJECT'] = args.wandb_project

    logger.info("training_config", config=config)

    # Setup model and tokenizer
    model, tokenizer = setup_model_and_tokenizer(config)

    # Load dataset
    train_dataset, eval_dataset = load_training_dataset(config, tokenizer)

    # Create trainer
    trainer = create_trainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        config=config
    )

    # Train
    logger.info("starting_training")

    if args.resume:
        trainer.train(resume_from_checkpoint=args.resume)
    else:
        trainer.train()

    # Save final model
    output_dir = config['training']['output_dir']
    logger.info("saving_model", path=output_dir)

    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    # Save training config for reference
    config_save_path = Path(output_dir) / 'training_config.yaml'
    with open(config_save_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True)

    logger.info("training_complete", output=output_dir)

    print("\n" + "="*60)
    print("Training complete!")
    print(f"Model saved to: {output_dir}")
    print("="*60)

    # Print next steps
    print("\nNext steps:")
    print("1. Evaluate the model:")
    print(f"   python evaluation/evaluate.py --model {output_dir}")
    print("2. Merge LoRA adapter (optional):")
    print(f"   python training/scripts/merge_adapter.py --adapter {output_dir}")
    print("3. Convert to GGUF for Ollama (optional):")
    print(f"   python -m llama_cpp.convert --outfile model.gguf {output_dir}")


if __name__ == "__main__":
    main()
