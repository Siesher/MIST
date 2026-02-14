"""
Генерация русскоязычного STEM датасета для REAP pruning.
Объединяет с английским и загружает на HuggingFace.
"""

import json
import random
import time
import os
from pathlib import Path
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras
from huggingface_hub import HfApi, login
from datasets import load_dataset, Dataset, concatenate_datasets

# Load environment
load_dotenv()

# Collect all API keys
API_KEYS = []
for i in range(1, 20):
    key = os.getenv(f"CEREBRAS_API_KEY_{i}")
    if key:
        API_KEYS.append(key)

print(f"[OK] Loaded {len(API_KEYS)} API keys")

# Russian STEM topics
TOPICS = {
    "math": [
        "линейные уравнения", "квадратные уравнения", "системы уравнений",
        "производные", "интегралы", "пределы", "тригонометрия",
        "логарифмы", "арифметические прогрессии", "геометрические прогрессии",
        "комбинаторика", "теория вероятностей", "статистика",
        "векторы", "матрицы", "комплексные числа"
    ],
    "physics": [
        "кинематика", "динамика", "законы Ньютона", "энергия и работа",
        "импульс", "вращательное движение", "гравитация",
        "термодинамика", "теплопередача", "газовые законы",
        "электростатика", "электрические цепи", "магнетизм",
        "волны", "оптика", "квантовая физика"
    ],
    "chemistry": [
        "строение атома", "химические связи", "окислительно-восстановительные реакции",
        "кислоты и основания", "растворы и концентрации", "электролиз",
        "органические соединения", "полимеры", "биохимия",
        "термохимия", "химическое равновесие", "скорость реакции"
    ],
    "biology": [
        "строение клетки", "митоз и мейоз", "ДНК и РНК",
        "генетика Менделя", "эволюция", "естественный отбор",
        "экосистемы", "пищевые цепи", "круговорот веществ",
        "фотосинтез", "дыхание клетки", "нервная система"
    ],
    "code": [
        "сортировка массива", "бинарный поиск", "рекурсия",
        "связные списки", "стеки и очереди", "деревья",
        "графы", "динамическое программирование", "жадные алгоритмы",
        "работа со строками", "хеш-таблицы", "обработка файлов"
    ],
}

DIFFICULTIES = ["basic", "intermediate", "advanced"]

SYSTEM_PROMPT = """Создай учебную STEM задачу на русском языке.
Домен: {domain} | Тема: {subtopic} | Сложность: {difficulty}

ВАЖНО: Верни ответ СТРОГО в одну строку, JSON формат, без переносов строк внутри значений.
Используй \\n для переносов в тексте.
НЕ используй LaTeX ($$, \\frac и т.д.) - пиши формулы текстом.

Формат: {{"instruction":"задача","output":"решение"}}"""


