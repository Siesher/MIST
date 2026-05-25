"""Сборка ВКР: skeleton (python-docx) + главы (pandoc md->docx с OMML) -> merge.

Usage: uv run python scripts/assemble_vkr.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHAPTERS = ROOT / "docs/diploma/chapters"


def find_pandoc() -> str:
    """Локатор pandoc: PATH -> %LOCALAPPDATA%\\Pandoc -> Program Files."""
    found = shutil.which("pandoc")
    if found:
        return found
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Pandoc" / "pandoc.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Pandoc" / "pandoc.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    raise RuntimeError("pandoc не найден (PATH/LOCALAPPDATA/ProgramFiles)")
