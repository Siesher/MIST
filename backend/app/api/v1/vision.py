"""Vision API endpoints for handwritten solution recognition."""

import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.api.v1.auth import get_current_user

logger = logging.getLogger(__name__)

# OCR гоняет VLM (дорого) — весь роутер только для авторизованных.
router = APIRouter(prefix="/vision", tags=["vision"], dependencies=[Depends(get_current_user)])


class RecognizeResponse(BaseModel):
    """Response from OCR recognition."""

    steps: list
    raw_latex: str
    confidence: str
    feedback: str


class VerifyRequest(BaseModel):
    """Request to verify a solution."""

    steps_latex: list[str]
    expected_answer: Optional[str] = None


class VerifyResponse(BaseModel):
    """Response from solution verification."""

    is_correct: bool
    first_error_step: Optional[int] = None
    feedback: str
    steps: list


@router.post("/recognize", response_model=RecognizeResponse)
async def recognize_handwritten(
    image: UploadFile = File(...),
    problem: str = Form(default=""),
    expected_answer: str = Form(default=""),
):
    """
    Recognize handwritten mathematical solution from uploaded image.

    Args:
        image: Uploaded image file (JPEG/PNG)
        problem: Optional problem context for better recognition
        expected_answer: Optional expected answer for verification
    """
    # Validate file type
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Поддерживаются только JPEG, PNG и WebP")

    # Save to temp file
    content = await image.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 10MB)")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from src.config import get_settings
        from src.models.vision_analyzer import VisionAnalyzer

        settings = get_settings()
        analyzer = VisionAnalyzer(vision_model=settings.VISION_MODEL)

        result = await analyzer.analyze_image(
            image_path=tmp_path,
            problem=problem,
            expected_answer=expected_answer if expected_answer else None,
        )

        steps_data = []
        raw_parts = []
        for step in result.steps:
            steps_data.append(
                {
                    "step_number": step.step_number,
                    "latex": step.recognized_latex,
                    "confidence": step.confidence.value,
                    "is_correct": step.is_correct,
                    "error": step.error_description,
                }
            )
            raw_parts.append(step.recognized_latex)

        return RecognizeResponse(
            steps=steps_data,
            raw_latex="\n".join(raw_parts),
            confidence=result.overall_confidence.value,
            feedback=result.feedback,
        )

    except Exception as e:
        logger.error(f"Recognition failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка распознавания: {str(e)}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/verify", response_model=VerifyResponse)
async def verify_solution(req: VerifyRequest):
    """
    Verify a mathematical solution using SymPy.

    Args:
        req: Solution steps in LaTeX and optional expected answer
    """
    try:
        from src.models.solution_verifier import verify_solution as do_verify

        result = do_verify(req.steps_latex, req.expected_answer)

        steps_data = []
        for step in result.steps:
            steps_data.append(
                {
                    "step_number": step.step_number,
                    "latex": step.latex,
                    "is_valid": step.is_valid_expr,
                    "is_correct_transition": step.is_correct_transition,
                    "error": step.error_description,
                }
            )

        return VerifyResponse(
            is_correct=result.is_correct,
            first_error_step=result.first_error_step,
            feedback=result.feedback,
            steps=steps_data,
        )

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка проверки: {str(e)}")
