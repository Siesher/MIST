"""
PDF → KnowledgeCard Ingestion Pipeline.

Extracts structured knowledge cards from PDF textbooks using:
1. pdfplumber for text extraction
2. Section-aware chunking (splits by headings, not arbitrary char count)
3. Pre-filtering (skips TOC, bibliography, empty pages)
4. Parallel LLM extraction with ThreadPoolExecutor
5. Chunk-level caching (skip already-processed chunks on re-run)

Usage:
    python scripts/ingest_pdf.py path/to/textbook.pdf --source "Алгебра 8 класс" --domain math
    python scripts/ingest_pdf.py path/to/textbook.pdf --source "Физика 10 класс" --domain physics --pages 10-50
    python scripts/ingest_pdf.py path/to/textbook.pdf --source "Алгебра" --domain math --workers 4

Output:
    data/knowledge/textbooks/<source_name>.json
"""

import argparse
import hashlib
import json
import re
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── LLM Extraction Prompt ────────────────────────────────────────

EXTRACTION_PROMPT = """Ты — ассистент для создания образовательных карточек знаний.
Из данного фрагмента учебника извлеки структурированные карточки знаний.

ВАЖНО: Текст извлечён из PDF и может содержать искажённые формулы (перепутанные
индексы, разбитые символы). Сосредоточься на определениях, теоремах и ключевых
концепциях, которые можно разобрать. Восстанови формулы по смыслу, если это возможно.
Если фрагмент слишком повреждён — верни [].

Каждая карточка описывает ОДНУ тему/концепцию и содержит:
- topic: короткое имя темы (snake_case, например "quadratic_equations")
- domain: предметная область ("{domain}")
- skill: ключ навыка (например "algebra.quadratic")
- difficulty: "easy", "medium" или "hard"
- prerequisites: список тем-пререквизитов
- definition: определение концепции (с LaTeX если возможно)
- key_formulas: список {{name, latex}}
- worked_examples: список {{difficulty, problem, steps[], answer}} (если есть примеры)
- common_errors: список {{error, description, correction}} (если упоминаются)
- solution_methods: список {{method_id, name, applicability, steps: [{{step, action, formula}}], when_to_use, common_pitfalls}} (если текст описывает АЛГОРИТМ или МЕТОД решения задач)
- problem_templates: список {{template_id, pattern, parameters: {{name: {{type, range, exclude}}}}, constraints, answer_template, solution_method_id, difficulty}} (если текст содержит параметризуемые примеры задач)
- tags: список тегов

Ответь JSON-массивом карточек. Если фрагмент не содержит полезной информации, верни [].

## ФРАГМЕНТ УЧЕБНИКА:
{chunk}

## ИСТОЧНИК:
{source}

Ответь ТОЛЬКО валидным JSON массивом:"""


# ── PDF Text Cleanup ─────────────────────────────────────────────

def _clean_pdf_text(text: str) -> str:
    """
    Clean up garbled PDF-extracted text:
    - Remove broken formula lines (mostly symbols/digits with no words)
    - Collapse excessive whitespace
    - Remove page headers/footers
    """
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        # Skip lines that are mostly math symbols with no readable words
        # (e.g., "⎡ ⎤ ⎡ ⎤ ⎡ ⎤" or "X (t)=AX(t)+GN (t)")
        alpha_chars = sum(1 for c in stripped if c.isalpha())
        total_chars = len(stripped)
        # Keep lines with enough alphabetic content (>30% or short lines with any text)
        if total_chars > 10 and alpha_chars / total_chars < 0.2:
            continue
        # Remove page headers like "34 Статистическая динамика и идентификация САУ"
        if re.match(r"^\d+\s+(Статистическая|Глава|Chapter)\s", stripped):
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


# ── Pre-filter patterns (skip non-content pages) ─────────────────

# Pages matching these are likely not educational content
SKIP_PATTERNS = [
    r"^содержание\s*$",          # Table of contents header
    r"^оглавление\s*$",
    r"^table\s+of\s+contents",
    r"^(список\s+)?литератур",   # Bibliography
    r"^библиограф",
    r"^предметный\s+указатель",  # Index
    r"^(ответы|ответы\s+к\s+)", # Answer keys
    r"^\d+\s*$",                 # Page numbers only
]
_skip_re = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in SKIP_PATTERNS]


def _is_skippable_page(text: str) -> bool:
    """Check if page is TOC, bibliography, index, or other non-content."""
    first_lines = "\n".join(text.strip().split("\n")[:3])
    for pattern in _skip_re:
        if pattern.search(first_lines):
            return True
    # Very short pages with mostly numbers (likely page of answers/index)
    if len(text.strip()) < 100:
        digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
        if digit_ratio > 0.4:
            return True
    return False


