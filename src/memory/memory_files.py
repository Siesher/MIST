"""Per-student file memory store — Claude-memory-tool style (/memory dir).

Layout: <base>/<student_id>/memory/{profile.md, dreams/<ts>.md, state.json}
Pure stdlib; trivially inspectable. Writes are confined to the student's dir.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List

_SAFE = re.compile(r"^[A-Za-z0-9_-]+$")


class StudentMemoryFiles:
    def __init__(self, student_id: str, base_dir: Path | str = "data/students") -> None:
        if not _SAFE.match(student_id):
            raise ValueError(f"unsafe student_id: {student_id!r}")
        self.root = Path(base_dir) / student_id / "memory"
        self.dreams_dir = self.root / "dreams"
        self.dreams_dir.mkdir(parents=True, exist_ok=True)

    # profile.md (durable facts)
    def read_profile(self) -> str:
        p = self.root / "profile.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def write_profile(self, text: str) -> Path:
        p = self.root / "profile.md"
        p.write_text(text, encoding="utf-8")
        return p

    # dreams/<ts>.md (append-only reflections)
    def append_dream(self, markdown: str, *, ts: str | None = None) -> Path:
        stamp = ts or datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        p = self.dreams_dir / f"{stamp}.md"
        p.write_text(markdown, encoding="utf-8")
        return p

    def list_dreams(self) -> List[str]:
        """Newest-first list of dream file names."""
        return sorted((f.name for f in self.dreams_dir.glob("*.md")), reverse=True)

    def read(self, dream_name: str) -> str:
        if not _SAFE.match(dream_name.removesuffix(".md")):
            raise ValueError(f"unsafe dream name: {dream_name!r}")
        p = self.dreams_dir / dream_name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    # state.json (idempotency marker)
    def read_state(self) -> dict:
        p = self.root / "state.json"
        if not p.exists():
            return {"last_dreamed_at": None, "sessions_seen": []}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"last_dreamed_at": None, "sessions_seen": []}

    def write_state(self, state: dict) -> None:
        (self.root / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
