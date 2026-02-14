"""
Curriculum Sorter for Training Data

Classifies STEM problems by difficulty level for curriculum learning:
- easy: grades 5-7 (basic operations, simple concepts)
- medium: grades 8-9 (multi-step, moderate complexity)
- hard: grades 10-11+ (olympiad, advanced topics)

Outputs per-domain difficulty files for staged training.

Usage:
    python -m training.scripts.sort_curriculum \
        --input training/data/combined_stem.jsonl \
        --output-dir training/data/curriculum/
"""

import json
import re
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Difficulty classification heuristics
DIFFICULTY_KEYWORDS = {
    "easy": {
        "math": ["сложение", "вычитание", "умножение", "деление", "дроби",
                 "пропорция", "процент", "линейное уравнение", "площадь",
                 "периметр", "объём"],
        "physics": ["скорость", "путь", "время", "плотность", "масса",
                    "сила тяжести", "давление"],
        "chemistry": ["валентность", "формула вещества", "молекулярная масса",
                      "оксиды", "кислоты", "основания"],
        "cs": ["print", "if-else", "цикл for", "переменная", "список",
               "строка", "ввод-вывод"],
        "biology": ["клетка", "ткани", "органы", "фотосинтез",
                    "царства живого", "витамины"],
    },
    "hard": {
        "math": ["интеграл", "дифференциал", "ряд", "предел",
                 "комплексные числа", "олимпиада", "теорема", "доказательство",
                 "неравенство", "тригонометрическое"],
        "physics": ["индукция", "электромагнитный", "квантовый", "релятивистский",
                    "термодинамика", "энтропия", "волновое уравнение"],
        "chemistry": ["органическая", "полимеризация", "электролиз",
                      "гибридизация", "изомеры", "энтальпия"],
        "cs": ["граф", "динамическое программирование", "рекурсия",
               "сложность O(n)", "бинарное дерево", "хеш-таблица",
               "NP-полный", "жадный алгоритм"],
        "biology": ["генетический код", "транскрипция", "трансляция",
                    "мутация", "естественный отбор", "популяционная генетика",
                    "биотехнология"],
    },
}


@dataclass
class DifficultyStats:
    """Statistics for difficulty classification."""
    total: int = 0
    easy: int = 0
    medium: int = 0
    hard: int = 0


def classify_difficulty(
    example: Dict[str, Any],
) -> str:
    """Classify a single example's difficulty.

    Uses multiple heuristics:
    1. Explicit grade/difficulty label if present
    2. Solution token count
    3. Keyword matching
    4. Step count in solution
    """
    # 1. Explicit label
    if "difficulty" in example:
        d = example["difficulty"].lower()
        if d in ("easy", "simple", "basic", "лёгкий", "простой"):
            return "easy"
        elif d in ("hard", "advanced", "olympiad", "сложный", "олимпиадный"):
            return "hard"
        elif d in ("medium", "intermediate", "средний"):
            return "medium"

    # Grade level
    if "grade" in example:
        grade = int(example["grade"]) if isinstance(example["grade"], (int, float)) else 0
        if grade <= 7:
            return "easy"
        elif grade <= 9:
            return "medium"
        else:
            return "hard"

    domain = example.get("domain", "math")
    text = (
        example.get("instruction", "")
        + " " + example.get("input", "")
        + " " + example.get("output", "")
        + " " + example.get("completion", "")
        + " " + example.get("prompt", "")
        + " " + example.get("answer", "")
    ).lower()

    # 2. Text length heuristic
    # Prefer solution length; fall back to prompt length for HF datasets
    solution = example.get("output", "") or example.get("completion", "")
    if solution.strip():
        token_count = len(solution.split())
        len_short, len_long = 100, 400
    else:
        # No full solution — use prompt length as difficulty proxy
        prompt_text = example.get("prompt", "") or example.get("instruction", "")
        token_count = len(prompt_text.split())
        len_short, len_long = 40, 120

    # 3. Keyword matching
    easy_keywords = DIFFICULTY_KEYWORDS["easy"].get(domain, [])
    hard_keywords = DIFFICULTY_KEYWORDS["hard"].get(domain, [])

    easy_hits = sum(1 for kw in easy_keywords if kw in text)
    hard_hits = sum(1 for kw in hard_keywords if kw in text)

    # 4. Step count / structural complexity
    step_patterns = [
        r'шаг\s*\d', r'step\s*\d', r'\d\)', r'\d\.',
        r'во-первых|во-вторых|далее',
        r'найдите|определите|вычислите|докажите|покажите',
        r'\\frac|\\int|\\sum|\\lim|\\sqrt',
    ]
    step_count = sum(len(re.findall(p, text)) for p in step_patterns)

    # Scoring
    score = 0  # -3..+3 range maps to easy/medium/hard

    # Token count signal
    if token_count < len_short:
        score -= 1
    elif token_count > len_long:
        score += 1

    # Keywords
    if easy_hits > hard_hits:
        score -= 1
    elif hard_hits > easy_hits:
        score += 1

    # Structural complexity
    if step_count >= 4:
        score += 1
    elif step_count <= 1:
        score -= 1

    if score <= -1:
        return "easy"
    elif score >= 1:
        return "hard"
    return "medium"


