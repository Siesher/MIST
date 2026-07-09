# MITS E2E Tests

End-to-end smoke tests using Playwright. Verifies full-stack flows:
frontend → backend API → database.

## Setup (one-time)

```powershell
# In the MITS venv
pip install pytest-playwright playwright
playwright install chromium
```

## Run

Prerequisite: backend + frontend running.

```powershell
# Terminal 1
python -m uvicorn backend.app.main:app --port 8000

# Terminal 2
cd frontend; npm run dev

# Terminal 3
pytest tests/e2e/ -v
pytest tests/e2e/ -v --headed          # watch browser
pytest tests/e2e/ -v -k theme_switch   # one test
pytest tests/e2e/ -v --slowmo=500      # slow down for debugging
```

## What's covered

| Test | Verifies |
|---|---|
| `test_home_loads` | Homepage renders with MITS branding |
| `test_login_page_renders` | Login form fields visible |
| `test_graph_page_loads` | Knowledge graph SVG + domain legend |
| `test_sources_page_loads` | Knowledge Forge pipeline panel |
| `test_settings_page_has_themes` | All 4 theme cards present |
| `test_tasks_page_loads` | Task bank header |
| `test_theme_switch_persists` | Theme change + localStorage persistence |
| `test_statusbar_shows_model` | Model name from /health fetched |
| `test_sources_upload_flow` | Full upload modal → submit → card appears |
| `test_chart_renderer_present` | SmartContent bundles load without crash |
| `test_api_health` | `/api/v1/health` returns status |
| `test_api_knowledge_stats` | `/api/v1/knowledge/stats` returns JSON |
| `test_api_metrics_cache` | `/api/v1/metrics/cache` returns hit_rate |
| `test_api_metrics_traces` | `/api/v1/metrics/traces` returns sessions list |

If `_verify_stack` fixture fails (backend unreachable), **all tests skip**
cleanly instead of erroring.

## Notes

- Tests don't create sessions that call the LLM — that's slow (~30s each)
  and adds flakiness. Keep LLM-dependent flows in manual smoke.
- Browser context: 1440×900, Russian locale (for GOST-style UI).
- `authed_page` fixture is available for tests needing login;
  currently unused in smoke tier.