def generate_example(client, domain: str, subtopic: str, difficulty: str, max_retries: int = 3) -> dict | None:
    """Generate a single Russian STEM example with retry logic."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="qwen-3-235b-a22b-instruct-2507",
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT.format(
                            domain=domain,
                            subtopic=subtopic,
                            difficulty=difficulty
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Создай задачу по теме '{subtopic}' уровня {difficulty}"
                    }
                ],
                temperature=0.8,
                max_tokens=2000,
            )

            content = response.choices[0].message.content
            if content is None:
                time.sleep(2)
                continue
            content = content.strip()

            # Clean up markdown if present
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        content = part
                        break

            # Try to extract JSON from text
            if not content.startswith("{"):
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end > start:
                    content = content[start:end]

            # Try to parse JSON, handling multiline responses
            try:
                # Replace actual newlines with \n for JSON
                content_oneline = content.replace('\r\n', '\\n').replace('\n', '\\n')
                data = json.loads(content_oneline)
            except json.JSONDecodeError:
                try:
                    # Try original content
                    data = json.loads(content)
                except:
                    print(f"  DEBUG: {content[:150]}...")
                    raise
            data["domain"] = domain
            data["subtopic"] = subtopic
            data["difficulty"] = difficulty
            data["input"] = ""
            data["language"] = "ru"

            return data

        except json.JSONDecodeError:
            print(f"  JSON error, retrying...")
            time.sleep(1)
            continue
        except Exception as e:
            if "429" in str(e) or "too_many_requests" in str(e):
                wait = 5 * (attempt + 1)
                print(f"  Rate limit, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  Error: {e}")
            return None

    return None


def generate_russian_dataset(target_count: int = 500) -> list[dict]:
    """Generate Russian STEM examples."""
    examples = []
    key_index = 0
    checkpoint_file = Path("training/calibration_data/russian_checkpoint.jsonl")
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

    # Load checkpoint if exists
    if checkpoint_file.exists():
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            examples = [json.loads(line) for line in f if line.strip()]
        print(f"[OK] Loaded {len(examples)} from checkpoint")

    # Calculate examples per domain
    domains = list(TOPICS.keys())
    per_domain = target_count // len(domains)

    for domain in domains:
        # Count existing for this domain
        existing = sum(1 for ex in examples if ex.get("domain") == domain)
        domain_count = existing
        subtopics = TOPICS[domain]

        if domain_count >= per_domain:
            print(f"\n[{domain.upper()}] Already have {domain_count}/{per_domain}, skipping")
            continue

        print(f"\n[{domain.upper()}] Generating {per_domain - domain_count} more examples...")

        while domain_count < per_domain:
            # Rotate API keys
            client = Cerebras(api_key=API_KEYS[key_index % len(API_KEYS)])
            key_index += 1

            subtopic = random.choice(subtopics)
            difficulty = random.choice(DIFFICULTIES)

            example = generate_example(client, domain, subtopic, difficulty)

            if example:
                examples.append(example)
                domain_count += 1
                print(f"  [{domain_count}/{per_domain}] {subtopic} ({difficulty})")

                # Save checkpoint every 10 examples
                if len(examples) % 10 == 0:
                    with open(checkpoint_file, "w", encoding="utf-8") as f:
                        for ex in examples:
                            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                    print(f"  [checkpoint saved: {len(examples)} total]")

            # Delay: 10 req/min limit per key, with 10 keys
            time.sleep(0.7)

    return examples


def merge_and_upload(russian_examples: list[dict], hf_token: str):
    """Merge with English dataset and upload to HuggingFace."""

    # Load existing English dataset
    print("\nLoading English dataset from HuggingFace...")
    english_ds = load_dataset("Siesher/mits-calibration-dataset", split="train")
    print(f"English examples: {len(english_ds)}")

    # Add language tag to English examples
    english_data = []
    for ex in english_ds:
        ex_dict = dict(ex)
        ex_dict["language"] = "en"
        english_data.append(ex_dict)

    # Combine
    all_examples = english_data + russian_examples
    random.shuffle(all_examples)

    print(f"Russian examples: {len(russian_examples)}")
    print(f"Total combined: {len(all_examples)}")

    # Create combined dataset
    combined_ds = Dataset.from_list(all_examples)

    # Save locally
    output_path = Path("training/calibration_data/stem_calibration_bilingual.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Saved locally to: {output_path}")

    # Upload to HuggingFace
    print("\nUploading to HuggingFace...")
    login(token=hf_token)

    api = HfApi()
    api.upload_file(
        path_or_fileobj=str(output_path),
        path_in_repo="stem_calibration.jsonl",
        repo_id="Siesher/mits-calibration-dataset",
        repo_type="dataset",
    )

    print("[OK] Uploaded to Siesher/mits-calibration-dataset")

    # Print statistics
    print("\n" + "="*50)
    print("DATASET STATISTICS")
    print("="*50)

    from collections import Counter
    domains = Counter(ex["domain"] for ex in all_examples)
    languages = Counter(ex.get("language", "en") for ex in all_examples)

    print("\nBy domain:")
    for domain, count in sorted(domains.items()):
        print(f"  {domain}: {count} ({count/len(all_examples)*100:.1f}%)")

    print("\nBy language:")
    for lang, count in sorted(languages.items()):
        print(f"  {lang}: {count} ({count/len(all_examples)*100:.1f}%)")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500, help="Number of Russian examples")
    parser.add_argument("--hf-token", type=str, required=True, help="HuggingFace token")
    args = parser.parse_args()

    print("="*50)
    print("RUSSIAN STEM DATASET GENERATOR")
    print("="*50)

    # Generate Russian examples
    russian_examples = generate_russian_dataset(args.count)

    # Save intermediate result
    with open("training/calibration_data/russian_stem.jsonl", "w", encoding="utf-8") as f:
        for ex in russian_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"\nSaved {len(russian_examples)} Russian examples")

    # Merge and upload
    merge_and_upload(russian_examples, args.hf_token)

    print("\n[OK] Done!")


if __name__ == "__main__":
    main()
