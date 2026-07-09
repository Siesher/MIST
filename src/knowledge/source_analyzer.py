"""Unified source analyzer — быстрый и точный анализ любых текстовых источников.

Единый движок, который используют оба пути работы с источниками:
  * brief  — сжатый дайджест (ключевые понятия/формулы) для подмешивания в
             контекст чата (путь A: вложение к сообщению);
  * graph  — полное извлечение сущностей по ВСЕМУ документу для Knowledge Forge
             (путь B), без обрезки первых 3000 символов.

Ключевые свойства:
  * Чанкинг с перекрытием — документ режется на куски, обрабатывается целиком.
  * Параллельная обработка чанков (ThreadPoolExecutor) — «быстро» при «полно».
  * Кэш по хэшу контента — повторный анализ того же текста не зовёт LLM.
  * Живой бэкенд: OpenAICompatLLMClient (llama-swap) → fallback LLMClient (Ollama).
  * Устойчивый разбор JSON (срезает markdown-ограждения и мусор вокруг объекта).
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Параметры чанкинга (символы). 6000 ≈ 1500 токенов на чанк — комфортно для 9B.
DEFAULT_CHUNK_CHARS = 6000
DEFAULT_OVERLAP = 400
# Предохранитель: не более 24 чанков (~144K символов) за один анализ.
MAX_CHUNKS = 24

_ENTITY_PROMPT = """Проанализируй фрагмент учебного текста и извлеки структурированные \
сущности знаний.

Для каждой сущности укажи:
- type: один из "concept", "formula", "theorem", "example", "method"
- title: название на русском
- title_en: название на английском
- content: определение/описание (1-3 предложения)
- difficulty: 0.0..1.0 (0=тривиально, 1=олимпиада)
- tags: ключевые слова (список)

Верни СТРОГО JSON-объект с ключом "entities" (список). Без пояснений.

ДОМЕН: {domain}

ТЕКСТ:
{text}
"""

_SUMMARY_PROMPT = """Кратко проанализируй фрагмент источника. Верни СТРОГО JSON-объект:
{{
  "key_points": ["главные тезисы фрагмента, 2-5 пунктов"],
  "formulas": ["ключевые формулы в LaTeX, если есть"],
  "topics": ["затронутые темы"]
}}