# ── Section-aware heading detection ──────────────────────────────

# Common textbook heading patterns (Russian + English)
HEADING_PATTERNS = [
    r"^§\s*\d+",                          # § 1. Квадратные уравнения
    r"^Глава\s+\d+",                      # Глава 3. Производная
    r"^Раздел\s+\d+",                     # Раздел 2
    r"^Chapter\s+\d+",
    r"^\d+\.\d+\.?\s+[А-ЯA-Z]",          # 2.3. Дискриминант
    r"^#{1,3}\s+",                        # Markdown-style headings
    r"^[А-ЯA-Z][А-Яа-яA-Za-z\s]{5,60}$",  # ALL-CAPS or Title-like line
]
_heading_re = [re.compile(p, re.MULTILINE) for p in HEADING_PATTERNS]


def _is_heading(line: str) -> bool:
    """Check if a line looks like a section heading."""
    line = line.strip()
    if not line or len(line) > 80:
        return False
    for pattern in _heading_re:
        if pattern.match(line):
            return True
    return False


# ── PDF Text Extraction ──────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str, page_range: Optional[str] = None) -> List[str]:
    """
    Extract text from PDF page by page, filtering out non-content pages.

    Args:
        pdf_path: Path to PDF file
        page_range: Optional "start-end" page range (1-indexed)

    Returns:
        List of page texts (pre-filtered)
    """
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        sys.exit(1)

    pages = []
    skipped = 0
    start_page, end_page = 0, None

    if page_range:
        parts = page_range.split("-")
        start_page = int(parts[0]) - 1
        if len(parts) > 1:
            end_page = int(parts[1])

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        logger.info(f"PDF has {total} pages")

        for i, page in enumerate(pdf.pages):
            if i < start_page:
                continue
            if end_page and i >= end_page:
                break

            text = page.extract_text()
            if not text or len(text.strip()) < 50:
                skipped += 1
                continue

            if _is_skippable_page(text):
                skipped += 1
                continue

            pages.append(text.strip())

    logger.info(f"Extracted {len(pages)} content pages, skipped {skipped}")
    return pages


# ── Section-Aware Chunking ───────────────────────────────────────

def chunk_text(
    pages: List[str],
    chunk_size: int = 2000,
    section_aware: bool = True,
) -> List[str]:
    """
    Split pages into chunks, preferring section boundaries.

    When section_aware=True, tries to split at heading lines rather than
    at arbitrary character counts. Falls back to size-based splitting
    if no headings are found.

    Args:
        pages: List of page texts
        chunk_size: Max characters per chunk
        section_aware: Use heading detection for smarter splits

    Returns:
        List of text chunks
    """
    full_text = "\n\n".join(pages)

    if not section_aware:
        return _chunk_by_size(pages, chunk_size)

    # Try section-aware splitting
    lines = full_text.split("\n")
    chunks = []
    current_chunk_lines: List[str] = []
    current_len = 0

    for line in lines:
        is_new_section = _is_heading(line) and current_len > 300

        if is_new_section or (current_len + len(line) > chunk_size and current_len > 300):
            if current_chunk_lines:
                chunks.append("\n".join(current_chunk_lines).strip())
            current_chunk_lines = [line]
            current_len = len(line)
        else:
            current_chunk_lines.append(line)
            current_len += len(line) + 1

    if current_chunk_lines:
        chunks.append("\n".join(current_chunk_lines).strip())

    # Filter out tiny chunks (merge into previous)
    merged = []
    for chunk in chunks:
        if len(chunk) < 100 and merged:
            merged[-1] += "\n\n" + chunk
        else:
            merged.append(chunk)

    logger.info(
        f"Created {len(merged)} chunks "
        f"(avg {sum(len(c) for c in merged) // max(len(merged), 1)} chars, "
        f"section-aware={section_aware})"
    )
    return merged


def _chunk_by_size(pages: List[str], chunk_size: int) -> List[str]:
    """Simple size-based chunking (fallback)."""
    chunks = []
    current_chunk = ""

    for page in pages:
        if len(current_chunk) + len(page) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = page
        else:
            current_chunk += "\n\n" + page

    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    return chunks


# ── Chunk Caching ────────────────────────────────────────────────

def _chunk_hash(chunk: str) -> str:
    """Deterministic hash for a chunk."""
    return hashlib.md5(chunk.encode("utf-8")).hexdigest()[:12]


