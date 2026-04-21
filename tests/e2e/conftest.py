"""Pytest config for E2E tests."""

import pytest


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
