"""HTML (Reveal.js) → PPTX через headless Chrome.

Шаги:
1. Распарсить data-screen-label из HTML.
2. Сделать temp-копию HTML с CSS-оверрайдом, который форсирует
   видимость всех Reveal.js fragment-элементов (иначе они скрыты до клика).
3. Для каждого слайда — headless Chrome с URL hash #/N → screenshot 1920×1080.
4. Сшить PPTX (16:9, 13.33" × 7.5") с full-bleed image на каждом слайде.
5. В pptx-метаданных каждого слайда — заголовок из data-screen-label
   (для outline view и поиска) + notes со ссылкой на оригинал.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from pptx import Presentation
from pptx.util import Emu, Pt

PROJECT = Path(__file__).resolve().parents[2]
HTML_SRC = PROJECT / "docs" / "diploma" / "Презентация_v2 (1).html"
RENDER_DIR = PROJECT / "_tmp_slides"
PPTX_OUT = PROJECT / "docs" / "diploma" / "Презентация_v2.pptx"

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WIDTH, HEIGHT = 1920, 1080  # 16:9 при 2× для retina-чёткости

SLIDE_W = Emu(12192000)  # 13.33"
SLIDE_H = Emu(6858000)   # 7.5"

# CSS-оверрайд для статичного рендера в PPTX:
# 1) Прячет Reveal.js UI (прогресс-бар 4 px и controls — это и есть «чёрная полоса»).
# 2) Форсирует видимость fragment-элементов (опция .visible активируется по клику).
# 3) Останавливает CSS-анимации в стабильной фазе (delay = -2 s, paused).
FRAGMENT_OVERRIDE_CSS = """
<style id="pptx-export-override">
/* === Скрываем UI Reveal.js + custom deck-chrome (это и есть чёрная полоса) === */
.reveal .progress,
.reveal .controls,
.reveal .slide-number,
.reveal .navigate-up,
.reveal .navigate-down,
.reveal .navigate-left,
.reveal .navigate-right,
.reveal aside,
.reveal-viewport > .controls,
.deck-progress,
.deck-toc,
#deck-toc { display: none !important; }
/* Reveal.js летit slides по vertical/horizontal aspect — даже при margin:0 */
/* остаётся ~5-7 % паддинг. Прокрашиваем body в editorial-цвет (#0F2618 = */
/* --bg в текущем режиме TWEAK_DEFAULTS), чтобы letterbox был НЕВИДИМЫМ. */
html, body, .reveal, .reveal-viewport { background: #0F2618 !important; }
/* === Reveal.js fragments — раскрываем все === */
.reveal .slides section .fragment,
.reveal .slides section .fragment.fade-in-up,
.reveal .slides section .fragment.fade-in,
.reveal .slides section .fragment.fade-up,
.reveal .slides section .fragment.fade-down,
.reveal .slides section .fragment.fade-left,
.reveal .slides section .fragment.fade-right,
.reveal .slides section .fragment.scale-up,
.reveal .slides section .fragment.scale-down,
.reveal .slides section .fragment.highlight-current-blue,
.reveal .slides section .fragment.highlight-red,
.reveal .slides section .fragment.semi-fade-out {
  opacity: 1 !important;
  visibility: visible !important;
  transform: none !important;
  filter: none !important;
}
/* === Все CSS-анимации замораживаем в стабильной фазе === */
* {
  animation-play-state: paused !important;
  animation-delay: -2s !important;
}
</style>
"""


def parse_slide_labels(html_path: Path) -> list[str]:
    text = html_path.read_text(encoding="utf-8")
    return re.findall(r'<section\s+data-screen-label="([^"]+)"', text)


def make_export_html(src: Path) -> Path:
    """Создаёт temp-копию HTML с CSS-оверрайдом для экспорта."""
    text = src.read_text(encoding="utf-8")
    # Вставляем оверрайд непосредственно перед </head>
    if "</head>" not in text:
        raise RuntimeError("В HTML нет </head> — некуда вставить оверрайд")
    patched = text.replace("</head>", FRAGMENT_OVERRIDE_CSS + "\n</head>", 1)
    # Сохраняем в той же директории (чтобы относительные пути CDN/шрифтов работали)
    out = src.parent / "_export_v2.html"
    out.write_text(patched, encoding="utf-8")
    return out


def html_to_file_uri(path: Path) -> str:
    abs_path = str(path.resolve()).replace("\\", "/")
    if not abs_path.startswith("/"):
        abs_path = "/" + abs_path
    return "file://" + quote(abs_path, safe="/:")


def render_slide(uri: str, slide_idx: int, out_png: Path) -> None:
    abs_out = str(out_png.resolve())
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--window-size={WIDTH},{HEIGHT}",
        "--virtual-time-budget=8000",
        f"--screenshot={abs_out}",
        f"{uri}#/{slide_idx}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if not out_png.exists():
        raise RuntimeError(
            f"Chrome не создал {out_png.name}.\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )


def set_slide_title(slide, title: str) -> None:
    """Невидимый title-textbox для outline view PowerPoint."""
    txBox = slide.shapes.add_textbox(Emu(-100000), Emu(-100000), Emu(50000), Emu(50000))
    tf = txBox.text_frame
    tf.text = title
    for p in tf.paragraphs:
        for r in p.runs:
            r.font.size = Pt(1)


def build():
    if not HTML_SRC.exists():
        sys.exit(f"HTML не найден: {HTML_SRC}")
    if not Path(CHROME).exists():
        sys.exit(f"Chrome не найден: {CHROME}")

    labels = parse_slide_labels(HTML_SRC)
    print(f"Слайдов в HTML: {len(labels)}")

    # Чистый рендер-каталог
    if RENDER_DIR.exists():
        shutil.rmtree(RENDER_DIR)
    RENDER_DIR.mkdir(parents=True)

    # Подготовим патченную HTML
    export_html = make_export_html(HTML_SRC)
    print(f"Создан экспортный HTML с CSS-оверрайдом: {export_html.name}")

    try:
        uri = html_to_file_uri(export_html)
        print(f"Рендер в {WIDTH}×{HEIGHT}...\n")

        pngs: list[Path] = []
        for i, label in enumerate(labels):
            out = RENDER_DIR / f"slide_{i:02d}.png"
            print(f"  [{i + 1:02d}/{len(labels)}] {label}", end=" ... ", flush=True)
            render_slide(uri, i, out)
            print(f"OK ({out.stat().st_size // 1024} KB)")
            pngs.append(out)

        # Сборка PPTX
        print(f"\nСборка PPTX → {PPTX_OUT.name}")
        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H

        blank_layout = prs.slide_layouts[6]

        for i, (png, label) in enumerate(zip(pngs, labels)):
            slide = prs.slides.add_slide(blank_layout)
            slide.shapes.add_picture(str(png), 0, 0, width=SLIDE_W, height=SLIDE_H)
            set_slide_title(slide, label)
            notes = slide.notes_slide.notes_text_frame
            notes.text = (
                f"Оригинал: docs/diploma/Презентация_v2 (1).html#/{i}\n"
                f"Слайд: {label}\n"
                f"Примечание: PPTX-версия — статический рендер. CSS-анимации "
                f"(токен-курсор, logit-bars) и slide-переходы Reveal.js в pptx "
                f"не переносятся; для интерактивной демонстрации используй HTML."
            )

        PPTX_OUT.parent.mkdir(parents=True, exist_ok=True)
        prs.save(PPTX_OUT)
        size_kb = PPTX_OUT.stat().st_size // 1024
        print(f"\n✓ Сохранено: {PPTX_OUT}  ({size_kb:,} KB)")
        print(f"  Слайдов: {len(labels)}, формат 16:9 (13.33\" × 7.5\")")
    finally:
        # Удаляем временный экспортный HTML
        if export_html.exists():
            export_html.unlink()
            print(f"\nУдалён временный {export_html.name}")


if __name__ == "__main__":
    build()