ТЕКСТ:
{text}
"""

# Модульный кэш результатов анализа: sha256(mode|text)[:16] -> результат.
_CACHE: Dict[str, Any] = {}


def _cache_key(mode: str, text: str) -> str:
    return hashlib.sha256(f"{mode}|{text}".encode("utf-8")).hexdigest()[:16]


def chunk_text(
    text: str,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> List[str]:
    """Режет текст на перекрывающиеся куски по границам абзацев/предложений.

    Перекрытие сохраняет контекст на стыках (сущность на границе чанка не теряется).
    """
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_chars, n)
        # Стараемся резать по границе абзаца/предложения в пределах последних 600 симв.
        if end < n:
            window = text[end - 600 : end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if cut != -1:
                end = end - 600 + cut + 1
        chunks.append(text[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def _safe_json(raw: str) -> Optional[dict]:
    """Устойчивый разбор JSON из ответа LLM: срезает ```-ограждения и мусор.

    Reasoning-модели часто оборачивают JSON в markdown или добавляют текст вокруг —
    извлекаем первый сбалансированный объект {...}.
    """
    if not raw:
        return None
    s = raw.strip()
    # Срезать markdown-ограждения ```json ... ```
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Найти первый сбалансированный объект.
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _make_llm():
    """LLM-клиент по LLM_BACKEND — делегирует единой фабрике src.models."""
    from src.models import create_llm_client

    return create_llm_client()


class SourceAnalyzer:
    """Чанкинг + параллельный анализ + кэш для любых текстовых источников."""

    def __init__(
        self,
        llm_client=None,
        chunk_chars: int = DEFAULT_CHUNK_CHARS,
        overlap: int = DEFAULT_OVERLAP,
        max_workers: int = 4,
    ):
        self._llm = llm_client
        self._chunk_chars = chunk_chars
        self._overlap = overlap
        self._max_workers = max_workers

    def _get_llm(self):
        if self._llm is None:
            self._llm = _make_llm()
        return self._llm

    def _generate_json(self, prompt: str) -> Optional[dict]:
        """Один LLM-вызов с устойчивым разбором JSON. None при сбое."""
        try:
            llm = self._get_llm()
            # thinking=False/temperature низкая — для извлечения нужна детерминированность.
            try:
                resp = llm.generate(prompt, temperature=0.2, max_tokens=2048, thinking=False)
            except TypeError:
                # Старый LLMClient может не принимать часть kwargs.
                resp = llm.generate(prompt)
            return _safe_json(resp)
        except Exception as e:
            logger.warning(f"SourceAnalyzer LLM call failed: {e}")
            return None

    def _map_chunks(self, chunks: List[str], prompt_fmt, key: str) -> List[dict]:
        """Параллельно прогоняет чанки через prompt_fmt(chunk) и собирает list по key."""
        if not chunks:
            return []
        results: List[dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(self._generate_json, prompt_fmt(c)): i for i, c in enumerate(chunks)}
            for fut in concurrent.futures.as_completed(futures):
                data = fut.result()
                if data and isinstance(data.get(key), list):
                    results.extend(data[key])
        return results

    # ── Path B: полное извлечение сущностей по всему документу ──────────

    def extract_entities(self, text: str, domain: str = "math") -> List[Dict]:
        """Извлекает сущности из ВСЕГО документа (чанкинг+параллель), дедуп по title.

        Заменяет старый _extract_entities с обрезкой text[:3000].
        """
        ck = _cache_key(f"entities:{domain}", text)
        if ck in _CACHE:
            logger.debug("SourceAnalyzer entities cache hit")
            return _CACHE[ck]

        chunks = chunk_text(text, self._chunk_chars, self._overlap)
        if len(chunks) > MAX_CHUNKS:
            logger.warning(
                f"Источник {len(text)} симв. → {len(chunks)} чанков, обрабатываю первые {MAX_CHUNKS} (предохранитель)."
            )
            chunks = chunks[:MAX_CHUNKS]

        raw = self._map_chunks(chunks, lambda c: _ENTITY_PROMPT.format(domain=domain, text=c), "entities")

        # Дедуп по нормализованному title (сущность на стыке чанков встречается дважды).
        seen: Dict[str, Dict] = {}
        for ent in raw:
            title = str(ent.get("title", "")).strip().lower()
            if not title:
                continue
            if title not in seen:
                seen[title] = ent
        merged = list(seen.values())
        logger.info(f"SourceAnalyzer: {len(chunks)} чанков → {len(raw)} сырых → {len(merged)} уникальных сущностей")
        _CACHE[ck] = merged
        return merged

    # ── Path A: быстрый дайджест для контекста чата ────────────────────

    def summarize(self, text: str, source_name: str = "источник") -> Dict[str, Any]:
        """Сжатый дайджест источника для подмешивания в контекст тьютора.

        Возвращает {summary, key_points, formulas, topics, source_name}.
        """
        ck = _cache_key("summary", text)
        if ck in _CACHE:
            return _CACHE[ck]

        chunks = chunk_text(text, self._chunk_chars, self._overlap)
        if len(chunks) > MAX_CHUNKS:
            logger.warning(f"summarize: {len(chunks)} чанков → беру первые {MAX_CHUNKS}")
            chunks = chunks[:MAX_CHUNKS]

        key_points: List[str] = []
        formulas: List[str] = []
        topics: List[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = [pool.submit(self._generate_json, _SUMMARY_PROMPT.format(text=c)) for c in chunks]
            for fut in concurrent.futures.as_completed(futures):
                data = fut.result()
                if not data:
                    continue
                key_points.extend(x for x in (data.get("key_points") or []) if isinstance(x, str))
                formulas.extend(x for x in (data.get("formulas") or []) if isinstance(x, str))
                topics.extend(x for x in (data.get("topics") or []) if isinstance(x, str))

        # Дедуп с сохранением порядка.
        def _dedup(items: List[str]) -> List[str]:
            out, seen = [], set()
            for x in items:
                k = x.strip().lower()
                if k and k not in seen:
                    seen.add(k)
                    out.append(x.strip())
            return out

        key_points, formulas, topics = _dedup(key_points), _dedup(formulas), _dedup(topics)
        summary = "; ".join(key_points[:6]) if key_points else "(не удалось извлечь ключевые тезисы)"
        result = {
            "source_name": source_name,
            "summary": summary,
            "key_points": key_points[:12],
            "formulas": formulas[:12],
            "topics": _dedup(topics)[:10],
            "chunks": len(chunks),
        }
        _CACHE[ck] = result
        return result

    def to_context_block(self, digest: Dict[str, Any]) -> str:
        """Форматирует дайджест в компактный блок для подмешивания в промпт тьютора."""
        lines = [f"[Источник: {digest.get('source_name', 'источник')}]"]
        if digest.get("topics"):
            lines.append("Темы: " + ", ".join(digest["topics"]))
        if digest.get("key_points"):
            lines.append("Ключевые тезисы:")
            lines.extend(f"  • {p}" for p in digest["key_points"])
        if digest.get("formulas"):
            lines.append("Формулы: " + "; ".join(digest["formulas"]))
        return "\n".join(lines)


def clear_cache() -> None:
    """Очистить кэш анализа (для тестов / переобработки)."""
    _CACHE.clear()
