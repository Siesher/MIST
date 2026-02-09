#!/usr/bin/env python3
"""
Merge Siesher/Adaptive_Skip_thinking_Reasoning with Cerebras-generated data.

Pipeline:
    1. Load HF dataset, classify domains, convert format
    2. Load raw_stem.jsonl (Cerebras-generated)
    3. Merge, check balance, output combined_stem.jsonl

Usage:
    python training/scripts/merge_stem_datasets.py
    python training/scripts/merge_stem_datasets.py --stats-only
    python training/scripts/merge_stem_datasets.py --no-hf  # skip HF, just use raw_stem
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import argparse
import json
import logging
import re
from collections import Counter
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  Domain classification by keywords
# ─────────────────────────────────────────────────────────────

DOMAIN_KEYWORDS = {
    "math": [
        "уравнен", "производн", "интеграл", "функци", "матриц", "предел",
        "вектор", "теорем", "формул", "многочлен", "тригонометр", "логарифм",
        "sin", "cos", "tg", "ctg", "log", "sqrt", "lim", "dx", "dy",
        "числител", "знаменател", "дробь", "корн", "степен", "факториал",
        "арифметич", "геометрич", "прогресс", "последовательн", "ряд",
        "неравенств", "система уравнен", "определител", "собственн",
        "алгебр", "геометри", "планиметри", "стереометри", "площад",
        "объём", "периметр", "окружност", "треугольник", "квадрат",
        "вероятност", "комбинатор", "перестанов", "сочетан",
    ],
    "physics": [
        "скорост", "ускорен", "сил", "масс", "энерг", "давлен",
        "температур", "ток", "напряжен", "сопротивлен", "электр",
        "магнит", "импульс", "момент", "работ", "мощност", "кинетич",
        "потенциальн", "гравитац", "тяготен", "трени", "упруг",
        "колебан", "волн", "частот", "период", "амплитуд",
        "термодинам", "теплоёмк", "теплот", "газ", "моль",
        "давлени", "Ньютон", "Кулон", "Ом", "Ампер", "Вольт",
        "индукц", "дифракц", "интерференц", "преломлен",
        "Дж", "Вт", "Н ", "м/с", "кг", "Кл",
        "механик", "оптик", "ядерн", "радиоактивн",
    ],
    "chemistry": [
        "молекул", "атом", "реакц", "раствор", "кислот", "щёлоч", "щелоч",
        "моль", "вещест", "окисл", "восстанов", "ион",
        "NaCl", "H2O", "HCl", "NaOH", "H2SO4", "CO2", "O2", "N2",
        "pH", "стехиометр", "электролиз", "электролит",
        "органическ", "неорганическ", "углеводород", "спирт",
        "альдегид", "кетон", "карбонов", "эфир", "амин",
        "полимер", "изомер", "номенклатур", "валентност",
        "энтальп", "энтропи", "Гесс", "химическ", "формула вещ",
        "периодическ", "менделеев", "элемент",
    ],
    "cs": [
        "алгоритм", "программ", "код", "python", "java", "функция",
        "массив", "список", "словарь", "стек", "очередь", "дерев",
        "граф", "хеш", "сортировк", "поиск", "рекурси",
        "сложность", "O(n", "O(log", "бинарн", "динамическ",
        "цикл", "условие", "перемен", "класс", "объект", "наследован",
        "база данных", "SQL", "API", "сервер", "клиент",
        "компилятор", "интерпретатор", "процесс", "поток",
        "операционн", "сеть", "протокол", "TCP", "HTTP",
        "def ", "for ", "while ", "if ", "import ", "print(",
    ],
    "biology": [
        "клетк", "ген", "ДНК", "РНК", "белок", "фермент",
        "организм", "эволюц", "популяц", "экосистем",
        "фотосинтез", "дыхан", "метаболизм", "гликолиз",
        "митоз", "мейоз", "хромосом", "аллель", "генотип", "фенотип",
        "мутаци", "отбор", "адаптац", "видообразован",
        "нервн", "гормон", "иммунитет", "кровообращен",
        "ткан", "орган", "систем", "анатом", "физиолог",
        "экологи", "биоценоз", "биом", "пищев", "трофическ",
        "Менделе", "Дарвин", "Харди", "Вайнберг",
        "нуклеотид", "кодон", "транскрипц", "трансляц", "реплик",
    ],
}


def classify_domain(text: str) -> str:
    """Classify text into STEM domain by keyword matching."""
    text_lower = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        scores[domain] = score

    best = max(scores, key=scores.get)
    if scores[best] >= 1:
        return best
    return "math"  # default fallback for STEM content


def classify_difficulty(text: str) -> str:
    """Estimate difficulty from text length and complexity markers."""
    length = len(text)
    text_lower = text.lower()

    hard_markers = ["докажите", "докажи", "доказательство", "олимпиад",
                    "нетривиальн", "сложн", "продвинут", "вывед"]
    easy_markers = ["прост", "базов", "основн", "школьн", "элементарн",
                    "вычисл", "найди", "реши"]

    has_hard = any(m in text_lower for m in hard_markers)
    has_easy = any(m in text_lower for m in easy_markers)

    if has_hard or length > 3000:
        return "продвинутый"
    elif has_easy or length < 500:
        return "школьный"
    else:
        return "базовый университетский"


def classify_type(text: str, domain: str) -> str:
    """Classify as calc or conceptual."""
    text_lower = text.lower()

    calc_markers = ["вычисл", "найди", "реши", "рассчитай", "определи значен",
                    "чему равн", "\\boxed", "= ?", "x =", "ответ:"]
    concept_markers = ["объясни", "почему", "опиши", "сравни", "что такое",
                       "в чём разниц", "какова роль", "как работает", "зачем"]

    calc_score = sum(1 for m in calc_markers if m in text_lower)
    concept_score = sum(1 for m in concept_markers if m in text_lower)

    if domain == "cs" and ("код" in text_lower or "python" in text_lower or "def " in text_lower):
        return "calc"

    if calc_score > concept_score:
        return "calc"
    elif concept_score > calc_score:
        return "conceptual"
    return "calc"  # default


# ─────────────────────────────────────────────────────────────
#  Format conversion
# ─────────────────────────────────────────────────────────────

def normalize_thinking_tags(text: str) -> str:
    """
    Convert various thinking formats to standard <think>...</think>.

    Handles:
      - <thought_type>...</thought_type><think><chunk_start>...<chunk_end></think>
      - <think>...</think> (already correct)
      - <|思考|>...</|思考|> (GLM format)
    """
    # Remove <thought_type> tags but keep the content
    text = re.sub(r"<thought_type>\w+</thought_type>\s*", "", text)

    # Remove chunk markers inside think blocks
    text = re.sub(r"<chunk_start>\s*", "", text)
    text = re.sub(r"\s*</?chunk_end>", "", text)
    text = re.sub(r"<continue_thinking>\s*", "", text)
    text = re.sub(r"<end_of_thought>\s*", "", text)

    # Normalize GLM format
    text = text.replace("<|思考|>", "<think>").replace("</|思考|>", "</think>")

    return text.strip()


def convert_hf_example(messages: List[Dict]) -> Optional[Dict]:
    """Convert HF messages format to our instruction/output format."""
    instruction = ""
    output = ""

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()

        if role == "user":
            instruction = content
        elif role == "assistant":
            output = normalize_thinking_tags(content)

    if not instruction or not output or len(output) < 50:
        return None

    full_text = instruction + " " + output
    domain = classify_domain(full_text)
    qtype = classify_type(full_text, domain)
    difficulty = classify_difficulty(output)

    return {
        "instruction": instruction,
        "output": output,
        "domain": domain,
        "type": qtype,
        "difficulty": difficulty,
        "source": "hf_adaptive",
    }


# ─────────────────────────────────────────────────────────────
#  Load, merge, balance
# ─────────────────────────────────────────────────────────────

def load_hf_dataset() -> List[Dict]:
    """Load and convert Siesher/Adaptive_Skip_thinking_Reasoning."""
    try:
        from datasets import load_dataset
    except ImportError:
        logger.error("datasets library required: pip install datasets")
        return []

    logger.info("Loading Siesher/Adaptive_Skip_thinking_Reasoning...")
    ds = load_dataset("Siesher/Adaptive_Skip_thinking_Reasoning", split="train")
    logger.info(f"Loaded {len(ds)} examples from HuggingFace")

    converted = []
    for ex in ds:
        result = convert_hf_example(ex["messages"])
        if result:
            converted.append(result)

    logger.info(f"Converted {len(converted)}/{len(ds)} examples")
    return converted


def load_cerebras_data(path: str) -> List[Dict]:
    """Load Cerebras-generated raw_stem.jsonl."""
    if not Path(path).exists():
        logger.warning(f"Cerebras data not found: {path}")
        return []

    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ex = json.loads(line.strip())
                ex.setdefault("source", "cerebras")
                examples.append(ex)
            except json.JSONDecodeError:
                continue

    logger.info(f"Loaded {len(examples)} examples from {path}")
    return examples


def print_stats(examples: List[Dict], title: str = "Dataset"):
    """Print dataset statistics."""
    total = len(examples)
    if total == 0:
        print(f"\n{title}: empty")
        return

    domain_counts = Counter(ex.get("domain", "?") for ex in examples)
    type_counts = Counter(ex.get("type", "?") for ex in examples)
    source_counts = Counter(ex.get("source", "?") for ex in examples)
    diff_counts = Counter(ex.get("difficulty", "?") for ex in examples)

    print(f"\n{'='*60}")
    print(f"{title}: {total} examples")
    print(f"{'='*60}")

    print(f"\nDomain distribution:")
    for d in ["math", "physics", "chemistry", "cs", "biology"]:
        c = domain_counts.get(d, 0)
        pct = 100 * c / total
        bar = "#" * int(pct)
        status = "OK" if 12 <= pct <= 25 else "WARN"
        print(f"  {d:12s}: {c:6d} ({pct:5.1f}%) {bar} [{status}]")
    other = sum(c for d, c in domain_counts.items() if d not in ["math", "physics", "chemistry", "cs", "biology"])
    if other:
        print(f"  {'other':12s}: {other:6d} ({100*other/total:5.1f}%)")

    print(f"\nType: {dict(type_counts)}")
    print(f"Source: {dict(source_counts)}")
    print(f"Difficulty: {dict(diff_counts)}")

    # Balance check
    print(f"\nBalance check:")
    ok = True
    for d in ["math", "physics", "chemistry", "cs", "biology"]:
        pct = 100 * domain_counts.get(d, 0) / total
        if pct > 25:
            print(f"  FAIL: {d} = {pct:.1f}% (> 25%)")
            ok = False
        elif pct < 12:
            print(f"  FAIL: {d} = {pct:.1f}% (< 12%)")
            ok = False
    if ok:
        print(f"  PASS: All domains within 12%-25%")


def merge_and_save(
    hf_data: List[Dict],
    cerebras_data: List[Dict],
    output_path: str,
):
    """Merge datasets and save."""
    combined = hf_data + cerebras_data
    logger.info(f"Combined: {len(hf_data)} (HF) + {len(cerebras_data)} (Cerebras) = {len(combined)} total")

    # Shuffle
    import random
    random.seed(42)
    random.shuffle(combined)

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in combined:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    logger.info(f"Saved to {output_path}")
    return combined


def main():
    parser = argparse.ArgumentParser(description="Merge STEM datasets")
    parser.add_argument("-o", "--output", default="training/data/combined_stem.jsonl")
    parser.add_argument("--raw-stem", default="training/data/raw_stem_clean.jsonl",
                        help="Cerebras-generated data (cleaned)")
    parser.add_argument("--no-hf", action="store_true",
                        help="Skip HuggingFace dataset")
    parser.add_argument("--stats-only", action="store_true",
                        help="Print stats for existing combined dataset")
    args = parser.parse_args()

    if args.stats_only:
        if Path(args.output).exists():
            examples = []
            with open(args.output, "r", encoding="utf-8") as f:
                for line in f:
                    examples.append(json.loads(line.strip()))
            print_stats(examples, "Combined STEM Dataset")
        else:
            print(f"Not found: {args.output}")
        return 0

    # Load sources
    hf_data = [] if args.no_hf else load_hf_dataset()
    cerebras_data = load_cerebras_data(args.raw_stem)

    if not hf_data and not cerebras_data:
        logger.error("No data loaded from either source")
        return 1

    # Print individual stats
    if hf_data:
        print_stats(hf_data, "HuggingFace: Adaptive_Skip_thinking_Reasoning")
    if cerebras_data:
        print_stats(cerebras_data, "Cerebras-generated STEM data")

    # Merge
    combined = merge_and_save(hf_data, cerebras_data, args.output)
    print_stats(combined, "MERGED: Combined STEM Dataset")

    return 0


if __name__ == "__main__":
    exit(main())
