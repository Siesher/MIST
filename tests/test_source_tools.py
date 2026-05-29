"""TDD: инструменты-«библиотекарь» source_tools (агентный доступ, без RAG).

Детерминированно, без БД/LLM/эмбеддингов — над внедрённой in-memory библиотекой.
"""

from __future__ import annotations

import json

from src.tools.source_tools import (
    list_sources,
    read_source,
    search_in_source,
    set_source_library,
)

LIB = {
    "s1": {
        "title": "Конспект по интегралам",
        "domain": "math",
        "kind": "text",
        "text": "Интеграл — это предел интегральных сумм. " + "A" * 50,
    },
    "s2": {
        "title": "ВКР FID",
        "domain": "cs",
        "kind": "pdf",
        "text": "FID измеряет близость сгенерированных изображений к реальным. " + "B" * 20000,
    },
}


def setup_function() -> None:
    set_source_library(LIB)


def test_list_sources_returns_metadata():
    data = json.loads(list_sources())
    assert data["count"] == 2
    ids = {s["id"] for s in data["sources"]}
    assert ids == {"s1", "s2"}
    s2 = next(s for s in data["sources"] if s["id"] == "s2")
    assert s2["title"] == "ВКР FID"
    assert s2["chars"] > 20000


def test_read_source_paginates():
    p1 = json.loads(read_source("s2", part=1, part_size=9000))
    assert p1["part"] == 1
    assert p1["total_parts"] >= 3
    assert len(p1["text"]) <= 9000
    p2 = json.loads(read_source("s2", part=2, part_size=9000))
    assert p2["text"] != p1["text"]


def test_read_source_invalid_id():
    assert "error" in json.loads(read_source("nope"))


def test_search_in_source_finds_substring_with_context():
    res = json.loads(search_in_source("близость сгенерированных"))
    assert res["count"] >= 1
    hit = res["hits"][0]
    assert hit["source_id"] == "s2"
    assert "близость" in hit["excerpt"].lower()


def test_search_in_source_filtered_and_no_match():
    res = json.loads(search_in_source("интеграл", source_id="s1"))
    assert res["count"] >= 1
    assert all(h["source_id"] == "s1" for h in res["hits"])
    none = json.loads(search_in_source("zzznotfoundzzz"))
    assert none["count"] == 0


def test_empty_library_graceful():
    set_source_library({})
    assert json.loads(list_sources())["count"] == 0
    assert "error" in json.loads(read_source("s1"))
    assert json.loads(search_in_source("x"))["count"] == 0


def test_search_matches_inflected_forms():
    """RU-стемминг: запрос «производные» находит «производной» (грамм. вариант)."""
    set_source_library(
        {
            "m": {
                "title": "Производные",
                "domain": "math",
                "kind": "text",
                "text": "Производной функции называется предел отношения приращения функции.",
            }
        }
    )
    res = json.loads(search_in_source("вычисли производные функции"))
    assert res["count"] >= 1
    assert res["hits"][0]["source_id"] == "m"
