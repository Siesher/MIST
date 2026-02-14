#!/usr/bin/env python3
"""
Convert synthetic dialogs to ChatML format for Unsloth training.

ChatML format (GLM-4 native):
    <|im_start|>system
    {system_prompt}<|im_end|>
    <|im_start|>user
    {message}<|im_end|>
    <|im_start|>assistant
    {response}<|im_end|>

Usage:
    python training/scripts/prepare_chatml.py \
        --input data/training/synthetic_dialogs.jsonl \
        --output data/training/chatml_ready.jsonl \
        --test-split 0.1
"""

import json
import random
import argparse
from pathlib import Path
from typing import List, Dict


SYSTEM_PROMPT = """Ты — сократический репетитор по математике. Помогай студентам находить решения через наводящие вопросы.

ПРИНЦИПЫ:
1. НИКОГДА не давай готовых ответов сразу
2. Задавай ОДИН чёткий вопрос за раз
3. Используй $LaTeX$ для математики
4. Отвечай на русском языке

Ответ в формате JSON:
{"move": "тип_хода", "message": "ответ", "reasoning": "обоснование"}"""


def dialog_to_chatml(dialog: dict) -> List[dict]:
    """
    Convert a dialog to ChatML training samples.

    Each dialog produces one multi-turn conversation.
    """
    task = dialog.get("task", {})
    turns = dialog.get("turns", [])

    if not turns:
        return []

    # Build task context for system prompt
    task_context = f"""ЗАДАЧА:
Условие: {task.get('problem', '')}
Тема: {task.get('topic', '')}
Сложность: {task.get('difficulty', '')}

СПРАВКА (скрыто от студента):
Решение: {task.get('solution', '')}
Ответ: {task.get('answer', '')}"""

    system_content = f"{SYSTEM_PROMPT}\n\n{task_context}"

    # Build messages array
    messages = [{"role": "system", "content": system_content}]

    for turn in turns:
        role = turn.get("role", "")
        content = turn.get("content", "")

        if role == "student":
            messages.append({"role": "user", "content": content})
        elif role == "tutor":
            # Format tutor response as JSON (training target)
            response = {
                "move": turn.get("move", "scaffolding"),
                "message": content,
                "reasoning": turn.get("reasoning", "")
            }
            messages.append({
                "role": "assistant",
                "content": json.dumps(response, ensure_ascii=False)
            })

    return [{
        "messages": messages,
        "id": dialog.get("id", ""),
        "topic": task.get("topic", ""),
        "difficulty": task.get("difficulty", ""),
        "student_persona": dialog.get("student_persona", ""),
    }]


def format_chatml_text(messages: List[dict]) -> str:
    """Format messages as raw ChatML text for SFTTrainer."""
    parts = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    return "\n".join(parts)


def process_dataset(
    input_path: Path,
    output_path: Path,
    test_split: float = 0.1,
    seed: int = 42,
    include_text: bool = True,
):
    """Process full dataset and split into train/test."""
    random.seed(seed)

    # Load dialogs
    dialogs = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            dialogs.append(json.loads(line))

    print(f"Loaded {len(dialogs)} dialogs")

    # Convert to ChatML
    samples = []
    skipped = 0
    for dialog in dialogs:
        converted = dialog_to_chatml(dialog)
        if converted:
            sample = converted[0]
            if include_text:
                sample["text"] = format_chatml_text(sample["messages"])
            samples.append(sample)
        else:
            skipped += 1

    print(f"Converted: {len(samples)}, Skipped: {skipped}")

    # Shuffle and split
    random.shuffle(samples)
    split_idx = int(len(samples) * (1 - test_split))
    train_samples = samples[:split_idx]
    test_samples = samples[split_idx:]

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)

    train_path = output_path.with_suffix("").with_name(output_path.stem + "_train.jsonl")
    test_path = output_path.with_suffix("").with_name(output_path.stem + "_test.jsonl")

    for path, data in [(train_path, train_samples), (test_path, test_samples)]:
        with open(path, "w", encoding="utf-8") as f:
            for sample in data:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        print(f"Saved {len(data)} samples to {path}")

    # Also save full dataset
    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
    print(f"Full dataset: {output_path}")

    # Stats
    avg_turns = sum(len(s["messages"]) for s in samples) / len(samples) if samples else 0
    avg_text_len = sum(len(s.get("text", "")) for s in samples) / len(samples) if samples else 0
    print(f"\nStats:")
    print(f"  Avg messages/sample: {avg_turns:.1f}")
    print(f"  Avg text length: {avg_text_len:.0f} chars")
    print(f"  Train: {len(train_samples)}, Test: {len(test_samples)}")


def main():
    parser = argparse.ArgumentParser(description="Convert dialogs to ChatML format")
    parser.add_argument("--input", "-i", type=str, required=True,
                        help="Input JSONL with synthetic dialogs")
    parser.add_argument("--output", "-o", type=str,
                        default="data/training/chatml_ready.jsonl",
                        help="Output JSONL path")
    parser.add_argument("--test-split", type=float, default=0.1,
                        help="Test split ratio (default: 0.1)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    process_dataset(
        input_path=Path(args.input),
        output_path=Path(args.output),
        test_split=args.test_split,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
