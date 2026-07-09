"""Регрессия: GET /api/v1/sessions не должен раскрывать чужие session UUID.

Фикс 2026-07-05 (анонимный enumeration-блокер): раньше anonymous-ветка отдавала
UUID ВСЕХ бесхозных сессий (user_id IS NULL) любому анониму, а
ensure_session_access пускает в бесхозную сессию по знанию UUID —
т.е. листинг был готовым списком чужих сессий для чтения.

Теперь инвариант двойной:
- аноним получает пустой список, причём сервис/БД вообще не опрашиваются
  (утечка невозможна по построению);
- авторизованный получает выборку, скоупленную строго его user_id.

Тесты стабовые (без LLM/БД-фикстур) — проверяем контракт эндпоинта,
а не оркестратор.
"""

from fastapi.testclient import TestClient

import backend.app.api.v1.sessions as sessions_module
from backend.app.api.v1.auth import get_optional_user
from backend.app.main import app


class _RecordingService:
    """Стаб оркестратора: фиксирует, с каким user_id пришли за списком."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def list_sessions(self, db, page: int, limit: int, status: str | None, user_id: str | None) -> dict:
        self.calls.append({"user_id": user_id, "page": page, "limit": limit, "status": status})
        return {"sessions": [], "total": 0, "page": page, "pages": 0}


def _install_service(monkeypatch) -> _RecordingService:
    service = _RecordingService()

    async def _fake_get_service() -> _RecordingService:
        return service

    # sessions.py импортирует функцию в свой namespace — патчим именно там.
    monkeypatch.setattr(sessions_module, "get_orchestrator_service", _fake_get_service)
    return service


def test_anonymous_listing_is_empty_and_never_queries_service(monkeypatch):
    service = _install_service(monkeypatch)
    app.dependency_overrides[get_optional_user] = lambda: None
    try:
        r = TestClient(app).get("/api/v1/sessions")
        assert r.status_code == 200
        body = r.json()
        assert body["sessions"] == []
        assert body["total"] == 0
        # Ключевая гарантия фикса: аноним не доходит до выборки сессий —
        # значит, чужие анонимные UUID не могут утечь ни при каком содержимом БД.
        assert service.calls == []
    finally:
        app.dependency_overrides.pop(get_optional_user, None)


def test_authorized_listing_is_scoped_to_caller(monkeypatch):
    service = _install_service(monkeypatch)

    class _User:
        id = "user-42"

    app.dependency_overrides[get_optional_user] = lambda: _User()
    try:
        r = TestClient(app).get("/api/v1/sessions")
        assert r.status_code == 200
        # Выборка обязана быть скоуплена вызывающим, не «все сессии» (user_id=None).
        assert [c["user_id"] for c in service.calls] == ["user-42"]
    finally:
        app.dependency_overrides.pop(get_optional_user, None)
