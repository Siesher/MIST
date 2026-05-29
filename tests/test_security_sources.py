"""Тесты безопасности: SSRF-фильтр URL + владение источниками (anti-IDOR)."""

from __future__ import annotations

from backend.app.api.v1.knowledge import _owns
from src.tools.web_tools import is_public_url


class _Row:
    def __init__(self, user_id):
        self.user_id = user_id


class _User:
    def __init__(self, uid):
        self.id = uid


def test_is_public_url_blocks_private_and_localhost():
    for u in [
        "http://localhost:8090",
        "http://127.0.0.1",
        "http://10.0.0.5",
        "http://192.168.1.1",
        "http://169.254.1.1",
        "http://[::1]",
    ]:
        assert is_public_url(u) is False, u


def test_is_public_url_allows_public_ip():
    assert is_public_url("http://8.8.8.8") is True
    assert is_public_url("https://1.1.1.1") is True


def test_is_public_url_empty_or_no_host():
    assert is_public_url("") is False
    assert is_public_url("notaurl") is False


def test_owns_public_source_accessible_to_anyone():
    assert _owns(_Row(None), None) is True
    assert _owns(_Row(None), _User("u1")) is True


def test_owns_private_source_only_owner():
    assert _owns(_Row("u1"), _User("u1")) is True
    assert _owns(_Row("u1"), _User("u2")) is False
    assert _owns(_Row("u1"), None) is False
