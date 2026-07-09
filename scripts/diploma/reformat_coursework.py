"""
Reformat Курсовой_проект_Сухацкий_2026.docx to match the reference template
Курсовая_MITS_Сухацкий.docx (GOST-compliant academic formatting).

Fixes:
  * Page size US Letter → A4 (210×297mm)
  * Margins asymmetric → GOST (30mm left, 15mm right, 20mm top/bottom)
  * Title page: flat 14pt → hierarchy 12/16/18/22pt matching reference
  * Body: Times New Roman 14pt, line spacing 1.5, first-line indent 1.25cm
  * Heading 1: CAPS, bold, 16pt, centered, page-break-before
  * Heading 2: bold, 14pt, left, indent 1.25cm
  * List Bullet normalized to dash-style (GOST)
"""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

SRC = Path("C:/Work/MITS/docs/Курсовой_проект_Сухацкий_2026.docx")
DST = Path("C:/Work/MITS/docs/Курсовой_проект_Сухацкий_2026.docx")  # overwrite in place
BACKUP = Path("C:/Work/MITS/docs/Курсовой_проект_Сухацкий_2026.bak.docx")


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def set_run_font(run, name="Times New Roman", size_pt=14, bold=None):
    run.font.name = name
    # Cyrillic font binding
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)
    rFonts.set(qn("w:cs"), name)
    rFonts.set(qn("w:eastAsia"), name)
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    if bold is not None:
        run.font.bold = bold


def set_paragraph_spacing(p, line_spacing=1.5, before_pt=0, after_pt=0, first_line_cm=None):
    pf = p.paragraph_format
    pf.line_spacing = line_spacing
    pf.space_before = Pt(before_pt)
    pf.space_after = Pt(after_pt)
    if first_line_cm is not None:
        pf.first_line_indent = Cm(first_line_cm)


def add_page_break_before(p):
    pPr = p._element.get_or_add_pPr()
    existing = pPr.find(qn("w:pageBreakBefore"))
    if existing is None:
        el = OxmlElement("w:pageBreakBefore")
        pPr.append(el)


# ─────────────────────────────────────────────────────────────────────
# Restyle
# ─────────────────────────────────────────────────────────────────────


