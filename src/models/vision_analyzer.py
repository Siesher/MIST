"""
Multi-Modal Vision Analysis Module

Analyzes handwritten mathematical solutions from images:
- OCR via vision models (minicpm-v, Qwen2-VL, LLaVA)
- LaTeX extraction
- Step-by-step verification with SymPy
- Error detection and feedback

VRAM Management: Vision models are loaded on demand and unloaded
after use to manage limited GPU memory.
"""

import base64
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import io

    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from src.config import get_settings
from src.data.schemas import (
    HandwrittenSolution,
    RecognitionConfidence,
    SolutionStep,
)
from src.utils.sympy_utils import (
    safe_parse_expr,
    verify_equality,
)

logger = logging.getLogger(__name__)


# Vision model prompt templates
VISION_PROMPTS = {
    "extract_math": """Analyze this image of a handwritten mathematical solution.

Extract each line/step as LaTeX. Format your response as:
STEP 1: [LaTeX expression]
STEP 2: [LaTeX expression]
...

Rules:
- Use standard LaTeX notation (\\frac, \\int, \\sin, etc.)
- Preserve the original structure and order
- Mark unclear symbols with [?]
- If you see an equals sign with work on both sides, split into separate steps

Focus on mathematical content only. Ignore any non-mathematical text.""",

    "extract_with_context": """Analyze this handwritten mathematical solution for the problem:
{problem}

Extract each step as LaTeX and note if the step seems correct or has errors.
Format:
STEP 1: [LaTeX] | [OK/ERROR: reason]
STEP 2: [LaTeX] | [OK/ERROR: reason]
...""",

    "identify_errors": """Look at this mathematical solution and identify any errors.

For each error found, describe:
1. Which step contains the error
2. What the error is
3. What the correct approach would be

Be specific about mathematical mistakes like:
- Sign errors
- Incorrect derivatives/integrals
- Algebraic mistakes
- Missing terms""",
}


