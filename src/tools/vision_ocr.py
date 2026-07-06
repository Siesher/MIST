"""Vision-OCR через mits-vision (llama-swap) — родная мультимодальность Qwen3.5.

Рендерим изображение/страницы PDF → OpenAI `image_url` (data-URI) → модель
`mits-vision` с `enable_thinking=false` (иначе reasoning_content съедает бюджет
и content приходит пустым). Тот же путь, что проверен вручную на скан-страницах.
"""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)

VISION_MODEL = "mits-vision"
_OCR_PROMPT = (
    "Распознай и выпиши ВЕСЬ текст с изображения дословно: заголовки, абзацы, "
    "формулы, подписи к таблицам и рисункам. Только текст, без своих комментариев."
)


def _vision_chat_url() -> str:
    """URL chat/completions того же llama-swap, что использует основной клиент.

    LLM_BASE_URL — из src.config (та же .env, что у backend/): src/ не
    импортирует backend/ (направление слоёв).
    """
    from src.config import settings

    return f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"


def ocr_image(image_bytes: bytes, mime: str = "image/png", prompt: str | None = None, timeout: int = 300) -> str:
    """OCR одного изображения через mits-vision. Возвращает распознанный текст."""
    import requests

    b64 = base64.b64encode(image_bytes).decode("ascii")
    body = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt or _OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.1,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    r = requests.post(_vision_chat_url(), json=body, timeout=(30, timeout))
    r.raise_for_status()
    return (r.json()["choices"][0]["message"].get("content") or "").strip()


def ocr_pdf(pdf_bytes: bytes, max_pages: int = 15, dpi: int = 150) -> str:
    """OCR скан-PDF постранично (рендер PyMuPDF → mits-vision). Кап на число страниц."""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_out: list[str] = []
    for i in range(min(doc.page_count, max_pages)):
        try:
            pix = doc[i].get_pixmap(dpi=dpi)
            txt = ocr_image(pix.tobytes("png"))
            if txt:
                pages_out.append(txt)
        except Exception as e:
            logger.warning(f"vision OCR страницы {i + 1} не удался: {e}")
    return "\n\n".join(pages_out)
