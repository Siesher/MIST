"""Сборка ВКР: skeleton (python-docx) + главы (pandoc md->docx с OMML) -> merge.

Usage: uv run python scripts/assemble_vkr.py
"""

from __future__ import annotations

import os
import shutil
from copy import deepcopy
from pathlib import Path

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

ROOT = Path(__file__).parent.parent
CHAPTERS = ROOT / "docs/diploma/chapters"


def find_pandoc() -> str:
    """Локатор pandoc: PATH -> %LOCALAPPDATA%\\Pandoc -> Program Files."""
    found = shutil.which("pandoc")
    if found:
        return found
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Pandoc" / "pandoc.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise RuntimeError("pandoc не найден (PATH/LOCALAPPDATA/ProgramFiles)")


def merge_fragment(doc, heading_prefix: str, fragment_doc) -> int:
    """Вставляет body фрагмента после заголовка heading_prefix, удаляя placeholder.

    Возвращает число вставленных элементов. Raises если заголовок не найден.
    """
    body = doc.element.body
    heading_el = None
    for p in doc.paragraphs:
        if p.text.strip().startswith(heading_prefix):
            heading_el = p._element
            break
    if heading_el is None:
        raise ValueError(f"заголовок {heading_prefix!r} не найден")
    # удалить placeholder-параграф сразу после заголовка (текст начинается с '[')
    nxt = heading_el.getnext()
    if nxt is not None and nxt.tag == qn("w:p"):
        if Paragraph(nxt, doc).text.strip().startswith("["):
            body.remove(nxt)
    # вставить элементы фрагмента (кроме sectPr) после заголовка
    anchor = heading_el
    inserted = 0
    for child in list(fragment_doc.element.body):
        if child.tag == qn("w:sectPr"):
            continue
        new = deepcopy(child)
        anchor.addnext(new)
        anchor = new
        inserted += 1
    return inserted