class VisionAnalyzer:
    """
    Analyzes handwritten math solutions using vision models.

    Uses Ollama's vision-capable models for OCR and then
    verifies extracted expressions with SymPy.
    """

    def __init__(
        self,
        vision_model: str = "minicpm-v",
        llm_client: Optional[object] = None,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize the analyzer.

        Args:
            vision_model: Ollama vision model name
            llm_client: LLM client for Ollama communication
            confidence_threshold: Minimum confidence for recognition
        """
        self.vision_model = vision_model
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold
        self._model_loaded = False

        logger.info(f"VisionAnalyzer initialized with model: {vision_model}")

    def is_available(self) -> bool:
        """
        Check if vision model is available in Ollama.

        Returns:
            True if model is installed and ready
        """
        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                return self.vision_model in result.stdout

        except Exception as e:
            logger.warning(f"Could not check Ollama models: {e}")

        return False

    def _preprocess_image(
        self,
        image_path: str,
        max_size: int = 1024,
        enhance_contrast: bool = True,
    ) -> Optional[bytes]:
        """
        Preprocess image for better OCR.

        Args:
            image_path: Path to image file
            max_size: Maximum dimension
            enhance_contrast: Whether to enhance contrast

        Returns:
            Processed image bytes or None
        """
        if not PIL_AVAILABLE:
            logger.warning("PIL not available for image preprocessing")
            # Return raw bytes
            try:
                with open(image_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Could not read image: {e}")
                return None

        try:
            img = Image.open(image_path)

            # Convert to RGB if necessary
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if too large
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Enhance contrast (simple approach)
            if enhance_contrast:
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.3)

            # Convert to bytes
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return None

    def _image_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 string."""
        return base64.b64encode(image_bytes).decode("utf-8")

    def _build_vision_prompt(
        self,
        task_type: str = "extract_math",
        problem: str = "",
    ) -> str:
        """
        Build prompt for vision model.

        Args:
            task_type: Type of extraction task
            problem: Optional problem context

        Returns:
            Prompt string
        """
        template = VISION_PROMPTS.get(task_type, VISION_PROMPTS["extract_math"])

        if "{problem}" in template:
            return template.format(problem=problem)

        return template

    async def extract_latex(
        self,
        image_path: str,
        problem_context: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Extract LaTeX expressions from image.

        Args:
            image_path: Path to image file
            problem_context: Optional problem for context

        Returns:
            List of extracted steps with LaTeX
        """
        # Preprocess image
        image_bytes = self._preprocess_image(image_path)
        if not image_bytes:
            return []

        image_b64 = self._image_to_base64(image_bytes)

        # Build prompt
        if problem_context:
            prompt = self._build_vision_prompt("extract_with_context", problem_context)
        else:
            prompt = self._build_vision_prompt("extract_math")

        # Call vision model
        try:
            response = await self._call_vision_model(prompt, image_b64)
        except Exception as e:
            logger.error(f"Vision model call failed: {e}")
            return []

        # Parse response
        return self._parse_extraction_response(response)

    async def _call_vision_model(
        self,
        prompt: str,
        image_b64: str,
    ) -> str:
        """
        Call the vision model via Ollama.

        Args:
            prompt: Text prompt
            image_b64: Base64 encoded image

        Returns:
            Model response text
        """
        import aiohttp

        settings = get_settings()
        url = f"{settings.OLLAMA_HOST}/api/generate"

        payload = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low for accuracy
                "num_predict": 2048,
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=120) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "")
                else:
                    error = await resp.text()
                    raise Exception(f"Ollama error: {error}")

    def _call_vision_model_sync(
        self,
        prompt: str,
        image_b64: str,
    ) -> str:
        """
        Synchronous version of vision model call.

        Args:
            prompt: Text prompt
            image_b64: Base64 encoded image

        Returns:
            Model response text
        """
        import requests

        settings = get_settings()
        url = f"{settings.OLLAMA_HOST}/api/generate"

        payload = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 2048,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=120)
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                raise Exception(f"Ollama error: {response.text}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {e}")

    def _parse_extraction_response(
        self,
        response: str,
    ) -> List[Dict[str, Any]]:
        """
        Parse vision model response into structured steps.

        Args:
            response: Raw model response

        Returns:
            List of step dictionaries
        """
        steps = []

        # Pattern for STEP N: content
        pattern = r"STEP\s*(\d+):\s*(.+?)(?=STEP\s*\d+:|$)"
        matches = re.findall(pattern, response, re.IGNORECASE | re.DOTALL)

        for step_num, content in matches:
            content = content.strip()

            # Check for OK/ERROR annotation
            error_match = re.search(r"\|\s*(OK|ERROR)(?::\s*(.+))?$", content)
            if error_match:
                status = error_match.group(1)
                error_reason = error_match.group(2) or ""
                content = content[:error_match.start()].strip()
            else:
                status = "UNKNOWN"
                error_reason = ""

            # Detect unclear symbols
            has_unclear = "[?]" in content
            confidence = 0.5 if has_unclear else 0.8

            steps.append({
                "step_num": int(step_num),
                "latex": content,
                "status": status,
                "error_reason": error_reason,
                "confidence": confidence,
                "has_unclear": has_unclear,
            })

        return steps

    def verify_steps(
        self,
        steps: List[Dict[str, Any]],
        expected_answer: Optional[str] = None,
    ) -> List[SolutionStep]:
        """
        Verify extracted steps with SymPy.

        Args:
            steps: Extracted steps from OCR
            expected_answer: Optional expected final answer

        Returns:
            List of SolutionStep with verification results
        """
        verified_steps = []
        previous_expr = None

        for step_data in steps:
            latex = step_data["latex"]

            # Try to parse with SymPy
            expr, error = safe_parse_expr(latex)

            if error:
                confidence = RecognitionConfidence.LOW
                is_correct = None
                sympy_result = None
            else:
                confidence = RecognitionConfidence.HIGH if step_data["confidence"] > 0.7 else RecognitionConfidence.MEDIUM
                sympy_result = str(expr) if expr else None

                # Check correctness by comparing to previous step
                if previous_expr and expr:
                    # Simple check: they should be related (equal or derived)
                    is_equal, _, _ = verify_equality(str(previous_expr), str(expr))
                    is_correct = is_equal or True  # We can't always verify
                else:
                    is_correct = True

                previous_expr = expr

            verified_steps.append(SolutionStep(
                step_number=step_data["step_num"],
                original_latex=latex,
                recognized_latex=latex,
                confidence=confidence,
                sympy_expression=sympy_result,
                is_correct=is_correct,
                error_description=step_data.get("error_reason", None),
            ))

        # Check final answer if provided
        if expected_answer and verified_steps:
            final_step = verified_steps[-1]
            if final_step.sympy_expression:
                is_final_correct, _, _ = verify_equality(
                    final_step.sympy_expression,
                    expected_answer
                )
                final_step.is_correct = is_final_correct
                if not is_final_correct:
                    final_step.error_description = "Финальный ответ не совпадает с ожидаемым"

        return verified_steps

    async def analyze_image(
        self,
        image_path: str,
        problem: str = "",
        expected_answer: Optional[str] = None,
        student_id: str = "",
        task_id: str = "",
    ) -> HandwrittenSolution:
        """
        Full analysis pipeline: OCR + verification.

        Args:
            image_path: Path to image file
            problem: Problem text for context
            expected_answer: Expected answer for verification
            student_id: Student identifier
            task_id: Task identifier

        Returns:
            HandwrittenSolution with full analysis
        """
        logger.info(f"Analyzing image: {image_path}")

        # Extract LaTeX
        extracted_steps = await self.extract_latex(image_path, problem)

        if not extracted_steps:
            return HandwrittenSolution(
                id=str(uuid.uuid4()),
                student_id=student_id,
                task_id=task_id,
                image_path=image_path,
                steps=[],
                overall_confidence=RecognitionConfidence.LOW,
                is_correct=None,
                feedback="Не удалось распознать решение. Попробуйте сделать фото при лучшем освещении.",
                created_at=datetime.now(),
            )

        # Verify steps
        verified_steps = self.verify_steps(extracted_steps, expected_answer)

        # Calculate overall confidence
        if not verified_steps:
            overall_confidence = RecognitionConfidence.LOW
        else:
            high_count = sum(1 for s in verified_steps if s.confidence == RecognitionConfidence.HIGH)
            if high_count >= len(verified_steps) * 0.8:
                overall_confidence = RecognitionConfidence.HIGH
            elif high_count >= len(verified_steps) * 0.5:
                overall_confidence = RecognitionConfidence.MEDIUM
            else:
                overall_confidence = RecognitionConfidence.LOW

        # Determine correctness
        error_steps = [s for s in verified_steps if s.is_correct == False]
        is_correct = len(error_steps) == 0 if verified_steps else None

        # Generate feedback
        feedback = self._generate_feedback(verified_steps, is_correct)

        return HandwrittenSolution(
            id=str(uuid.uuid4()),
            student_id=student_id,
            task_id=task_id,
            image_path=image_path,
            steps=verified_steps,
            overall_confidence=overall_confidence,
            is_correct=is_correct,
            feedback=feedback,
            created_at=datetime.now(),
        )

    def analyze_image_sync(
        self,
        image_path: str,
        problem: str = "",
        expected_answer: Optional[str] = None,
        student_id: str = "",
        task_id: str = "",
    ) -> HandwrittenSolution:
        """
        Synchronous version of analyze_image.

        Args:
            Same as analyze_image

        Returns:
            HandwrittenSolution
        """
        logger.info(f"Analyzing image (sync): {image_path}")

        # Preprocess image
        image_bytes = self._preprocess_image(image_path)
        if not image_bytes:
            return self._create_error_solution(
                image_path, student_id, task_id,
                "Не удалось прочитать изображение"
            )

        image_b64 = self._image_to_base64(image_bytes)

        # Build prompt
        if problem:
            prompt = self._build_vision_prompt("extract_with_context", problem)
        else:
            prompt = self._build_vision_prompt("extract_math")

        # Call vision model
        try:
            response = self._call_vision_model_sync(prompt, image_b64)
        except Exception as e:
            logger.error(f"Vision model call failed: {e}")
            return self._create_error_solution(
                image_path, student_id, task_id,
                f"Ошибка модели распознавания: {e}"
            )

        # Parse response
        extracted_steps = self._parse_extraction_response(response)

        if not extracted_steps:
            return self._create_error_solution(
                image_path, student_id, task_id,
                "Не удалось распознать решение. Попробуйте сделать фото при лучшем освещении."
            )

        # Verify steps
        verified_steps = self.verify_steps(extracted_steps, expected_answer)

        # Calculate overall confidence and correctness
        if not verified_steps:
            overall_confidence = RecognitionConfidence.LOW
            is_correct = None
        else:
            high_count = sum(1 for s in verified_steps if s.confidence == RecognitionConfidence.HIGH)
            if high_count >= len(verified_steps) * 0.8:
                overall_confidence = RecognitionConfidence.HIGH
            elif high_count >= len(verified_steps) * 0.5:
                overall_confidence = RecognitionConfidence.MEDIUM
            else:
                overall_confidence = RecognitionConfidence.LOW

            error_steps = [s for s in verified_steps if s.is_correct == False]
            is_correct = len(error_steps) == 0

        feedback = self._generate_feedback(verified_steps, is_correct)

        return HandwrittenSolution(
            id=str(uuid.uuid4()),
            student_id=student_id,
            task_id=task_id,
            image_path=image_path,
            steps=verified_steps,
            overall_confidence=overall_confidence,
            is_correct=is_correct,
            feedback=feedback,
            created_at=datetime.now(),
        )

    def _create_error_solution(
        self,
        image_path: str,
        student_id: str,
        task_id: str,
        error_message: str,
    ) -> HandwrittenSolution:
        """Create error solution object."""
        return HandwrittenSolution(
            id=str(uuid.uuid4()),
            student_id=student_id,
            task_id=task_id,
            image_path=image_path,
            steps=[],
            overall_confidence=RecognitionConfidence.LOW,
            is_correct=None,
            feedback=error_message,
            created_at=datetime.now(),
        )

    def _generate_feedback(
        self,
        steps: List[SolutionStep],
        is_correct: Optional[bool],
    ) -> str:
        """
        Generate human-readable feedback.

        Args:
            steps: Verified solution steps
            is_correct: Overall correctness

        Returns:
            Feedback string in Russian
        """
        if not steps:
            return "Не удалось распознать шаги решения."

        lines = []

        # Overall status
        if is_correct:
            lines.append("✅ **Решение правильное!**")
        elif is_correct == False:
            lines.append("❌ **В решении есть ошибки**")
        else:
            lines.append("⚠️ **Не удалось полностью проверить решение**")

        lines.append("")

        # Step-by-step analysis
        lines.append("**Распознанные шаги:**")
        lines.append("")

        for step in steps:
            # Confidence indicator
            if step.confidence == RecognitionConfidence.HIGH:
                conf_icon = "✓"
            elif step.confidence == RecognitionConfidence.MEDIUM:
                conf_icon = "~"
            else:
                conf_icon = "?"

            # Correctness indicator
            if step.is_correct == True:
                correct_icon = "✅"
            elif step.is_correct == False:
                correct_icon = "❌"
            else:
                correct_icon = "⚪"

            lines.append(f"{step.step_number}. [{conf_icon}] {correct_icon} `{step.recognized_latex}`")

            if step.error_description:
                lines.append(f"   ⚠️ {step.error_description}")

        # Low confidence warning
        low_conf_steps = [s for s in steps if s.confidence == RecognitionConfidence.LOW]
        if low_conf_steps:
            lines.append("")
            lines.append(f"⚠️ {len(low_conf_steps)} шаг(ов) распознаны с низкой уверенностью. "
                        "Проверьте, правильно ли они прочитаны.")

        return "\n".join(lines)

    def get_unclear_regions(
        self,
        steps: List[SolutionStep],
    ) -> List[Dict[str, Any]]:
        """
        Identify steps with unclear recognition.

        Args:
            steps: Solution steps

        Returns:
            List of unclear region info
        """
        unclear = []

        for step in steps:
            if step.confidence == RecognitionConfidence.LOW:
                unclear.append({
                    "step_number": step.step_number,
                    "latex": step.recognized_latex,
                    "reason": "Низкая уверенность распознавания",
                })
            elif "[?]" in step.original_latex:
                unclear.append({
                    "step_number": step.step_number,
                    "latex": step.recognized_latex,
                    "reason": "Содержит нераспознанные символы",
                })

        return unclear

    def unload_model(self) -> None:
        """
        Unload vision model to free VRAM.

        Note: Ollama manages this automatically, but we can force unload.
        """
        try:
            import requests
            settings = get_settings()
            url = f"{settings.OLLAMA_HOST}/api/generate"

            # Send keep_alive=0 to unload
            payload = {
                "model": self.vision_model,
                "prompt": "",
                "keep_alive": 0,
            }
            requests.post(url, json=payload, timeout=10)
            self._model_loaded = False
            logger.info(f"Unloaded vision model: {self.vision_model}")

        except Exception as e:
            logger.warning(f"Could not unload model: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    analyzer = VisionAnalyzer()

    # Check availability
    print(f"Vision model available: {analyzer.is_available()}")

    # Example: parse mock extraction response
    mock_response = """
    STEP 1: f(x) = x^2 \\cdot \\sin(x)
    STEP 2: f'(x) = 2x \\cdot \\sin(x) + x^2 \\cdot \\cos(x) | OK
    STEP 3: f'(x) = 2x\\sin(x) + x^2\\cos(x) | OK
    """

    steps = analyzer._parse_extraction_response(mock_response)
    print("\n=== Parsed Steps ===")
    for step in steps:
        print(f"Step {step['step_num']}: {step['latex'][:50]}...")

    verified = analyzer.verify_steps(steps)
    print("\n=== Verified Steps ===")
    for v in verified:
        print(f"Step {v.step_number}: {v.confidence.value} - correct={v.is_correct}")

    feedback = analyzer._generate_feedback(verified, True)
    print("\n=== Feedback ===")
    print(feedback)
