"""Захват анимаций слайдов 5 и 6 в MP4 и встраивание в PPTX с автозапуском.

Что делает скрипт:
1. Запускает Playwright Chromium при 1920×1080 и грузит оригинальный HTML.
2. Через page.add_style_tag() инжектит CSS, который скрывает Reveal.js
   progress-bar и controls (это и есть «чёрная полоса снизу»),
   но не трогает анимации (в отличие от статичного html_to_pptx.py).
3. Для слайдов 5 (ThinkingBudget) и 6 (Демо · до/после):
   - Reveal.slide(N, 0, 0).
   - Ждёт инициализации JS.
   - Снимает 200 кадров через 40 мс (8 с при 25 fps).
   - Кодирует MP4 (H.264, yuv420p, max совместимость с PowerPoint).
4. Берёт _NEW.pptx, заменяет картинки на 5/6 на видео + poster image.
5. Для каждого видео-слайда инжектит XML-блок <p:timing>, который запускает
   видео автоматически при показе слайда (preset class mediacall, playFrom(0)).
"""
from __future__ import annotations

import io
import shutil
import time
from pathlib import Path

import imageio
from lxml import etree
from PIL import Image
from playwright.sync_api import sync_playwright
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Emu

PROJECT = Path(__file__).resolve().parents[2]
HTML_SRC = PROJECT / "docs" / "diploma" / "Презентация_v2 (1).html"
PPTX_IN = PROJECT / "docs" / "diploma" / "Презентация_v2.pptx"
PPTX_OUT = PROJECT / "docs" / "diploma" / "Презентация_v2_FINAL.pptx"
VIDEO_DIR = PROJECT / "_tmp_videos"
POSTER_DIR = PROJECT / "_tmp_posters"

W, H = 1920, 1080
FPS = 25
DURATION_S = 8
N_FRAMES = FPS * DURATION_S

TARGETS = [
    {"idx": 4, "name": "thinking_budget", "label": "05 ThinkingBudget — главное", "init_wait_ms": 300},
    {"idx": 5, "name": "demo_terminal",   "label": "06 Демо · до/после",          "init_wait_ms": 500},
]

SLIDE_W = Emu(12192000)
SLIDE_H = Emu(6858000)

# CSS для Playwright: прячем UI, оставляем анимации живыми.
INJECT_CSS = """
.reveal .progress, .reveal .controls, .reveal .slide-number,
.reveal .navigate-up, .reveal .navigate-down,
.reveal .navigate-left, .reveal .navigate-right,
.reveal aside,
.deck-progress, .deck-toc, #deck-toc { display: none !important; }
html, body, .reveal, .reveal-viewport { background: #0F2618 !important; }
/* Раскрываем фрагменты — но НЕ трогаем animation-play-state */
.fragment, .fragment.fade-in-up, .fragment.fade-in,
.fragment.fade-up, .fragment.fade-down,
.fragment.fade-left, .fragment.fade-right,
.fragment.scale-up, .fragment.scale-down,
.fragment.semi-fade-out {
  opacity: 1 !important;
  visibility: visible !important;
  transform: none !important;
  filter: none !important;
}
"""


def file_uri(path: Path) -> str:
    from urllib.parse import quote
    abs_path = str(path.resolve()).replace("\\", "/")
    if not abs_path.startswith("/"):
        abs_path = "/" + abs_path
    return "file://" + quote(abs_path, safe="/:")


def capture_animation(page, target: dict, video_path: Path, poster_path: Path) -> None:
    name = target["name"]
    print(f"  → {name}: Reveal.slide({target['idx']}, 0, 0)")
    page.evaluate(f"Reveal.slide({target['idx']}, 0, 0)")
    page.wait_for_timeout(target["init_wait_ms"])

    print(f"  → {name}: захват {N_FRAMES} кадров...")
    target_interval_s = 1.0 / FPS
    writer = imageio.get_writer(
        str(video_path), fps=FPS, codec="libx264",
        quality=8, pixelformat="yuv420p", macro_block_size=8,
    )

    next_t = time.perf_counter()
    poster_saved = False
    for i in range(N_FRAMES):
        now = time.perf_counter()
        if next_t > now:
            time.sleep(next_t - now)
        png_bytes = page.screenshot(type="png", clip={"x": 0, "y": 0, "width": W, "height": H})
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        if not poster_saved:
            img.save(poster_path, format="PNG", optimize=True)
            poster_saved = True
        if img.size != (W, H):
            img = img.resize((W, H), Image.LANCZOS)
        import numpy as np
        writer.append_data(np.array(img))
        next_t += target_interval_s
        if (i + 1) % 50 == 0:
            print(f"     ... {i + 1}/{N_FRAMES}")
    writer.close()
    size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"  → {name}: MP4 сохранён ({size_mb:.2f} MB)")


