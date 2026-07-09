"""TDD: TutoringContext должен уметь нести чанки источника и выводить их в промпт.

Этап 2 document-RAG: поле chunks наполняется ретривером по прикреплённому
источнику и попадает в промпт тьютора через to_prompt_context().
"""

from __future__ import annotations

from src.knowledge.rag_retriever import TutoringContext


def test_to_prompt_context_includes_source_chunks():
    ctx = TutoringContext(
        chunks=[
            "FID оценивает близость сгенерированных изображений к реальным данным.",
            "Вход модели — растровое изображение плана.",
        ]
    )

    text = ctx.to_prompt_context()

    assert "FID оценивает близость" in text
    assert "растровое изображение плана" in text


def test_to_prompt_context_empty_chunks_no_source_block():
    ctx = TutoringContext()  # без чанков
    text = ctx.to_prompt_context()
    assert "ИСТОЧНИК" not in text.upper()
