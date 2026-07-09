"""Встроить скриншоты UI в Приложение А собранного ВКР.

Логика: найти заголовок «Приложение А.» в docx, заменить placeholder-параграф
после него на серию рисунок + подпись («Рисунок А.N — Описание» по ГОСТ).

Usage:
    uv run python scripts/embed_screenshots.py
    uv run python scripts/embed_screenshots.py --input docs/diploma/ВКР.docx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows-консоль по умолчанию cp1251 → роняет print со стрелками/тире.
# Переключаем stdout/stderr на UTF-8 для корректной русской диагностики.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches

# (filename, caption) — порядок соответствует ГОСТ-нумерации А.1, А.2, ...
SCREENSHOTS: list[tuple[str, str]] = [
    ("screen_main_midnight.png", "Главный экран в тёмной теме (Midnight)"),
    ("screen_main_daylight.png", "Главный экран в светлой теме (Daylight)"),
    ("screen_graph.png", "Граф знаний (Knowledge Forge)"),
    ("screen_sources.png", "Источники знаний и предметные домены"),
]

# Целевая ширина рисунка в дюймах (вписывается в A4 — 6.0 дюйма).
PICTURE_WIDTH_INCHES = 6.0

ROOT = Path(__file__).parent.parent
DEFAULT_INPUT = ROOT / "docs/diploma/ВКР_Сухацкий_2026.docx"
DEFAULT_OUTPUT = ROOT / "docs/diploma/ВКР_Сухацкий_2026_with_screenshots.docx"
DEFAULT_ASSETS = ROOT / "docs/diploma/assets"

APPENDIX_A_PREFIX = "Приложение А"
PLACEHOLDER_PREFIX = "["


def find_appendix_paragraph(doc: Document) -> int | None:
    """Вернуть индекс параграфа с заголовком «Приложение А.» (или None)."""
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if text.startswith(APPENDIX_A_PREFIX) or text.startswith(APPENDIX_A_PREFIX.upper()):
            return i
    return None


def remove_placeholder_after(doc: Document, heading_index: int) -> bool:
    """Удалить следующий за заголовком placeholder-параграф (текст начинается с '[').

    Возвращает True если placeholder удалён, False — если placeholder не найден.
    """
    paragraphs = doc.paragraphs
    if heading_index + 1 >= len(paragraphs):
        return False
    next_p = paragraphs[heading_index + 1]
    if next_p.text.strip().startswith(PLACEHOLDER_PREFIX):
        body = doc.element.body
        body.remove(next_p._element)
        return True
    return False


def insert_picture_block(
    doc: Document,
    after_element,
    image_path: Path,
    caption: str,
):
    """Вставить после `after_element` параграф с центрированной картинкой и
    параграф-подпись. Возвращает последний вставленный параграф (для цепочки).
    """
    # Создаём два новых параграфа в конце документа (используя add_paragraph),
    # затем переносим их XML-элементы туда, куда нужно.
    pic_para = doc.add_paragraph()
    pic_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = pic_para.add_run()
    run.add_picture(str(image_path), width=Inches(PICTURE_WIDTH_INCHES))

    cap_para = doc.add_paragraph(caption)
    cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in cap_para.runs:
        run.italic = True

    # Переносим элементы в нужное место документа.
    pic_el = pic_para._element
    cap_el = cap_para._element
    body = doc.element.body
    body.remove(pic_el)
    body.remove(cap_el)
    after_element.addnext(pic_el)
    pic_el.addnext(cap_el)
    return cap_el


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Исходный docx (по умолчанию: {DEFAULT_INPUT.name})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Выходной docx (по умолчанию: {DEFAULT_OUTPUT.name})",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=DEFAULT_ASSETS,
        help="Папка со скриншотами PNG",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: входной docx не найден: {args.input}", file=sys.stderr)
        return 2
    if not args.assets_dir.exists():
        print(f"ERROR: папка assets не найдена: {args.assets_dir}", file=sys.stderr)
        return 2

    missing = [fn for fn, _ in SCREENSHOTS if not (args.assets_dir / fn).exists()]
    if missing:
        print(
            f"ERROR: не найдены скриншоты: {missing}\nОжидаются в {args.assets_dir}",
            file=sys.stderr,
        )
        return 2

    print(f"Открываю: {args.input}")
    doc = Document(str(args.input))

    heading_idx = find_appendix_paragraph(doc)
    if heading_idx is None:
        print(
            f"ERROR: заголовок «{APPENDIX_A_PREFIX}» не найден в документе.",
            file=sys.stderr,
        )
        return 3
    heading_p = doc.paragraphs[heading_idx]
    print(f"Найден заголовок [{heading_idx}]: {heading_p.text!r}")

    if remove_placeholder_after(doc, heading_idx):
        print("Удалён placeholder-параграф.")
    else:
        print("Placeholder не найден — вставляю сразу после заголовка.")

    # Вставляем рисунки В ОБРАТНОМ порядке после заголовка, чтобы итоговый
    # порядок совпал с SCREENSHOTS (каждая новая вставка идёт ПОСЛЕ heading).
    after_el = heading_p._element
    last_inserted = after_el
    for i, (filename, caption_text) in enumerate(SCREENSHOTS, start=1):
        image_path = args.assets_dir / filename
        gost_caption = f"Рисунок А.{i} — {caption_text}"
        last_inserted = insert_picture_block(doc, last_inserted, image_path, gost_caption)
        print(f"  + А.{i}: {filename} → «{gost_caption}»")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(args.output))
    print(f"\nСохранено: {args.output}")
    print(f"Размер: {args.output.stat().st_size / 1024:.1f} КБ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
