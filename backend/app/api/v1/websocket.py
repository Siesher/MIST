"""WebSocket endpoint for streaming chat."""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.app.models.database import async_session_factory
from backend.app.models.auth import verify_token
from backend.app.services.orchestrator_service import get_orchestrator_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str, token: str = Query(default="")):
    """WebSocket endpoint for streaming chat responses."""
    logger.info(f"WebSocket connection request for session: {session_id}")

    # Optional JWT auth via query param
    user_id = None
    if token:
        payload = verify_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")
            logger.info(f"WebSocket authenticated user: {user_id}")

    service = await get_orchestrator_service()

    # WebSocket can't use Depends(get_db), so we create a session manually
    async with async_session_factory() as db:
        session = await service.get_session(db, session_id)

        if not session:
            logger.warning(f"Session not found: {session_id}")
            await websocket.close(code=1008, reason="Session not found")
            return

        await websocket.accept()
        logger.info(f"WebSocket accepted for session: {session_id}")

        # Send connection ready
        await websocket.send_json({
            "type": "connection_ready",
            "session_id": session_id,
            "session_state": {
                "is_solved": session.is_solved,
                "hints_used": session.hints_used,
                "attempts": session.attempts,
            },
        })
        logger.info(f"Sent connection_ready to session: {session_id}")

        try:
            while True:
                data = await websocket.receive_text()

                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_MESSAGE",
                        "message": "Неверный формат сообщения",
                        "recoverable": True,
                    })
                    continue

                msg_type = msg.get("type")

                if msg_type == "message":
                    content = msg.get("content", "").strip()
                    if not content:
                        await websocket.send_json({
                            "type": "error",
                            "code": "INVALID_MESSAGE",
                            "message": "Пустое сообщение",
                            "recoverable": True,
                        })
                        continue

                    try:
                        token_count = 0
                        async for token_data in service.process_message_stream(db, session_id, content):
                            await websocket.send_json(token_data)
                            token_count += 1
                            if token_count == 1:
                                logger.info(f"First token sent via WebSocket for session: {session_id}")
                            if token_count % 100 == 0:
                                logger.debug(f"Sent {token_count} tokens via WebSocket")
                        logger.info(f"Streaming complete: {token_count} tokens sent for session: {session_id}")
                    except Exception as e:
                        logger.error(f"Streaming error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "code": "INTERNAL_ERROR",
                            "message": "Ошибка генерации ответа",
                            "recoverable": True,
                            "retry_after": 5,
                        })

                elif msg_type == "mode_change":
                    new_mode = msg.get("mode", "").strip()
                    if new_mode not in ("chat", "guided_learning", "task_generator"):
                        await websocket.send_json({
                            "type": "error",
                            "code": "INVALID_MODE",
                            "message": f"Неизвестный режим: {new_mode}",
                            "recoverable": True,
                        })
                        continue

                    result = await service.change_mode(db, session_id, new_mode)
                    if result:
                        from backend.app.services.orchestrator_service import MODE_CONFIGS
                        config = MODE_CONFIGS.get(new_mode)
                        await websocket.send_json({
                            "type": "mode_changed",
                            "previous_mode": result["previous_mode"],
                            "current_mode": result["current_mode"],
                            "placeholder": config.placeholder_text if config else "",
                            "message": result.get("message", ""),
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "code": "SESSION_NOT_FOUND",
                            "message": "Сессия не найдена",
                            "recoverable": False,
                        })

                elif msg_type == "hint_request":
                    result = await service.get_hint(db, session_id)
                    if result:
                        await websocket.send_json({
                            "type": "hint_response",
                            **result,
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "code": "NO_HINTS_REMAINING",
                            "message": "Все подсказки использованы",
                            "recoverable": False,
                        })

                elif msg_type == "image_upload":
                    image_b64 = msg.get("image", "")
                    problem = msg.get("problem", "")
                    if not image_b64:
                        await websocket.send_json({
                            "type": "error",
                            "code": "INVALID_MESSAGE",
                            "message": "Изображение не предоставлено",
                            "recoverable": True,
                        })
                        continue

                    try:
                        import base64
                        import tempfile
                        from pathlib import Path as FSPath
                        from src.models.vision_analyzer import VisionAnalyzer
                        from src.config import get_settings

                        settings = get_settings()
                        image_bytes = base64.b64decode(image_b64)

                        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                            tmp.write(image_bytes)
                            tmp_path = tmp.name

                        analyzer = VisionAnalyzer(vision_model=settings.VISION_MODEL)
                        result = await analyzer.analyze_image(
                            image_path=tmp_path,
                            problem=problem,
                        )
                        FSPath(tmp_path).unlink(missing_ok=True)

                        steps_data = []
                        for step in result.steps:
                            steps_data.append({
                                "step_number": step.step_number,
                                "latex": step.recognized_latex,
                                "confidence": step.confidence.value,
                                "is_correct": step.is_correct,
                            })

                        await websocket.send_json({
                            "type": "ocr_result",
                            "steps": steps_data,
                            "feedback": result.feedback,
                            "confidence": result.overall_confidence.value,
                            "is_correct": result.is_correct,
                        })
                    except Exception as e:
                        logger.error(f"Image recognition error: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "code": "OCR_FAILED",
                            "message": f"Ошибка распознавания: {str(e)}",
                            "recoverable": True,
                        })

                elif msg_type in ("typing_start", "typing_stop"):
                    pass  # Analytics only, no response needed

                else:
                    await websocket.send_json({
                        "type": "error",
                        "code": "INVALID_MESSAGE",
                        "message": f"Неизвестный тип сообщения: {msg_type}",
                        "recoverable": True,
                    })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {session_id}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            try:
                await websocket.close(code=1011)
            except Exception:
                pass
