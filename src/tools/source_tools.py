"""Source library tools — агентный доступ к загруженным источникам (НЕ RAG).

Агент работает с источниками как с кодовой базой: list / read / search (grep).
Никаких эмбеддингов и векторного поиска — только чтение и лексический поиск над
библиотекой, инъецированной в память до tool-loop (по образцу navigator_tools).

Регистрируется в orchestrator_service рядом с SKI/Navigator и вызывается LLM в
chat / guided_learning / task_generator.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Размер одной «части» при чтении (символы). ~9000 ≈ 2-3K токенов — комфортно для 64K ctx.
READ_PART_CHARS = 9000
DEFAULT_MAX_HITS = 5

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
# Минимальный набор частых слов, не несущих смысла для поиска (RU/EN).
_STOPWORDS = {
    "что",
    "как",
    "для",
    "это",
    "или",
    "при",
    "над",
    "под",
    "его",
    "она",
    "они",
    "так",
    "там",
    "где",
    "кто",
    "чем",
    "the",
    "and",
    "for",
    "are",
    "you",
}


def _tokenize(text: str) -> List[str]:
    """Токены-слова в нижнем регистре (unicode)."""
    return _TOKEN_RE.findall(text.lower())


# Библиотека источников, внедряемая сервисом перед tool-loop.
# Форма: {source_id: {"title", "domain", "kind", "text"}}.
_LIBRARY: Dict[str, Dict[str, str]] = {}


def set_source_library(library: Dict[str, Dict[str, str]]) -> None:
    """Внедрить библиотеку источников для tool-dispatch (вызывается per-request)."""
    global _LIBRARY
    _LIBRARY = library or {}


# ── Tool dispatch ─────────────────────────────────────────────────────


def list_sources() -> str:
    """Список загруженных источников с метаданными (без текста)."""
    sources = [
        {
            "id": sid,
            "title": meta.get("title", "—"),
            "domain": meta.get("domain", "—"),
            "kind": meta.get("kind", "—"),
            "chars": len(meta.get("text", "")),
        }
        for sid, meta in _LIBRARY.items()
    ]
    return json.dumps({"sources": sources, "count": len(sources)}, ensure_ascii=False)


def read_source(source_id: str, part: int = 1, part_size: int = READ_PART_CHARS) -> str:
    """Прочитать часть текста источника (постраничная навигация по большим докам)."""
    meta = _LIBRARY.get(source_id)
    if meta is None:
        return json.dumps(
            {"error": f"источник не найден: {source_id}", "available": list(_LIBRARY)},
            ensure_ascii=False,
        )
    text = meta.get("text", "")
    total_parts = max(1, (len(text) + part_size - 1) // part_size)
    if part < 1 or part > total_parts:
        return json.dumps(
            {"error": f"part вне диапазона 1..{total_parts}", "total_parts": total_parts},
            ensure_ascii=False,
        )
    start = (part - 1) * part_size
    chunk = text[start : start + part_size]
    return json.dumps(
        {
            "source_id": source_id,
            "title": meta.get("title", "—"),
            "part": part,
            "total_parts": total_parts,
            "text": chunk,
        },
        ensure_ascii=False,
    )


_RU_SUFFIXES = (
    "ами",
    "ями",
    "ого",
    "его",
    "ому",
    "ему",
    "ыми",
    "ими",
    "ах",
    "ях",
    "ой",
    "ей",
    "ую",
    "юю",
    "ая",
    "яя",
    "ое",
    "ее",
    "ые",
    "ие",
    "ам",
    "ям",
    "ом",
    "ем",
    "ов",
    "ев",
    "ий",
    "ый",
    "их",
    "ых",
    "ть",
    "ся",
    "сь",
    "и",
    "ы",
    "а",
    "я",
    "е",
    "о",
    "у",
    "ь",
    "й",
)


def _stem(token: str) -> str:
    """Грубый русский стемминг: отбрасывает частые окончания (без зависимостей).

    Чтобы запрос «производные» находил «производной/производных» — иначе keyword-
    поиск по неизменяемой подстроке теряет грамматические варианты.
    """
    for suf in _RU_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token


def search_in_source(
    query: str,
    source_id: Optional[str] = None,
    max_hits: int = DEFAULT_MAX_HITS,
) -> str:
    """Поиск по словам (keyword-IR, НЕ эмбеддинги): сегменты с наибольшим числом
    совпавших слов запроса. По одному источнику (source_id) или по всем."""
    q_stems = {_stem(t) for t in _tokenize(query) if len(t) >= 3 and t not in _STOPWORDS}
    if not q_stems:
        return json.dumps({"query": query, "hits": [], "count": 0}, ensure_ascii=False)

    targets = (
        [(source_id, _LIBRARY[source_id])]
        if source_id and source_id in _LIBRARY
        else list(_LIBRARY.items())
    )

    scored = []
    for sid, meta in targets:
        title = meta.get("title", "—")
        for seg in re.split(r"(?<=[.!?])\s+|\n+", meta.get("text", "")):
            seg = seg.strip()
            if not seg:
                continue
            seg_low = seg.lower()
            matched = sum(1 for s in q_stems if s in seg_low)
            if matched:
                excerpt = seg[:400] + ("…" if len(seg) > 400 else "")
                scored.append((matched, sid, title, excerpt))

    scored.sort(key=lambda x: x[0], reverse=True)
    hits = [
        {"source_id": sid, "title": title, "matched_terms": m, "excerpt": excerpt}
        for m, sid, title, excerpt in scored[:max_hits]
    ]
    return json.dumps({"query": query, "hits": hits, "count": len(hits)}, ensure_ascii=False)


# ── Tool definitions (OpenAI function-calling format) ─────────────────

SOURCE_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_sources",
            "description": (
                "Список загруженных пользователем источников (учебники, конспекты, статьи, "
                "PDF) с id, названием, доменом и размером. Вызови ПЕРВЫМ, чтобы узнать, что "
                "есть в библиотеке, прежде чем читать или искать. Используй источники, когда "
                "вопрос или генерируемое задание могут на них опираться."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_source",
            "description": (
                "Прочитать содержимое источника по частям (часть ~9000 символов). Возвращает "
                "текст части и общее число частей. Используй для глубокого знакомства с "
                "материалом перед ответом или составлением задания по нему."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "id источника из list_sources"},
                    "part": {
                        "type": "integer",
                        "description": "Номер части (с 1). По умолчанию 1.",
                    },
                },
                "required": ["source_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_source",
            "description": (
                "Лексический поиск (по подстроке) в источнике или по всей библиотеке. "
                "Возвращает совпадения с окружающим контекстом. Быстрый способ найти "
                "конкретный термин/факт/формулу в большом документе, не читая его целиком."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Искомая подстрока/термин"},
                    "source_id": {
                        "type": "string",
                        "description": "Ограничить одним источником (опционально; иначе по всем)",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

SOURCE_FUNCTIONS = {
    "list_sources": list_sources,
    "read_source": read_source,
    "search_in_source": search_in_source,
}
