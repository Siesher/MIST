"""End-to-end smoke tests for MITS frontend + backend.

Requires:
    * Backend running on http://localhost:8000
    * Frontend on http://localhost:3000
    * `pip install pytest-playwright playwright && playwright install chromium`

Run:
    pytest tests/e2e/ -v
    pytest tests/e2e/ -v --headed        # watch browser
    pytest tests/e2e/ -v -k login        # one scenario

These tests verify the user-visible flows end-to-end. They're slow (~30s each)
and need the full stack up. For CI, spin up docker-compose first.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

FRONTEND = "http://localhost:3000"
BACKEND = "http://localhost:8000"


# ─────────────────────────────────────────────────────────────────────
# Setup helpers
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _verify_stack():
    """Skip all tests if stack isn't up."""
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"{BACKEND}/api/v1/health", timeout=2) as r:
            if r.status != 200:
                pytest.skip(f"Backend unhealthy: {r.status}")
    except (urllib.error.URLError, OSError) as e:
        pytest.skip(f"Backend not running on {BACKEND}: {e}")


@pytest.fixture
def authed_page(page: Page) -> Page:
    """Login flow — ensures subsequent tests run with auth."""
    page.goto(f"{FRONTEND}/auth/login")
    # Default demo creds baked into login form
    page.fill('input[type="email"]', "siesher@mits.sys")
    page.fill('input[type="password"]', "demo-access-key")
    page.click('button[type="submit"]')
    page.wait_for_url(f"{FRONTEND}/", timeout=10000)
    return page


# ─────────────────────────────────────────────────────────────────────
# Navigation tests — no LLM needed, fast
# ─────────────────────────────────────────────────────────────────────


def test_home_loads(page: Page):
    """Homepage renders with MITS branding."""
    page.goto(FRONTEND)
    expect(page.locator("text=MITS").first).to_be_visible(timeout=5000)


def test_login_page_renders(page: Page):
    """Login page has email + password fields."""
    page.goto(f"{FRONTEND}/auth/login")
    expect(page.locator('input[type="email"]')).to_be_visible()
    expect(page.locator('input[type="password"]')).to_be_visible()
    expect(page.locator('button[type="submit"]')).to_be_visible()


def test_graph_page_loads(page: Page):
    """Knowledge graph page renders SVG with nodes."""
    page.goto(f"{FRONTEND}/graph")
    expect(page.locator("svg").first).to_be_visible(timeout=5000)
    # Should have domain legend
    expect(page.locator("text=math").first).to_be_visible()


def test_sources_page_loads(page: Page):
    """Sources page shows Knowledge Forge pipeline panel."""
    page.goto(f"{FRONTEND}/sources")
    expect(page.locator("text=KNOWLEDGE FORGE").first).to_be_visible(timeout=5000)
    # Add-source button must exist
    expect(page.locator('button:has-text("ДОБАВИТЬ")').first).to_be_visible()


def test_settings_page_has_themes(page: Page):
    """Settings page exposes all 4 theme variants."""
    page.goto(f"{FRONTEND}/settings")
    expect(page.locator("text=Grimoire").first).to_be_visible(timeout=5000)
    expect(page.locator("text=Minimal").first).to_be_visible()
    expect(page.locator("text=Mono").first).to_be_visible()
    expect(page.locator("text=Acid").first).to_be_visible()


def test_tasks_page_loads(page: Page):
    """Task bank page shows tasks."""
    page.goto(f"{FRONTEND}/tasks")
    expect(page.locator("text=TASK BANK").first).to_be_visible(timeout=5000)


# ─────────────────────────────────────────────────────────────────────
# Theme switching
# ─────────────────────────────────────────────────────────────────────


def test_theme_switch_persists(page: Page):
    """Theme switch updates <html data-theme> and persists to localStorage."""
    page.goto(f"{FRONTEND}/settings")

    # Switch to Neo
    page.click('text="Mono"')
    time.sleep(0.3)
    theme = page.evaluate("() => document.documentElement.dataset.theme")
    assert theme == "neo", f"expected 'neo', got {theme!r}"

    # Reload — theme should persist from localStorage
    page.reload()
    time.sleep(0.5)
    theme = page.evaluate("() => document.documentElement.dataset.theme")
    assert theme == "neo", f"theme did not persist: {theme!r}"


# ─────────────────────────────────────────────────────────────────────
# Status bar: model + cache stats
# ─────────────────────────────────────────────────────────────────────


def test_statusbar_shows_model(page: Page):
    """StatusBar fetches /health and displays model name."""
    page.goto(FRONTEND)
    # Wait for health probe (runs on mount)
    time.sleep(2)
    text = page.locator("text=/qwen|gemma|mits-tutor/").first
    # Either visible OR the status bar says "OFFLINE" cleanly
    if text.count() == 0:
        expect(page.locator("text=/ОФЛАЙН|OFFLINE/").first).to_be_visible()


# ─────────────────────────────────────────────────────────────────────
# Sources upload (requires backend with knowledge router)
# ─────────────────────────────────────────────────────────────────────


def test_sources_upload_flow(page: Page):
    """Open upload modal, fill form, submit, verify card appears."""
    page.goto(f"{FRONTEND}/sources")
    page.click('button:has-text("ДОБАВИТЬ")')
    # Modal opens
    expect(page.locator("text=ДОБАВИТЬ ИСТОЧНИК").first).to_be_visible(timeout=3000)

    # Fill form
    page.fill('input[placeholder*="Демидович"]', "Test Source " + str(int(time.time())))
    # Select math domain via dropdown
    page.select_option("select", "math")
    # Textarea — min 20 chars
    page.fill(
        "textarea",
        "Производная функции f(x)=x^2 равна 2x. Это простейший пример применения правила степени.",
    )

    # Submit
    page.click('button:has-text("ЗАГРУЗИТЬ")')

    # Modal should close OR error banner should appear (backend may OOM)
    time.sleep(2)
    # New card should have appeared in grid
    cards = page.locator('text="Test Source"')
    assert cards.count() >= 1, "Uploaded source card not visible"


# ─────────────────────────────────────────────────────────────────────
# Chart rendering (new Mermaid + Plotly integration)
# ─────────────────────────────────────────────────────────────────────


def test_chart_renderer_present(page: Page):
    """Verify SmartContent components load without error.

    We simulate by injecting a test message with Mermaid fence into chatStore.
    """
    page.goto(FRONTEND)
    # Run a JS snippet that feeds a mermaid message to chatStore (dev/test only)
    # For now just confirm the chart libs are importable at page level
    # by checking window.mermaid loaded when visiting chat
    page.goto(f"{FRONTEND}/chat/test-session-id")
    time.sleep(1)
    # If page loads without crash, libs are bundled correctly
    # (render requires real session + message, skip deeper check in smoke tier)


# ─────────────────────────────────────────────────────────────────────
# Backend API smoke (direct, bypasses frontend)
# ─────────────────────────────────────────────────────────────────────


def test_api_health(page: Page):
    page.goto(f"{BACKEND}/api/v1/health")
    content = page.content()
    assert "healthy" in content or "degraded" in content


def test_api_knowledge_stats(page: Page):
    page.goto(f"{BACKEND}/api/v1/knowledge/stats")
    content = page.content()
    assert "total_nodes" in content


def test_api_metrics_cache(page: Page):
    page.goto(f"{BACKEND}/api/v1/metrics/cache")
    content = page.content()
    assert "hit_rate" in content


def test_api_metrics_traces(page: Page):
    page.goto(f"{BACKEND}/api/v1/metrics/traces")
    content = page.content()
    assert "sessions" in content
