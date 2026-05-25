"""Генератор каркаса ВКР из образца (clone template, clear content, build structure).

Идемпотентный: перезапуск пересобирает каркас. Источник стилей — образец ВКР,
источник библиографии — DIPLOMA_PLAN.md.

Usage: uv run python scripts/build_vkr_skeleton.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
TEMPLATE = ROOT / "ВКР(10) (3).docx"
PLAN = ROOT / "docs/diploma/DIPLOMA_PLAN.md"
OUT = ROOT / "docs/diploma/ВКР_Сухацкий_2026.docx"

CUT_HEADING = "АННОТАЦИЯ"  # первый контент-параграф образца (Heading 1)


def clear_content_from_cutpoint(doc) -> None:
    """Удаляет body-элементы от параграфа CUT_HEADING до конца, сохраняя sectPr."""
    body = doc.element.body
    cut_el = None
    for p in doc.paragraphs:
        if p.text.strip() == CUT_HEADING:
            cut_el = p._element
            break
    if cut_el is None:
        raise RuntimeError(f"cut point {CUT_HEADING!r} not found in template")
    to_remove = []
    el = cut_el
    while el is not None:
        nxt = el.getnext()
        if el.tag != qn("w:sectPr"):  # sectPr (поля страницы) сохраняем
            to_remove.append(el)
        el = nxt
    for el in to_remove:
        body.remove(el)


def main() -> None:
    doc = Document(str(TEMPLATE))
    clear_content_from_cutpoint(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"[ok] cleared + saved skeleton base -> {OUT}")


if __name__ == "__main__":
    main()
