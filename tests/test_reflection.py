import json

from src.agents.reflection import ReflectionGenerator, SessionDigest
from src.memory.memory_files import StudentMemoryFiles


class _FakeLLM:
    def __init__(self, payload: dict):
        self._payload = payload
        self.calls = 0

    def generate(self, prompt, system=None, **kw):
        self.calls += 1
        return json.dumps(self._payload, ensure_ascii=False)


def _digest():
    return [
        SessionDigest(topic="integrals", solved=True, hints=1, errors=["знак подстановки"], turns=6)
    ]


def test_reflection_writes_files(tmp_path):
    mem = StudentMemoryFiles("alice", base_dir=tmp_path)
    llm = _FakeLLM(
        {
            "reflection_md": "## Интегралы\nХорошо справился с подстановкой.",
            "profile_update_md": "Уверенно: интегралы (подстановка).",
            "misconceptions": ["путает знак при подстановке"],
            "next_focus": ["интегрирование по частям"],
        }
    )
    gen = ReflectionGenerator(llm=llm, memory=mem)
    result = gen.reflect(_digest())
    assert llm.calls == 1
    assert mem.list_dreams()  # a dream file was written
    assert "подстановкой" in mem.read(mem.list_dreams()[0])
    assert "интегралы" in mem.read_profile().lower()
    assert result.misconceptions == ["путает знак при подстановке"]


def test_reflection_llm_failure_fallback(tmp_path):
    mem = StudentMemoryFiles("bob", base_dir=tmp_path)

    class _Boom:
        def generate(self, *a, **k):
            raise RuntimeError("llm down")

    gen = ReflectionGenerator(llm=_Boom(), memory=mem)
    result = gen.reflect(_digest())
    assert mem.list_dreams()  # fallback still wrote a dream
    assert result.misconceptions == []  # graceful empty
