#!/usr/bin/env python3
"""
Generate emotion-labeled dataset using existing rule-based detector.

Exports labeled messages from MITS sessions for RuBERT fine-tuning.
Target: 3000-5000 labeled examples across 5 emotion classes.

Usage:
    python training/scripts/generate_affect_labels.py \
        --output data/training/affect_labels.jsonl \
        --sessions-dir data/students \
        --target-count 5000

    # From synthetic dialogs
    python training/scripts/generate_affect_labels.py \
        --from-dialogs data/training/synthetic_dialogs.jsonl \
        --output data/training/affect_labels.jsonl
"""

import json
import argparse
import logging
import re
from pathlib import Path
from collections import Counter
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Simplified rule-based emotion labels (matching existing AffectiveDetector logic)
FRUSTRATION_PHRASES = [
    "не понимаю", "не могу", "опять", "надоело", "сложно", "трудно",
    "не получается", "запутался", "запуталась", "устал", "бесит",
    "невозможно", "не знаю что делать",
]

CONFUSION_PHRASES = [
    "не понимаю", "что это", "как это", "почему", "зачем",
    "объясни", "не ясно", "непонятно", "а что", "а как", "хм",
]

ENGAGEMENT_PHRASES = [
    "интересно", "а если", "а можно", "а что если",
    "понял", "поняла", "ага", "ясно", "логично", "классно",
    "получилось", "а ещё",
]

CONFIDENT_PHRASES = [
    "я знаю", "думаю что", "ответ", "получается", "правильно",
    "верно", "конечно", "очевидно", "легко",
]


def classify_text(text: str) -> str:
    """Rule-based emotion classification."""
    text_lower = text.lower().strip()

    # Check for frustration signals
    frustration_score = sum(1 for p in FRUSTRATION_PHRASES if p in text_lower)
    if "!" in text and text.count("!") >= 2:
        frustration_score += 1
    if len(text_lower) < 10 and "?" not in text_lower:
        frustration_score += 0.5

    # Check for confusion signals
    confusion_score = sum(1 for p in CONFUSION_PHRASES if p in text_lower)
    if text_lower.count("?") >= 2:
        confusion_score += 1

    # Check for engagement signals
    engagement_score = sum(1 for p in ENGAGEMENT_PHRASES if p in text_lower)

    # Check for confidence
    confident_score = sum(1 for p in CONFIDENT_PHRASES if p in text_lower)

    # Determine label by highest score
    scores = {
        "frustrated": frustration_score,
        "confused": confusion_score,
        "engaged": engagement_score,
        "confident": confident_score,
    }

    max_score = max(scores.values())
    if max_score < 1:
        return "neutral"

    return max(scores, key=scores.get)


def label_from_dialogs(dialogs_path: Path, target_count: int = 5000) -> List[dict]:
    """Generate labels from synthetic dialog JSONL.

    Supports two formats:
      - {"turns": [{"role": "student", "content": "..."}]}
      - {"conversations": [{"role": "user", "content": "..."}]}
    """
    samples = []

    with open(dialogs_path, "r", encoding="utf-8") as f:
        for line in f:
            dialog = json.loads(line)
            turns = dialog.get("turns", dialog.get("conversations", []))
            dialog_id = dialog.get("id", dialog.get("metadata", {}).get("id", ""))

            for turn in turns:
                role = turn.get("role", "")
                if role not in ("student", "user"):
                    continue
                content = turn.get("content", "").strip()
                if len(content) < 3:
                    continue

                emotion = classify_text(content)
                samples.append({
                    "text": content,
                    "label": emotion,
                    "source": "synthetic",
                    "dialog_id": dialog_id,
                })

    logger.info(f"Labeled {len(samples)} samples from dialogs")
    return samples[:target_count]


def label_from_sessions(sessions_dir: Path, target_count: int = 5000) -> List[dict]:
    """Generate labels from stored session files."""
    samples = []

    for session_file in sorted(sessions_dir.glob("*.json")):
        try:
            with open(session_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Try different session formats
            messages = data.get("messages", data.get("history", []))
            for msg in messages:
                role = msg.get("role", msg.get("speaker", ""))
                content = msg.get("content", msg.get("text", "")).strip()
                if role not in ("student", "user") or len(content) < 3:
                    continue

                emotion = classify_text(content)
                samples.append({
                    "text": content,
                    "label": emotion,
                    "source": "session",
                    "session_file": session_file.name,
                })
        except Exception as e:
            logger.debug(f"Skipping {session_file}: {e}")

    logger.info(f"Labeled {len(samples)} samples from sessions")
    return samples[:target_count]


def balance_dataset(samples: List[dict], min_per_class: int = 200) -> List[dict]:
    """Balance dataset by oversampling minority classes."""
    from collections import defaultdict
    import random

    by_label = defaultdict(list)
    for s in samples:
        by_label[s["label"]].append(s)

    # Find target count per class
    max_count = max(len(v) for v in by_label.values())
    target = min(max_count, max(min_per_class, len(samples) // len(by_label)))

    balanced = []
    for label, items in by_label.items():
        if len(items) >= target:
            balanced.extend(random.sample(items, target))
        else:
            # Oversample
            balanced.extend(items)
            extra = target - len(items)
            balanced.extend(random.choices(items, k=extra))

    random.shuffle(balanced)
    return balanced


def main():
    parser = argparse.ArgumentParser(description="Generate affect labels")
    parser.add_argument("--from-dialogs", type=str, default=None,
                        help="Path to synthetic dialogs JSONL")
    parser.add_argument("--sessions-dir", type=str, default="data/students",
                        help="Path to session files directory")
    parser.add_argument("--output", "-o", type=str,
                        default="data/training/affect_labels.jsonl")
    parser.add_argument("--target-count", type=int, default=5000)
    parser.add_argument("--balance", action="store_true", default=True)
    args = parser.parse_args()

    samples = []

    if args.from_dialogs:
        dialogs_path = Path(args.from_dialogs)
        if dialogs_path.exists():
            samples.extend(label_from_dialogs(dialogs_path, args.target_count))

    sessions_dir = Path(args.sessions_dir)
    if sessions_dir.exists():
        samples.extend(label_from_sessions(sessions_dir, args.target_count))

    if not samples:
        logger.error("No samples generated. Provide --from-dialogs or --sessions-dir")
        return 1

    # Balance
    if args.balance:
        samples = balance_dataset(samples)

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # Stats
    label_counts = Counter(s["label"] for s in samples)
    logger.info(f"\nSaved {len(samples)} labeled samples to {output_path}")
    logger.info("Label distribution:")
    for label, count in sorted(label_counts.items()):
        logger.info(f"  {label}: {count} ({100*count/len(samples):.1f}%)")

    return 0


if __name__ == "__main__":
    exit(main())
