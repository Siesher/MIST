"""Извлечение готовых источников в markdown (pandoc docx->md) для нарезки в главы.

Usage: uv run python scripts/extract_sources.py
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assemble_vkr import find_pandoc  # noqa: E402

ROOT = Path(__file__).parent.parent
EXTRACTED = ROOT / "docs/diploma/_extracted"
SOURCES = {
    "nir.md": ROOT / "docs/diploma/НИР_Сухацкий_2026_controlled_reasoning.docx",
    "kursovoy.md": ROOT / "docs/diploma/Курсовой_проект_Сухацкий_2026.docx",
}


def main() -> None:
    pandoc = find_pandoc()
    EXTRACTED.mkdir(parents=True, exist_ok=True)
    for out_name, src in SOURCES.items():
        out = EXTRACTED / out_name
        subprocess.run(
            [pandoc, str(src), "-t", "markdown", "--wrap=none", "-o", str(out)],
            check=True,
            capture_output=True,
            text=True,
        )
        n_lines = len(out.read_text(encoding="utf-8").splitlines())
        print(f"[ok] {src.name} -> {out} ({n_lines} строк)")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