def _load_cache(cache_path: Path) -> Dict[str, List[Dict]]:
    """Load chunk hash → cards cache."""
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache_path: Path, cache: Dict[str, List[Dict]]) -> None:
    """Persist cache to disk."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


# ── LLM Card Extraction ─────────────────────────────────────────

def extract_cards_from_chunk(
    llm_client,
    chunk: str,
    source: str,
    domain: str,
) -> List[Dict[str, Any]]:
    """
    Use LLM to extract knowledge cards from a text chunk.

    Args:
        llm_client: LLMClient instance
        chunk: Text chunk from PDF
        source: Source reference name
        domain: Subject domain

    Returns:
        List of card dictionaries
    """
    cleaned_chunk = _clean_pdf_text(chunk)
    if len(cleaned_chunk.strip()) < 50:
        logger.debug("Chunk too short after cleanup, skipping")
        return []

    prompt = EXTRACTION_PROMPT.format(
        chunk=cleaned_chunk[:3000],
        source=source,
        domain=domain,
    )

    try:
        response = llm_client.generate(
            prompt=prompt,
            system="Ты извлекаешь структурированные данные из текста учебника. Отвечай ТОЛЬКО JSON.",
            json_mode=True,
            thinking=False,
            temperature=0.1,
        )

        data = json.loads(response)
        if isinstance(data, list):
            cards = data
        elif isinstance(data, dict):
            cards = data.get("cards", [data])
        else:
            return []

        for card in cards:
            if "source_reference" not in card:
                card["source_reference"] = {"type": "textbook", "title": source}
            if "id" not in card:
                card["id"] = f"{domain}_{card.get('topic', 'unknown')}_{_chunk_hash(chunk)}"

        return cards

    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}")
        return []
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return []


# ── Deduplication ────────────────────────────────────────────────

def _normalize_topic(topic: str) -> str:
    """Normalize topic name for grouping."""
    return topic.lower().strip().replace("-", "_").replace(" ", "_")


def _topics_match(a: str, b: str) -> bool:
    """Check if two topic strings refer to the same concept (fuzzy)."""
    na, nb = _normalize_topic(a), _normalize_topic(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return False


def _merge_lists_by_key(
    existing: List[Dict], new: List[Dict], key: str
) -> List[Dict]:
    """Merge two lists of dicts, deduplicating by a key field."""
    seen = {item.get(key, "").lower().strip() for item in existing if item.get(key)}
    merged = list(existing)
    for item in new:
        val = item.get(key, "").lower().strip()
        if val and val not in seen:
            seen.add(val)
            merged.append(item)
    return merged


def deduplicate_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate and merge cards with overlapping topics.

    Groups by normalized topic (fuzzy), then merges fields:
    longest definition wins, lists are unioned by key fields.
    """
    if not cards:
        return []

    groups: List[List[Dict[str, Any]]] = []
    assigned = [False] * len(cards)

    for i, card in enumerate(cards):
        if assigned[i]:
            continue
        group = [card]
        assigned[i] = True
        topic_i = card.get("topic", "")

        for j in range(i + 1, len(cards)):
            if assigned[j]:
                continue
            if _topics_match(topic_i, cards[j].get("topic", "")):
                group.append(cards[j])
                assigned[j] = True

        groups.append(group)

    merged_cards = []
    for group in groups:
        base = dict(group[0])

        for card in group[1:]:
            if len(card.get("definition", "")) > len(base.get("definition", "")):
                base["definition"] = card["definition"]

            base["key_formulas"] = _merge_lists_by_key(
                base.get("key_formulas", []), card.get("key_formulas", []), "name",
            )
            base["worked_examples"] = _merge_lists_by_key(
                base.get("worked_examples", []), card.get("worked_examples", []), "problem",
            )
            base["common_errors"] = _merge_lists_by_key(
                base.get("common_errors", []), card.get("common_errors", []), "error",
            )

            existing_prereqs = set(base.get("prerequisites", []))
            for p in card.get("prerequisites", []):
                if p not in existing_prereqs:
                    base.setdefault("prerequisites", []).append(p)
                    existing_prereqs.add(p)

            existing_tags = {t.lower() for t in base.get("tags", [])}
            for t in card.get("tags", []):
                if t.lower() not in existing_tags:
                    base.setdefault("tags", []).append(t)
                    existing_tags.add(t.lower())

        merged_cards.append(base)

    logger.info(f"Deduplicated {len(cards)} cards -> {len(merged_cards)} unique")
    return merged_cards


