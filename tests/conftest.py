"""Общесьютовая гигиена тестов.

In-memory rate-state (счётчики попыток логина и анонимная LLM-квота) живёт
в модуле auth и разделяется всеми TestClient'ами процесса (у них один
client.host = "testclient"). Без очистки между тестами суита сама выедала бы
квоту и флейкала 429-ми в зависимости от порядка запуска.
"""

import pytest

from backend.app.api.v1 import auth as _auth_module


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    _auth_module._auth_attempts.clear()
    _auth_module._anon_llm_calls.clear()
    yield
