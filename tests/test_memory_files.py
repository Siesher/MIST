import pytest

from src.memory.memory_files import StudentMemoryFiles


def test_append_dream_and_read(tmp_path):
    mem = StudentMemoryFiles("alice", base_dir=tmp_path)
    path = mem.append_dream("# Сон 1\nПрогресс по интегралам.")
    assert path.exists()
    dreams = mem.list_dreams()
    assert len(dreams) == 1
    assert "интегралам" in mem.read(dreams[0])


def test_profile_write_and_read(tmp_path):
    mem = StudentMemoryFiles("bob", base_dir=tmp_path)
    assert mem.read_profile() == ""  # empty before first dream
    mem.write_profile("Силён в алгебре. Путает производную и дифференциал.")
    assert "алгебре" in mem.read_profile()


def test_path_traversal_rejected(tmp_path):
    with pytest.raises(ValueError):
        StudentMemoryFiles("../../etc", base_dir=tmp_path)
