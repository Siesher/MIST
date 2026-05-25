"""Сборка ВКР: skeleton (python-docx) + главы (pandoc md->docx с OMML) -> merge.

Usage: uv run python scripts/assemble_vkr.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

sys.path.insert(0, str(Path(__file__).parent))
from build_vkr_skeleton import OUT, SECTION_IDS, TEMPLATE, build_document  # noqa: E402

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


def md_to_fragment(md_path: Path, pandoc: str) -> Path:
    """pandoc md -> временный docx с OMML-формулами и стилями образца."""
    frag = Path(tempfile.gettempdir()) / f"_vkr_frag_{md_path.stem}.docx"
    subprocess.run(
        [
            pandoc,
            str(md_path),
            "--shift-heading-level-by=1",
            f"--reference-doc={TEMPLATE}",
            "-o",
            str(frag),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return frag


def assemble() -> None:
    doc = build_document()
    pandoc = find_pandoc()
    populated = []
    for heading, sid in SECTION_IDS.items():
        md = CHAPTERS / f"{sid}.md"
        if md.exists() and md.read_text(encoding="utf-8").strip():
            frag = md_to_fragment(md, pandoc)
            n = merge_fragment(doc, heading, Document(str(frag)))
            populated.append(f"{sid}(+{n})")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT))
    print(f"[ok] assembled -> {OUT}")
    print(f"  наполнено секций: {len(populated)}: {populated}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    assemble()
