"""Pytest config for E2E tests."""

import pytest

# Без pytest-playwright коллекция этой папки падала бы с ImportError —
# в CI плагин не ставится, e2e скипаются целиком
pytest.importorskip("playwright", reason="e2e требует playwright + pytest-playwright")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests requiring running backend + frontend",
    )


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Default browser context — no cookie persistence between tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 900},
        "locale": "ru-RU",
    }
