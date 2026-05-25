import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import assemble_vkr as av


def test_find_pandoc_returns_existing_exe():
    p = av.find_pandoc()
    assert p, "pandoc не найден"
    assert Path(p).exists()
    assert "pandoc" in Path(p).name.lower()
