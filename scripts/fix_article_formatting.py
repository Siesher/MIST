"""Fix formatting of НИР article to match reference style (Лысенко).

Reference formatting (Статья_GNN_Лысенко):
- Font: Times New Roman throughout
- УДК: 14pt, regular, left-aligned
- Title: 18pt, BOLD (no italic), center
- Authors: 14pt, BOLD+ITALIC, justified
- Abstract: 14pt, ITALIC (no bold), justified
- Keywords "Ключевые слова:": 14pt, BOLD (label), rest regular, justified
- Body text: 14pt, regular, justified
- First body paragraph: 14pt, ITALIC, justified
- Table captions: 14pt, right-aligned, "Таблица N. Caption" on one line
- Table cells headers: 12pt, BOLD, center
- Table cells body: 12pt, regular, center
- References header: "Список литературы", BOLD
- References: 14pt, regular, justified, with "(дата обращения: DD.MM.YYYY)"
- English section: same pattern as Russian
"""

import re
import shutil
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

INPUT = Path("docs/НИР_управляемое_рассуждение_Сухацкий.docx")
OUTPUT = Path("docs/НИР_управляемое_рассуждение_Сухацкий_formatted.docx")
BACKUP = INPUT.with_suffix(".docx.bak")

FONT_NAME = "Times New Roman"


def get_text(paragraph) -> str:
    """Get full text of paragraph."""
    return "".join(run.text for run in paragraph.runs)


def set_run_format(
    run, size_pt: int, bold: bool = False, italic: bool = False, font: str = FONT_NAME
):
    """Set formatting for a single run."""
    run.font.name = font
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic


def set_paragraph_format(
    paragraph,
    size_pt: int,
    bold: bool = False,
    italic: bool = False,
    alignment=None,
    font: str = FONT_NAME,
):
    """Set formatting for all runs in a paragraph."""
    if alignment is not None:
        paragraph.alignment = alignment
    for run in paragraph.runs:
        set_run_format(run, size_pt, bold, italic, font)


def classify_paragraph(text: str, idx: int, total: int) -> str:
    """Classify paragraph by its content."""
    text_stripped = text.strip()

    if text_stripped.startswith("УДК"):
        return "udk"
    if idx == 1 and len(text_stripped) > 30:
        return "title_ru"
    if "loxterpoi@gmail.com" in text or "mkorlyakova@yandex.ru" in text:
        return "author"
    if text_stripped == "КФ МГТУ имени Н.Э. Баумана":
        return "affiliation_ru"
    if text_stripped == "Kaluga Branch of Bauman Moscow State Technical University":
        return "affiliation_en"
    if text_stripped.startswith("Ключевые слова:"):
        return "keywords_ru"
    if text_stripped.startswith("Keywords:"):
        return "keywords_en"
    if text_stripped.startswith("В статье представлен метод"):
        return "abstract_ru"
    if text_stripped.startswith("This article presents"):
        return "abstract_en"
    if text_stripped in ("Список источников", "Список литературы"):
        return "references_header"
    if text_stripped.startswith("Method of Controlled Reasoning"):
        return "title_en"
    if text_stripped.startswith("Sukhatsky") or text_stripped.startswith("Korlyakova"):
        return "author_en"
    if re.match(r"^\d+\.\s", text_stripped) and idx > 50:
        return "reference"
    if text_stripped.startswith("Таблица"):
        return "table_caption"
    if text_stripped in (
        "Домен",
        "Точность",
        "Кол-во задач",
        "Подход",
        "Clipped ratio",
        "Correctness (шаг 50)",
        "Сходимость",
        "Base",
        "GSPO",
        "KTO",
        "DPO (финал)",
        "Δ",
    ):
        return "table_header_cell"
    # Check if it's a table data cell (short, often numeric)
    if len(text_stripped) < 30 and (
        re.match(r"^[\d,\.%+−\-]+$", text_stripped)
        or text_stripped
        in ("Математика", "Физика", "Информатика", "Химия", "Биология", "Среднее", "Нет", "Да", "—")
    ):
        return "table_data_cell"

    return "body"


def fix_references_format(paragraph, text: str):
    """Fix reference format to match Лысенко style: add (дата обращения: ...)."""
    # Already has access date
    if "дата обращения" in text:
        return

    # Add access date to URL references
    if "URL:" in text or "https://" in text or "http://" in text:
        for run in paragraph.runs:
            if run.text.rstrip().endswith(")") or run.text.rstrip().endswith("."):
                continue
            # Find URL and append access date
            url_match = re.search(r"(https?://\S+)", run.text)
            if url_match:
                url = url_match.group(1).rstrip(".")
                run.text = run.text.replace(
                    url_match.group(0), f"{url} (дата обращения: 20.03.2026)."
                )


