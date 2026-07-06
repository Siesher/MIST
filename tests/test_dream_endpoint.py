# tests/test_dream_endpoint.py
from fastapi.testclient import TestClient

from backend.app.api.v1 import dream as dream_module
from backend.app.api.v1.auth import get_current_user
from backend.app.main import app
from src.memory.memory_files import StudentMemoryFiles


def test_dream_memory_requires_auth():
    # Контракт после закрытия dream-эндпоинтов: аноним получает 401 от
    # get_current_user ещё до входа в хендлер. Раньше тут был 200 с пустой
    # памятью — тест закрепляет, что обратно это не откатится молча.
    r = TestClient(app).get("/api/v1/dream/memory")
    assert r.status_code == 401


def test_dream_memory_authorized_reads_own_memory(monkeypatch, tmp_path):
    class _User:
        id = "user-dream-test"

    # dream.py импортирует класс в свой namespace — патчим именно там.
    # base_dir уводим в tmp_path: конструктор StudentMemoryFiles эагерно
    # делает mkdir, иначе тест насорил бы в data/students репозитория.
    monkeypatch.setattr(
        dream_module,
        "StudentMemoryFiles",
        lambda sid: StudentMemoryFiles(sid, base_dir=tmp_path),
    )
    app.dependency_overrides[get_current_user] = lambda: _User()
    try:
        r = TestClient(app).get("/api/v1/dream/memory")
        assert r.status_code == 200
        body = r.json()
        # Свежий пользователь: профиль пуст, снов нет — но форма ответа стабильна.
        assert body["dreams"] == []
        assert body["profile"] == ""
    finally:
        app.dependency_overrides.pop(get_current_user, None)
