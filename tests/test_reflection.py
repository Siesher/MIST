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


def test_reflection_consolidates_profile_not_append(tmp_path):
    """profile.md is OVERWRITTEN with the consolidated version, not stacked.

    Each dream is handed the existing profile and returns the full merged profile,
    so repeated passes must not accumulate duplicate paragraphs (the bug we fix).
    Dreams themselves remain an append-only journal.
    """
    mem = StudentMemoryFiles("carol", base_dir=tmp_path)

    ReflectionGenerator(
        llm=_FakeLLM({"reflection_md": "## сон 1", "profile_md": "ПРОФИЛЬ ВЕРСИЯ A"}),
        memory=mem,
    ).reflect(_digest())

    ReflectionGenerator(
        llm=_FakeLLM(
            {"reflection_md": "## сон 2", "profile_md": "ПРОФИЛЬ ВЕРСИЯ B (консолидировано)"}
        ),
        memory=mem,
    ).reflect(_digest())

    prof = mem.read_profile()
    assert prof == "ПРОФИЛЬ ВЕРСИЯ B (консолидировано)"  # overwrite, not stacked
    assert "ВЕРСИЯ A" not in prof
    assert len(mem.list_dreams()) == 2  # but both dreams are kept (append-only)


def test_reflection_includes_mastery_block():
    """When mastery is supplied, it is rendered into the prompt the LLM receives."""
    import json as _json

    captured = {}

    class _CapturingLLM:
        def generate(self, prompt, system=None, **kw):
            captured["prompt"] = prompt
            return _json.dumps({"reflection_md": "ok", "profile_md": "p"})

    from src.memory.memory_files import StudentMemoryFiles

    def _mk(tmp):
        return StudentMemoryFiles("masterystud", base_dir=tmp)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        mem = _mk(tmp)
        gen = ReflectionGenerator(llm=_CapturingLLM(), memory=mem)
        gen.reflect(_digest(), mastery=[{"topic": "derivatives", "p_known": 0.42, "attempts": 7}])
    assert "Текущее мастерство" in captured["prompt"]
    assert "derivatives" in captured["prompt"]
    assert "0.42" in captured["prompt"]
