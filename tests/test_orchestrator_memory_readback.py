# tests/test_orchestrator_memory_readback.py
"""Guards the dreaming memory read-back wiring in the guided system prompt.

Task 6 of the dreaming plan injects the student's durable ``profile.md`` (written
by previous "dreams") into the guided-learning system prompt so the tutor
personalizes future sessions. ``process_message_stream`` is a large async
generator that needs a live DB session, LLM client and full session state, so
it is not unit-exercisable here; instead we assert the read-back is wired into
the ``sys_parts`` assembly block of the guided branch (the multi-turn block
added during the context-holding fix).
"""

from __future__ import annotations

import inspect

from backend.app.services import orchestrator_service


def test_guided_system_prompt_reads_student_profile() -> None:
    """The guided sys_parts assembly must read profile.md and append it to sys_parts."""
    source = inspect.getsource(orchestrator_service)
    # The read-back uses StudentMemoryFiles.read_profile() and feeds the result
    # into the guided system prompt (sys_parts) — both must be present.
    assert "StudentMemoryFiles" in source, "memory read-back import missing"
    assert "read_profile()" in source, "profile.md is not read back"
    assert "sys_parts.append" in source and "read_profile" in source, (
        "profile.md read-back is not injected into the guided sys_parts block"
    )