# ── Main Pipeline ────────────────────────────────────────────────

def ingest_pdf(
    pdf_path: str,
    source_name: str,
    domain: str = "math",
    output_dir: str = "data/knowledge/textbooks",
    page_range: Optional[str] = None,
    chunk_size: int = 2000,
    max_workers: int = 1,
    model: Optional[str] = None,
) -> Path:
    """
    Full PDF → KnowledgeCards pipeline with caching and parallelism.

    Args:
        pdf_path: Path to PDF textbook
        source_name: Human-readable source name
        domain: Subject domain
        output_dir: Output directory for JSON files
        page_range: Optional page range "start-end"
        chunk_size: Characters per chunk
        max_workers: Parallel LLM extraction threads (1 = sequential)

    Returns:
        Path to output JSON file
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    safe_name = source_name.lower().replace(" ", "_").replace(".", "")
    cache_path = out_path / f".cache_{safe_name}.json"
    output_file = out_path / f"{safe_name}.json"

    # Step 1: Extract + filter text
    logger.info(f"Extracting text from: {pdf_path}")
    pages = extract_text_from_pdf(pdf_path, page_range)
    if not pages:
        logger.error("No text extracted from PDF")
        sys.exit(1)

    # Step 2: Section-aware chunking
    chunks = chunk_text(pages, chunk_size, section_aware=True)

    # Step 3: Load cache
    cache = _load_cache(cache_path)
    cache_hits = 0

    # Step 4: Extract cards (parallel with caching)
    logger.info(f"Extracting cards via LLM ({max_workers} workers)...")

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.models.llm_client import LLMClient
    llm = LLMClient(model=model) if model else LLMClient()

    all_cards: List[Dict[str, Any]] = []

    def process_chunk(idx_chunk):
        idx, chunk = idx_chunk
        h = _chunk_hash(chunk)
        if h in cache:
            return idx, cache[h], True
        cards = extract_cards_from_chunk(llm, chunk, source_name, domain)
        return idx, cards, False

    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_chunk, (i, c)): i
                for i, c in enumerate(chunks)
            }
            for future in as_completed(futures):
                idx, cards, was_cached = future.result()
                if was_cached:
                    cache_hits += 1
                else:
                    cache[_chunk_hash(chunks[idx])] = cards
                all_cards.extend(cards)
                logger.info(
                    f"  Chunk {idx + 1}/{len(chunks)}: "
                    f"{len(cards)} cards {'(cached)' if was_cached else ''}"
                )
    else:
        for i, chunk in enumerate(chunks):
            _, cards, was_cached = process_chunk((i, chunk))
            if was_cached:
                cache_hits += 1
            else:
                cache[_chunk_hash(chunk)] = cards
            all_cards.extend(cards)
            logger.info(
                f"  Chunk {i + 1}/{len(chunks)}: "
                f"{len(cards)} cards {'(cached)' if was_cached else ''}"
            )

    # Save cache for next run
    _save_cache(cache_path, cache)
    if cache_hits:
        logger.info(f"Cache: {cache_hits}/{len(chunks)} chunks reused")

    if not all_cards:
        logger.warning("No cards extracted from PDF")
        return out_path

    # Step 5: Deduplicate
    all_cards = deduplicate_cards(all_cards)

    # Step 6: Save
    output_data = {"cards": all_cards}
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(all_cards)} cards to {output_file}")
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF textbook into KnowledgeCards")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--source", required=True, help="Source name (e.g., 'Алгебра 8 класс')")
    parser.add_argument("--domain", default="math",
                        choices=["math", "physics", "cs", "chemistry", "biology"])
    parser.add_argument("--output", default="data/knowledge/textbooks", help="Output directory")
    parser.add_argument("--pages", default=None, help="Page range (e.g., '10-50')")
    parser.add_argument("--chunk-size", type=int, default=2000, help="Characters per chunk")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel LLM workers (default 1, try 2-4 for faster extraction)")
    parser.add_argument("--model", default=None,
                        help="Ollama model name (e.g., 'qwen3.5:9b'). Uses default from config if not set.")

    args = parser.parse_args()

    if not Path(args.pdf_path).exists():
        logger.error(f"File not found: {args.pdf_path}")
        sys.exit(1)

    ingest_pdf(
        pdf_path=args.pdf_path,
        source_name=args.source,
        domain=args.domain,
        output_dir=args.output,
        page_range=args.pages,
        chunk_size=args.chunk_size,
        max_workers=args.workers,
        model=args.model,
    )


if __name__ == "__main__":
    main()
