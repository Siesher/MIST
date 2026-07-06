"""Тесты единой фабрики LLM-клиентов и контракта BaseLLMClient.

До унификации развилка выбора бэкенда была скопирована в двух местах
(orchestrator_service, source_analyzer._make_llm) и местами обходилась
(голый LLMClient() в ingest игнорировал LLM_BACKEND). Теперь развилка одна —
src.models.create_llm_client; тесты пиннят выбор и структурное соответствие
обоих клиентов общему контракту.
"""

import src.models as models_pkg
from src.config import settings
from src.models import BaseLLMClient, LLMClient, OpenAICompatLLMClient, create_llm_client


class _StubOllamaClient:
    """Стаб вместо LLMClient: его конструктор ходит в Ollama за списком моделей."""

    def __init__(self, model=None, **kwargs):
        self.model = model
        self.kwargs = kwargs


def test_both_clients_satisfy_contract_structurally():
    # BaseLLMClient — non-data Protocol, поэтому issubclass работает и не
    # требует инстанцирования (LLMClient.__init__ ходит в сеть — в юнитах нельзя).
    assert issubclass(LLMClient, BaseLLMClient)
    assert issubclass(OpenAICompatLLMClient, BaseLLMClient)


def test_factory_llamacpp_returns_openai_compat_with_overrides():
    client = create_llm_client(backend="llamacpp", model="m", base_url="http://x/v1/", api_key="k")
    assert isinstance(client, OpenAICompatLLMClient)
    assert client.model == "m"
    assert client.base_url == "http://x/v1"  # хвостовой слэш срезан
    assert client.api_key == "k"


def test_factory_ollama_returns_native_client(monkeypatch):
    monkeypatch.setattr(models_pkg, "LLMClient", _StubOllamaClient)
    client = create_llm_client(backend="ollama", model="qwen3.5:9b")
    assert isinstance(client, _StubOllamaClient)
    assert client.model == "qwen3.5:9b"


def test_factory_default_backend_reads_settings(monkeypatch):
    """backend=None → развилка по LLM_BACKEND из src.config (не backend/-конфига)."""
    monkeypatch.setattr(models_pkg, "LLMClient", _StubOllamaClient)

    monkeypatch.setattr(settings, "LLM_BACKEND", "ollama")
    assert isinstance(create_llm_client(), _StubOllamaClient)

    monkeypatch.setattr(settings, "LLM_BACKEND", "llamacpp")
    assert isinstance(create_llm_client(model="m2"), OpenAICompatLLMClient)


def test_openai_client_chat_matches_generate_parsing(monkeypatch):
    """chat() шлёт историю как есть и разбирает ответ тем же путём, что generate()."""
    captured = {}

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ответ"}}]}

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["body"] = json
        return _Resp()

    import src.models.openai_llm_client as mod

    monkeypatch.setattr(mod.requests, "post", _fake_post)
    client = OpenAICompatLLMClient(model="m", base_url="http://x/v1", api_key="")
    history = [{"role": "user", "content": "привет"}]

    assert client.chat(history, temperature=0.3) == "ответ"
    assert captured["body"]["messages"] == history
    assert captured["body"]["temperature"] == 0.3
    assert captured["body"]["stream"] is False