def find_movie_picture(slide) -> tuple | None:
    """Ищет в слайде <p:pic>, у которого внутри nvPr есть <a:videoFile>.

    ВАЖНО: videoFile — в namespace DrawingML (a:), не PresentationML (p:).
    Возвращает (picture_element, shape_id) или None.
    """
    for pic in slide._element.iter(qn("p:pic")):
        nvPr = pic.find(f"{qn('p:nvPicPr')}/{qn('p:nvPr')}")
        if nvPr is None:
            continue
        if nvPr.find(qn("a:videoFile")) is not None:
            cNvPr = pic.find(f"{qn('p:nvPicPr')}/{qn('p:cNvPr')}")
            if cNvPr is not None:
                return pic, int(cNvPr.attrib["id"])
    return None


def inject_autoplay(slide, duration_ms: int = 8000) -> bool:
    """Заменяет/создаёт <p:timing> в слайде, чтобы видео запускалось автоматически.

    Использует preset class 'mediacall' с командой playFrom(0.0). Этот вариант
    тестирован в PowerPoint 2016+ и LibreOffice Impress 7+.
    """
    found = find_movie_picture(slide)
    if found is None:
        print("    ! Видео-объект не найден")
        return False
    _, sp_id = found

    timing_xml = f"""<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
                <p:par>
                  <p:cTn id="3" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="4" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="5" presetID="1" presetClass="mediacall" presetSubtype="0" fill="hold" nodeType="afterEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:cmd type="call" cmd="playFrom(0.0)">
                                    <p:cBhvr>
                                      <p:cTn id="6" dur="{duration_ms}" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{sp_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                  </p:cmd>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst>
              <p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>
            </p:prevCondLst>
            <p:nextCondLst>
              <p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>
            </p:nextCondLst>
          </p:seq>
          <p:video>
            <p:cMediaNode vol="80000">
              <p:cTn id="7" fill="hold" display="0">
                <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
              </p:cTn>
              <p:tgtEl><p:spTgt spid="{sp_id}"/></p:tgtEl>
            </p:cMediaNode>
          </p:video>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
</p:timing>"""

    # Удаляем существующий timing, если есть
    for old in slide._element.findall(qn("p:timing")):
        slide._element.remove(old)
    new_timing = etree.fromstring(timing_xml)
    slide._element.append(new_timing)
    print(f"    ✓ autoplay XML добавлен (sp_id={sp_id}, dur={duration_ms}ms)")
    return True


def replace_image_with_movie(slide, video_path: Path, poster_path: Path) -> None:
    pics_to_remove = [s for s in slide.shapes if s.shape_type == 13]
    for shape in pics_to_remove:
        sp = shape._element
        sp.getparent().remove(sp)
    slide.shapes.add_movie(
        str(video_path), left=0, top=0,
        width=SLIDE_W, height=SLIDE_H,
        poster_frame_image=str(poster_path),
        mime_type="video/mp4",
    )


def main():
    if not HTML_SRC.exists():
        raise SystemExit(f"HTML не найден: {HTML_SRC}")
    if not PPTX_IN.exists():
        raise SystemExit(f"PPTX не найден: {PPTX_IN}. Сначала запусти html_to_pptx.py")

    VIDEO_DIR.mkdir(exist_ok=True)
    POSTER_DIR.mkdir(exist_ok=True)

    uri = file_uri(HTML_SRC)
    print(f"Открываем {HTML_SRC.name} в Playwright Chromium...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": W, "height": H})
        page = context.new_page()
        page.goto(uri)
        page.wait_for_function("typeof Reveal !== 'undefined' && Reveal.isReady()", timeout=10000)
        # Прячем Reveal.js UI (progress, controls)
        page.add_style_tag(content=INJECT_CSS)
        page.wait_for_timeout(100)
        print("✓ Reveal.js готов, CSS-оверрайд применён")

        for target in TARGETS:
            video = VIDEO_DIR / f"{target['name']}.mp4"
            poster = POSTER_DIR / f"{target['name']}.png"
            print(f"\n=== Слайд {target['idx'] + 1}: {target['label']} ===")
            capture_animation(page, target, video, poster)

        browser.close()

    print(f"\n=== Сборка PPTX с видео + автозапуском ===")
    print(f"Вход: {PPTX_IN.name}")
    shutil.copy2(PPTX_IN, PPTX_OUT)

    prs = Presentation(PPTX_OUT)
    for target in TARGETS:
        slide = prs.slides[target["idx"]]
        video = VIDEO_DIR / f"{target['name']}.mp4"
        poster = POSTER_DIR / f"{target['name']}.png"
        print(f"\n  Слайд {target['idx'] + 1}: встраиваем {video.name}")
        replace_image_with_movie(slide, video, poster)
        inject_autoplay(slide, duration_ms=DURATION_S * 1000)

    prs.save(PPTX_OUT)
    size_mb = PPTX_OUT.stat().st_size / (1024 * 1024)
    print(f"\n✓ Сохранено: {PPTX_OUT}  ({size_mb:.2f} MB)")
    print("  PowerPoint: видео должно запускаться автоматически при показе слайда.")


if __name__ == "__main__":
    main()