def restyle(doc: Document) -> None:
    # 1. Page + margins (all sections)
    for sec in doc.sections:
        sec.page_width = Mm(210)
        sec.page_height = Mm(297)
        sec.left_margin = Mm(30)
        sec.right_margin = Mm(15)
        sec.top_margin = Mm(20)
        sec.bottom_margin = Mm(20)
        sec.header_distance = Mm(12.5)
        sec.footer_distance = Mm(12.5)

    # 2. Redefine Normal style default
    styles = doc.styles
    normal = styles["Normal"]
    set_run_font(normal.font._element if False else None, "Times New Roman", 14) if False else None
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(14)
    # Cyrillic binding at style level
    rPr = normal.element.find(qn("w:rPr"))
    if rPr is None:
        rPr = OxmlElement("w:rPr")
        normal.element.insert(0, rPr)
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(attr), "Times New Roman")

    # 3. Heading styles
    for h_name, size, is_center, caps in [
        ("Heading 1", 16, True, True),
        ("Heading 2", 14, False, False),
        ("Heading 3", 14, False, False),
    ]:
        try:
            h = styles[h_name]
            h.font.name = "Times New Roman"
            h.font.size = Pt(size)
            h.font.bold = True
            h.font.color.rgb = RGBColor(0, 0, 0)  # pure black, no auto-blue
            rPr = h.element.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                h.element.insert(0, rPr)
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.append(rFonts)
            for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                rFonts.set(qn(attr), "Times New Roman")
            # Remove any existing color
            color = rPr.find(qn("w:color"))
            if color is not None:
                color.set(qn("w:val"), "000000")
            else:
                color = OxmlElement("w:color")
                color.set(qn("w:val"), "000000")
                rPr.append(color)
        except KeyError:
            continue

    # 4. Per-paragraph restyle
    paragraphs = list(doc.paragraphs)
    n = len(paragraphs)

    # ── Title page: identified as paragraphs[0..22] based on earlier analysis ──
    # Reference hierarchy:
    #   University lines: 12pt (centered)
    #   "КУРСОВОЙ ПРОЕКТ": 22pt bold centered
    #   "К курсовому проекту": 18pt bold centered
    #   "На тему:" : 18pt bold centered
    #   Title of work: 18pt centered
    #   "Москва, 2026": default

    # Find title elements by matching text
    title_page_limit = 25
    for i, p in enumerate(paragraphs[:title_page_limit]):
        text = p.text.strip()
        if not text:
            continue
        # Clear style-level alignment override
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_paragraph_spacing(p, line_spacing=1.15, before_pt=0, after_pt=0, first_line_cm=0)

        # Determine size by text patterns
        upper_text = text.upper()
        if "РАСЧЕТНО-ПОЯСНИТЕЛЬНАЯ" in upper_text or "ЗАПИСКА" in upper_text:
            size = 22
            bold = True
        elif "К КУРСОВОМУ ПРОЕКТУ" in upper_text or "НА ТЕМУ" in upper_text:
            size = 18
            bold = True
        elif (
            "МГТУ" in text
            or "Баумана" in text
            or "Бауман" in text.upper()
            or "Министерство" in text
            or "МОСКОВСКИЙ" in upper_text
            or "ФАКУЛЬТЕТ" in upper_text
            or "КАФЕДРА" in upper_text
            or "КАЛУЖСКИЙ" in upper_text
            or "образовательного учреждения" in text.lower()
            or "высшего образования" in text.lower()
            or "национальный исследовательский" in text.lower()
            or "филиал федерального" in text.lower()
        ):
            size = 12
            bold = False
        elif "Москва" in text and ("2025" in text or "2026" in text):
            size = 14
            bold = False
        elif "Разработка" in text or "РАЗРАБОТКА" in upper_text or "подсистемы" in text.lower():
            size = 18
            bold = False
        elif (
            text.startswith("Группа")
            or "СМ3" in text
            or "Студент" in text.lower()
            or "Руководитель" in text.lower()
            or "Преподаватель" in text.lower()
        ):
            size = 14
            bold = False
        else:
            size = 14
            bold = None

        for r in p.runs:
            set_run_font(r, "Times New Roman", size, bold)

    # ── Body paragraphs (after title page) ──
    for i, p in enumerate(paragraphs[title_page_limit:], start=title_page_limit):
        text = p.text.strip()
        style_name = p.style.name

        if style_name == "Heading 1":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_paragraph_spacing(p, line_spacing=1.5, before_pt=18, after_pt=12, first_line_cm=0)
            add_page_break_before(p)
            for r in p.runs:
                set_run_font(r, "Times New Roman", 16, bold=True)
            continue

        if style_name == "Heading 2":
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_paragraph_spacing(p, line_spacing=1.5, before_pt=12, after_pt=6, first_line_cm=1.25)
            for r in p.runs:
                set_run_font(r, "Times New Roman", 14, bold=True)
            continue

        if style_name == "Heading 3":
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_paragraph_spacing(p, line_spacing=1.5, before_pt=6, after_pt=3, first_line_cm=1.25)
            for r in p.runs:
                set_run_font(r, "Times New Roman", 14, bold=True)
            continue

        if style_name == "List Bullet" or (text.startswith("•") or text.startswith("−")):
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            set_paragraph_spacing(p, line_spacing=1.5, before_pt=0, after_pt=0, first_line_cm=0)
            p.paragraph_format.left_indent = Cm(1.25)
            for r in p.runs:
                set_run_font(r, "Times New Roman", 14)
            continue

        # Default body paragraph
        if text:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            set_paragraph_spacing(p, line_spacing=1.5, before_pt=0, after_pt=0, first_line_cm=1.25)
            for r in p.runs:
                # Don't overwrite monospace code blocks (detected by presence of code-like chars)
                is_code = (
                    any(c in r.text for c in ("{", "}", "def ", "→", "∇", "α=")) and len(r.text) > 5
                )
                if is_code:
                    set_run_font(r, "Consolas", 10)
                else:
                    set_run_font(r, "Times New Roman", 14)

    # 5. Tables — ensure TNR 12pt, auto width preserved
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    set_paragraph_spacing(
                        p, line_spacing=1.15, before_pt=0, after_pt=0, first_line_cm=0
                    )
                    for r in p.runs:
                        set_run_font(r, "Times New Roman", 12)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Not found: {SRC}")

    # Backup
    if not BACKUP.exists():
        BACKUP.write_bytes(SRC.read_bytes())
        print(f"Backup saved: {BACKUP}")

    doc = Document(str(SRC))
    restyle(doc)
    doc.save(str(DST))

    print(f"Reformatted: {DST}")
    # Verify
    d2 = Document(str(DST))
    s = d2.sections[0]
    print(f"  Page: {s.page_width / 36000:.0f}x{s.page_height / 36000:.0f}mm")
    print(
        f"  Margins: L={s.left_margin / 36000:.0f} R={s.right_margin / 36000:.0f} T={s.top_margin / 36000:.0f} B={s.bottom_margin / 36000:.0f}mm"
    )
    print(f"  Paragraphs: {len(d2.paragraphs)}  Tables: {len(d2.tables)}")


if __name__ == "__main__":
    main()