def main():
    # Backup original
    shutil.copy2(INPUT, BACKUP)
    print(f"Backup: {BACKUP}")

    doc = Document(str(INPUT))
    paragraphs = doc.paragraphs
    total = len(paragraphs)

    # Track first body paragraph (for italic styling like reference)
    first_body_found = False
    in_references = False

    for idx, para in enumerate(paragraphs):
        text = get_text(para)
        if not text.strip():
            continue

        ptype = classify_paragraph(text, idx, total)

        if ptype == "udk":
            set_paragraph_format(
                para, 14, bold=False, italic=False, alignment=WD_ALIGN_PARAGRAPH.LEFT
            )
            print(f"[{idx}] УДК: 14pt regular left")

        elif ptype == "title_ru":
            set_paragraph_format(
                para, 18, bold=True, italic=False, alignment=WD_ALIGN_PARAGRAPH.CENTER
            )
            print(f"[{idx}] Title RU: 18pt bold center")

        elif ptype == "title_en":
            set_paragraph_format(
                para, 18, bold=True, italic=False, alignment=WD_ALIGN_PARAGRAPH.CENTER
            )
            print(f"[{idx}] Title EN: 18pt bold center")

        elif ptype in ("author", "author_en"):
            set_paragraph_format(
                para, 14, bold=True, italic=True, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
            )
            print(f"[{idx}] Author: 14pt bold+italic justified")

        elif ptype in ("affiliation_ru", "affiliation_en"):
            set_paragraph_format(
                para, 14, bold=True, italic=True, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
            )
            print(f"[{idx}] Affiliation: 14pt bold+italic justified")

        elif ptype in ("abstract_ru", "abstract_en"):
            set_paragraph_format(
                para, 14, bold=False, italic=True, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
            )
            print(f"[{idx}] Abstract: 14pt italic justified")

        elif ptype == "keywords_ru":
            # "Ключевые слова:" bold, rest regular
            set_paragraph_format(
                para, 14, bold=True, italic=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
            )
            print(f"[{idx}] Keywords RU: 14pt bold justified")

        elif ptype == "keywords_en":
            set_paragraph_format(
                para, 14, bold=True, italic=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
            )
            print(f"[{idx}] Keywords EN: 14pt bold justified")

        elif ptype == "references_header":
            # Fix text: "Список источников" → "Список литературы"
            for run in para.runs:
                run.text = run.text.replace("Список источников", "Список литературы")
            set_paragraph_format(
                para, 14, bold=True, italic=False, alignment=WD_ALIGN_PARAGRAPH.CENTER
            )
            in_references = True
            print(f"[{idx}] References header: renamed + 14pt bold center")

        elif ptype == "reference":
            set_paragraph_format(
                para, 14, bold=False, italic=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
            )
            fix_references_format(para, text)
            print(f"[{idx}] Reference: 14pt regular justified")

        elif ptype == "table_caption":
            set_paragraph_format(
                para, 14, bold=False, italic=False, alignment=WD_ALIGN_PARAGRAPH.RIGHT
            )
            print(f"[{idx}] Table caption: 14pt regular right")

        elif ptype == "table_header_cell":
            set_paragraph_format(
                para, 12, bold=True, italic=False, alignment=WD_ALIGN_PARAGRAPH.CENTER
            )

        elif ptype == "table_data_cell":
            set_paragraph_format(
                para, 12, bold=False, italic=False, alignment=WD_ALIGN_PARAGRAPH.CENTER
            )

        elif ptype == "body":
            if not first_body_found:
                # First body paragraph is italic (like reference)
                set_paragraph_format(
                    para, 14, bold=False, italic=True, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
                )
                first_body_found = True
                print(f"[{idx}] First body: 14pt italic justified")
            else:
                set_paragraph_format(
                    para, 14, bold=False, italic=False, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
                )

    # Also fix table cells that are inside actual table objects
    for table in doc.tables:
        for row_idx, row in enumerate(table.rows):
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    for run in para.runs:
                        run.font.name = FONT_NAME
                        run.font.size = Pt(12)
                        # First row = header → bold
                        run.bold = row_idx == 0
                        run.italic = False

    doc.save(str(OUTPUT))
    print(f"\nSaved: {OUTPUT}")
    print(f"Original backup: {BACKUP}")


if __name__ == "__main__":
    main()
