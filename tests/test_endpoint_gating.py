"""Регрессия: гейтинг дорогих и чувствительных эндпоинтов (2026-07-05).

До фикса /experiments, /vision, /ingest, /metrics/traces были доступны без
авторизации, /dream писал в общую память "student_default" от анонима, а все
LLM-пути (chat, tasks/generate, создание сессии, WS) позволяли анонимно
выжигать GPU-время без ограничений.

Три слоя защиты:
- жёсткий гейт (401 анониму): /experiments, /vision, /ingest, /dream,
  /metrics/traces*;
- REQUIRE_AUTH=True (публичный инстанс) переводит LLM-пути в 401 для анонимов;
- при REQUIRE_AUTH=False аноним живёт под per-IP квотой
  ANON_LLM_LIMIT/ANON_LLM_WINDOW (429 при исчерпании).

Тесты стабовые (без LLM/БД-фикстур): проверяем контракт зависимостей,
а не оркестратор.
"""

import pytest
from fastapi.testclient import TestClient

import backend.app.api.v1.tasks as tasks_module
from backend.app.api.v1 import auth as auth_module
from backend.app.api.v1.auth import get_optional_user
from backend.app.config import backend_settings
from backend.app.main import app


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.pop(get_optional_user, None)


class _User:
    id = "user-42"


class _StubOrchestrator:
    """Стаб для /tasks/generate: разрешённые вызовы не должны требовать LLM."""

    async def generate_task(self, topic, difficulty, avoid_recent):
        return {
            "id": "t-1",
            "topic": topic,
            "difficulty": difficulty,
            "problem": "2 + 2 = ?",
            "hints": [],
            "skills": [],
        }


def _install_task_stub(monkeypatch):
    stub = _StubOrchestrator()

    async def _fake_get_service():
        return stub

    # tasks.py импортирует функцию в свой namespace — патчим именно там.
    monkeypatch.setattr(tasks_module, "get_orchestrator_service", _fake_get_service)


_GENERATE_BODY = {"topic": "algebra", "difficulty": "medium"}


# ── Слой 1: жёсткий гейт ────────────────────────────────────


@pytest.mark.parametrize(
    "prefix",
    ["/api/v1/experiments", "/api/v1/vision", "/api/v1/ingest", "/api/v1/dream"],
)
def test_hard_gated_prefixes_reject_anonymous(prefix):
    """Свип ВСЕХ роутов под префиксом: новый незащищённый эндпоинт провалит тест."""
    client = TestClient(app)
    routes = [r for r in app.routes if getattr(r, "path", "").startswith(prefix) and hasattr(r, "methods")]
    assert routes, f"под {prefix} нет роутов — префикс переехал?"
    for route in routes:
        path = route.path
        for param in getattr(route, "param_convertors", {}):
            path = path.replace("{" + param + "}", "x")
        for method in route.methods - {"HEAD", "OPTIONS"}:
            r = client.request(method, path)
            assert r.status_code == 401, f"{method} {path} -> {r.status_code}, ожидали 401 анониму"


def test_traces_require_auth_but_snapshot_stays_public():
    client = TestClient(app)
    # Трейсы содержат тексты диалогов — только для авторизованных.
    assert client.get("/api/v1/metrics/traces").status_code == 401
    assert client.get("/api/v1/metrics/traces/some-session").status_code == 401
    # Агрегированный снапшот (латентность/кэш) — дешёвая observability, без секретов.
    assert client.get("/api/v1/metrics").status_code == 200


# ── Слой 2: REQUIRE_AUTH (публичный инстанс) ────────────────


def test_require_auth_blocks_anonymous_llm_paths(monkeypatch):
    monkeypatch.setattr(backend_settings, "REQUIRE_AUTH", True)
    client = TestClient(app)
    assert client.post("/api/v1/tasks/generate", json=_GENERATE_BODY).status_code == 401
    assert client.post("/api/v1/chat/some-session/message", json={"content": "hi"}).status_code == 401
    assert client.post("/api/v1/sessions", json={}).status_code == 401


def test_require_auth_passes_authenticated_users(monkeypatch):
    monkeypatch.setattr(backend_settings, "REQUIRE_AUTH", True)
    _install_task_stub(monkeypatch)
    app.dependency_overrides[get_optional_user] = lambda: _User()
    r = TestClient(app).post("/api/v1/tasks/generate", json=_GENERATE_BODY)
    assert r.status_code == 200
    assert r.json()["problem"] == "2 + 2 = ?"


# ── Слой 3: анонимная per-IP квота ──────────────────────────


def test_quota_counts_per_ip(monkeypatch):
    monkeypatch.setattr(backend_settings, "ANON_LLM_LIMIT", 2)
    assert auth_module.check_anon_llm_quota("1.2.3.4")
    assert auth_module.check_anon_llm_quota("1.2.3.4")
    assert not auth_module.check_anon_llm_quota("1.2.3.4")
    # Другой IP — независимый бюджет.
    assert auth_module.check_anon_llm_quota("5.6.7.8")


def test_quota_window_slides(monkeypatch):
    fake = {"now": 1000.0}
    monkeypatch.setattr(auth_module.time, "monotonic", lambda: fake["now"])
    monkeypatch.setattr(backend_settings, "ANON_LLM_LIMIT", 1)
    monkeypatch.setattr(backend_settings, "ANON_LLM_WINDOW", 10.0)
    assert auth_module.check_anon_llm_quota("ip")
    assert not auth_module.check_anon_llm_quota("ip")
    fake["now"] += 11.0  # окно проехало — бюджет восстановился
    assert auth_module.check_anon_llm_quota("ip")


def test_anon_quota_exhaustion_returns_429(monkeypatch):
    monkeypatch.setattr(backend_settings, "ANON_LLM_LIMIT", 0)
    r = TestClient(app).post("/api/v1/tasks/generate", json=_GENERATE_BODY)
    assert r.status_code == 429


def test_authenticated_users_bypass_quota(monkeypatch):
    monkeypatch.setattr(backend_settings, "ANON_LLM_LIMIT", 0)
    _install_task_stub(monkeypatch)
    app.dependency_overrides[get_optional_user] = lambda: _User()
    r = TestClient(app).post("/api/v1/tasks/generate", json=_GENERATE_BODY)
    assert r.status_code == 200
