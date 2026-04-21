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

import base64
import io
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


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

    # Try VisionAnalyzer (handwritten math pipeline). If not available or
    # fails for generic images, describe via LLM with base64.
    description = ""
    metadata: dict[str, Any] = {"content_type": file.content_type}

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from src.config import settings
        from src.models.vision_analyzer import VisionAnalyzer

        analyzer = VisionAnalyzer(vision_model=getattr(settings, "VISION_MODEL", "qwen2.5vl:7b"))
        result = await analyzer.analyze_image(
            image_path=tmp_path,
            problem=context or "Опиши что на изображении.",
            expected_answer=None,
        )
        steps = []
        for step in result.steps:
            steps.append(f"• {step.recognized_latex}")
        description = (result.feedback or "").strip() + (
            "\n\nРаспознано:\n" + "\n".join(steps) if steps else ""
        )
        metadata["vision_model"] = "active"
    except Exception as e:
        logger.info(f"VisionAnalyzer unavailable ({e}); falling back to LLM describe")
        # Fallback: ask the main LLM to describe via base64
        try:
            from src.models.llm_client import LLMClient

            b64 = base64.b64encode(content).decode("ascii")
            llm = LLMClient()
            # Many Ollama models support images field in messages
            prompt = (
                f"Опиши изображение кратко (5-10 предложений). "
                f"Контекст: {context or 'общее описание'}"
            )
            try:
                response = llm.chat(
                    messages=[{"role": "user", "content": prompt, "images": [b64]}],
                    temperature=0.3,
                )
                description = response if isinstance(response, str) else str(response)
                metadata["vision_model"] = "llm_fallback"
            except Exception as llm_err:
                logger.warning(f"LLM image describe failed: {llm_err}")
                description = (
                    f"[Image {file.filename}, {len(content) // 1024}KB] "
                    "Vision model not available. Upload error-free but no description generated."
                )
                metadata["vision_model"] = "unavailable"
        except Exception:
            description = f"[Image {file.filename}] Analysis failed."
    finally:
        Path(tmp_path).unlink(missing_ok=True)

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