def sort_dataset(
    input_path: str,
    output_dir: str,
    per_domain: bool = True,
) -> Dict[str, Any]:
    """Sort a JSONL dataset into difficulty-stratified files.

    Args:
        input_path: Path to input JSONL
        output_dir: Directory for output files
        per_domain: If True, output {domain}_{difficulty}.jsonl files
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Collect examples by (domain, difficulty)
    buckets: Dict[str, Dict[str, List[Dict]]] = defaultdict(
        lambda: defaultdict(list)
    )
    stats: Dict[str, DifficultyStats] = defaultdict(DifficultyStats)
    global_stats = DifficultyStats()

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            example = json.loads(line)
            domain = example.get("domain", "math")
            difficulty = classify_difficulty(example)

            example["difficulty"] = difficulty
            buckets[domain][difficulty].append(example)

            # Stats
            stats[domain].total += 1
            global_stats.total += 1
            setattr(stats[domain], difficulty, getattr(stats[domain], difficulty) + 1)
            setattr(global_stats, difficulty, getattr(global_stats, difficulty) + 1)

    # Write output files
    files_written = []

    if per_domain:
        for domain, difficulties in buckets.items():
            for difficulty, examples in difficulties.items():
                filename = f"{domain}_{difficulty}.jsonl"
                filepath = output / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    for ex in examples:
                        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                files_written.append(str(filepath))
    else:
        for difficulty in ("easy", "medium", "hard"):
            filepath = output / f"{difficulty}.jsonl"
            with open(filepath, "w", encoding="utf-8") as f:
                for domain, difficulties in buckets.items():
                    for ex in difficulties.get(difficulty, []):
                        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            files_written.append(str(filepath))

    result = {
        "total": global_stats.total,
        "easy": global_stats.easy,
        "medium": global_stats.medium,
        "hard": global_stats.hard,
        "distribution": {
            "easy_pct": global_stats.easy / global_stats.total * 100 if global_stats.total else 0,
            "medium_pct": global_stats.medium / global_stats.total * 100 if global_stats.total else 0,
            "hard_pct": global_stats.hard / global_stats.total * 100 if global_stats.total else 0,
        },
        "per_domain": {
            domain: {
                "total": s.total, "easy": s.easy, "medium": s.medium, "hard": s.hard,
            }
            for domain, s in stats.items()
        },
        "files_written": files_written,
    }

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curriculum difficulty sorter")
    parser.add_argument("--input", required=True, help="Input JSONL dataset")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--flat", action="store_true",
                        help="Output 3 files (easy/medium/hard) instead of per-domain")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = sort_dataset(args.input, args.output_dir, per_domain=not args.flat)
    print(json.dumps(result, indent=2, ensure_ascii=False))
