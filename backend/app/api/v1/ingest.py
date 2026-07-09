"""File ingestion endpoints — extract text from PDF/DOCX/images for chat context.

Usage pattern in frontend:
    1. User attaches file in ChatInput
    2. POST /api/v1/ingest/{pdf|docx|image} with multipart/form-data
    3. Get back extracted text (+ preview)
    4. Prepend to next user message OR store in session attachment list

Не делаем полного RAG — этот путь лёгкий и предсказуемый. Для больших
документов есть `/api/v1/knowledge/sources` который запускает полное
извлечение в Knowledge Forge.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json as _json
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.api.v1.auth import get_current_user

logger = logging.getLogger(__name__)

# Загрузка файлов/URL пишет в базу знаний и дёргает vision-LLM —
# весь роутер только для авторизованных.
router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(get_current_user)])


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────


class IngestResponse(BaseModel):
    kind: str  # pdf | docx | image | text
    filename: str
    size_bytes: int
    text: str  # extracted content (may be truncated)
    preview: str  # first ~200 chars
    pages: int | None = None
    metadata: dict[str, Any] = {}
    truncated: bool = False


MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_TEXT_CHARS = 40_000  # cap extracted text to ~10K tokens


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_TEXT_CHARS:
        return text, False
    return text[:MAX_TEXT_CHARS] + "\n…[truncated]…", True


# ─────────────────────────────────────────────────────────────────────
# PDF — pypdf fast path + pdfplumber fallback for complex layouts
# ─────────────────────────────────────────────────────────────────────


@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf(file: UploadFile = File(...)) -> IngestResponse:
    """Extract text from a PDF. Uses pypdf (fast); falls back to pdfplumber."""
    if not file.filename:
        raise HTTPException(400, "filename required")
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, f"file > {MAX_FILE_BYTES // (1024 * 1024)}MB")

    # Primary: pypdf
    pages_text: list[str] = []
    meta: dict[str, Any] = {}
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        for page in reader.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                pages_text.append("")
        if reader.metadata:
            meta = {k: str(v) for k, v in reader.metadata.items() if v is not None}
    except Exception as e:
        logger.warning(f"pypdf failed, trying pdfplumber: {e}")

    # Fallback: pdfplumber (better for tables/complex layouts)
    full_text = "\n\n".join(t.strip() for t in pages_text if t.strip())
    if len(full_text) < 100:
        try:
            import pdfplumber

            pages_text = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for p in pdf.pages:
                    pages_text.append(p.extract_text() or "")
            full_text = "\n\n".join(t.strip() for t in pages_text if t.strip())
        except Exception as e:
            logger.error(f"Both pypdf and pdfplumber failed: {e}")

    # Скан без текстового слоя → vision-OCR через mits-vision (родная мультимодальность).
    if len(full_text) < 100:
        try:
            from src.tools.vision_ocr import ocr_pdf

            ocr_text = ocr_pdf(content)
            if ocr_text:
                full_text = ocr_text
                meta["ocr"] = "mits-vision"
        except Exception as e:
            logger.warning(f"vision OCR PDF fallback failed: {e}")

    text, truncated = _truncate(full_text)
    return IngestResponse(
        kind="pdf",
        filename=file.filename,
        size_bytes=len(content),
        text=text,
        preview=text[:200].strip(),
        pages=len(pages_text),
        metadata=meta,
        truncated=truncated,
    )


# ─────────────────────────────────────────────────────────────────────
# DOCX — python-docx (paragraphs + tables)
# ─────────────────────────────────────────────────────────────────────


@router.post("/docx", response_model=IngestResponse)
async def ingest_docx(file: UploadFile = File(...)) -> IngestResponse:
    """Extract text from Word document (.docx)."""
    if not file.filename:
        raise HTTPException(400, "filename required")
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "only .docx supported (use /ingest/pdf for .pdf)")

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, f"file > {MAX_FILE_BYTES // (1024 * 1024)}MB")

    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(io.BytesIO(content))
        parts: list[str] = []

        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)

        # Tables — join with tabs
        for table in doc.tables:
            for row in table.rows:
                row_text = "\t".join(cell.text.strip() for cell in row.cells)
                if row_text.strip():
                    parts.append(row_text)

        full_text = "\n".join(parts)
    except Exception as e:
        logger.exception("docx extract failed")
        raise HTTPException(500, f"Extraction failed: {e}")

    text, truncated = _truncate(full_text)
    return IngestResponse(
        kind="docx",
        filename=file.filename,
        size_bytes=len(content),
        text=text,
        preview=text[:200].strip(),
        pages=None,
        metadata={
            "paragraphs": len([p for p in doc.paragraphs if p.text.strip()]),
            "tables": len(doc.tables),
        },
        truncated=truncated,
    )


# ─────────────────────────────────────────────────────────────────────
# Image — optional VisionAnalyzer (falls back to base64 + LLM describe)
# ─────────────────────────────────────────────────────────────────────


class ImageAnalyzeRequest(BaseModel):
    context: str = ""  # what to extract/recognize about the image


@router.post("/image", response_model=IngestResponse)
async def ingest_image(
    file: UploadFile = File(...),
    context: str = Form(default=""),
) -> IngestResponse:
    """Describe/recognize content of an uploaded image via vision model.

    For handwritten math specifically, use /api/v1/vision/recognize instead
    (has dedicated math-OCR pipeline with SymPy verification).
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        raise HTTPException(400, f"Unsupported image type: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, f"file > {MAX_FILE_BYTES // (1024 * 1024)}MB")

    # Primary: mits-vision — родная мультимодальность Qwen3.5 через llama-swap
    # (проверенный путь: data-URI image_url + enable_thinking=false).
    description = ""
    metadata: dict[str, Any] = {"content_type": file.content_type}
    try:
        from src.tools.vision_ocr import ocr_image

        description = ocr_image(content, mime=file.content_type or "image/png", prompt=context or None)
        if description:
            metadata["vision_model"] = "mits-vision"
    except Exception as e:
        logger.info(f"mits-vision OCR unavailable ({e}); falling back to LLM describe")

    # Fallback: describe via main LLM (base64) only if vision gave nothing.
    if not description:
        try:
            # Сознательно НЕ create_llm_client: этот fallback шлёт картинку в
            # Ollama-формате (images прямо в message) — OpenAI-совместимый путь
            # его не понимает (там image_url content-parts, см. src/tools/vision_ocr).
            from src.models.llm_client import LLMClient

            b64 = base64.b64encode(content).decode("ascii")
            llm = LLMClient()
            prompt = f"Опиши изображение кратко (5-10 предложений). Контекст: {context or 'общее описание'}"
            response = llm.chat(
                messages=[{"role": "user", "content": prompt, "images": [b64]}],
                temperature=0.3,
            )
            description = response if isinstance(response, str) else str(response)
            metadata["vision_model"] = "llm_fallback"
        except Exception as llm_err:
            logger.warning(f"LLM image describe failed: {llm_err}")
            description = f"[Image {file.filename}, {len(content) // 1024}KB] Vision unavailable."
            metadata["vision_model"] = "unavailable"

    text, truncated = _truncate(description)
    return IngestResponse(
        kind="image",
        filename=file.filename or "image.jpg",
        size_bytes=len(content),
        text=text,
        preview=text[:200].strip(),
        pages=None,
        metadata=metadata,
        truncated=truncated,
    )


# ─────────────────────────────────────────────────────────────────────
# URL — fetch readable text from a web page (reuses web_tools.fetch_url)
# ─────────────────────────────────────────────────────────────────────


class IngestUrlRequest(BaseModel):
    url: str
    summarize: bool = False  # прогнать через SourceAnalyzer и вернуть дайджест в metadata


@router.post("/url", response_model=IngestResponse)
async def ingest_url(req: IngestUrlRequest) -> IngestResponse:
    """Извлечь читаемый текст со страницы по URL (HTML удаляется).

    При summarize=true дополнительно прогоняет текст через SourceAnalyzer и кладёт
    структурированный дайджест (key_points/formulas/topics) в metadata.digest —
    готовый к подмешиванию в контекст тьютора.
    """
    if not (req.url.startswith("http://") or req.url.startswith("https://")):
        raise HTTPException(400, "url должен начинаться с http(s)://")

    # fetch_url синхронный (httpx.get) — уводим в тред, чтобы не блокировать loop.
    def _fetch() -> dict[str, Any]:
        from src.tools.web_tools import fetch_url

        return _json.loads(fetch_url(req.url, max_chars=MAX_TEXT_CHARS))

    try:
        data = await asyncio.to_thread(_fetch)
    except Exception as e:
        raise HTTPException(502, f"Не удалось загрузить URL: {e}")
    if data.get("error"):
        raise HTTPException(502, str(data["error"]))

    full_text = data.get("text", "") or ""
    text, truncated = _truncate(full_text)
    meta: dict[str, Any] = {
        "url": data.get("url", req.url),
        "content_type": data.get("content_type", ""),
    }

    if req.summarize and text.strip():
        try:

            def _summarize() -> dict[str, Any]:
                from src.knowledge.source_analyzer import SourceAnalyzer

                return SourceAnalyzer().summarize(text, source_name=req.url)

            meta["digest"] = await asyncio.to_thread(_summarize)
        except Exception as e:
            logger.warning(f"URL summarize failed: {e}")

    return IngestResponse(
        kind="url",
        filename=req.url,
        size_bytes=len(full_text.encode("utf-8")),
        text=text,
        preview=text[:200].strip(),
        pages=None,
        metadata=meta,
        truncated=truncated,
    )


# ─────────────────────────────────────────────────────────────────────
# Text — plain/markdown/code — no magic, just read bytes
# ─────────────────────────────────────────────────────────────────────


@router.post("/text", response_model=IngestResponse)
async def ingest_text(file: UploadFile = File(...)) -> IngestResponse:
    """Accept plain text / markdown / source code as-is."""
    if not file.filename:
        raise HTTPException(400, "filename required")
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, f"file > {MAX_FILE_BYTES // (1024 * 1024)}MB")

    try:
        full_text = content.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(400, f"Decode failed: {e}")

    text, truncated = _truncate(full_text)
    return IngestResponse(
        kind="text",
        filename=file.filename,
        size_bytes=len(content),
        text=text,
        preview=text[:200].strip(),
        pages=None,
        metadata={"encoding": "utf-8"},
        truncated=truncated,
    )
