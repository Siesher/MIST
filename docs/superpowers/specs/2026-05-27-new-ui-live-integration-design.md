# Дизайн: live-интеграция нового дизайна (new-ui) с backend через llama-server

- **Дата:** 2026-05-27
- **Автор:** Сухацкий М. (+ Claude)
- **Статус:** утверждён к реализации (брейншторминг пройден)
- **Контекст:** подготовка к защите ВКР; нужно «реально работающее» приложение с новым дизайном, доступное с любого устройства по Wi-Fi.

## 1. Цель

Сделать так, чтобы **новый дизайн (`docs/design/new-ui`, тема midnight) работал как настоящий сайт**: все 7 экранов (chat, tasks, graph, dashboard, profile, sources, settings) + auth, с живыми данными из backend, модель — через **llama-server**.

## 2. Ключевой вывод разведки

`frontend/` (Next.js 14) **уже содержит все 7 экранов как роуты и уже подключён к backend** (REST + WS + JWT + Zustand). Текущий вид — «cyber»-тема (`components/cyber/*`).

➡️ Поэтому выбран **Approach A**, и он сводится к **«переодеванию уже подключённых экранов»**, а не к постройке с нуля. Data-слой переиспользуется; меняется презентация + один backend-узел (llama-server).

Отвергнутый вариант B (прикрутить данные к Babel-прототипу new-ui) — быстрее к чату, но дублирует проверенный data-слой и не даёт продакшн-результата.

## 3. Архитектура: что меняем / что переиспользуем

| Слой | Действие |
|------|----------|
| Роутинг, `lib/api.ts`, `hooks/useChat`, `useWebSocket`, `store/chatStore`, JWT-auth | ♻️ **Без изменений** |
| Дизайн-токены (тема midnight: цвета, Geist, карточки) | 🎨 Перенести из `new-ui/styles.css` → `frontend` globals + Tailwind |
| Шелл `cyber/AppShell` + `Sidebar` + `StatusBar` | 🎨 Заменить на шелл new-ui (`NavRail` + `Sidebar`) |
| Компоненты экранов (`components/{chat,analytics,...}`) | 🎨 Рестайл под new-ui, логика/пропсы сохраняются |
| `src/models/llm_client.py` (сейчас `ollama`-only) | 🔌 Добавить `LLM_BACKEND=ollama\|llamacpp`; OpenAI-совместимый путь на `http://127.0.0.1:8081/v1` |
| `backend/app/config.py` CORS, hosts | 🌐 `CORS_ORIGINS += LAN-origin`; запуск на `0.0.0.0` |

## 4. Маппинг экран → роут → endpoints (всё уже существует в backend)

| Экран new-ui | Роут frontend | Backend endpoints |
|---|---|---|
| chat | `app/chat/[sessionId]` | WS `/ws/{session_id}`; `POST /chat/{id}/message,/hint,/solution`; `sessions` CRUD; `vision/recognize,/verify` |
| tasks | `app/tasks` | `GET /tasks/topics`, `POST /tasks/generate`, `GET /tasks/recommended` |
| graph | `app/graph` | `GET /knowledge/stats,/nodes,/nodes/{id}`, evolution, proposals |
| dashboard | `app/dashboard` | `GET /analytics/{metrics,activity,performance,mastery,errors,recommendations}`; `export/report.pdf` |
| profile | `app/profile` | `GET /students/me/{profile,analytics,knowledge}` |
| sources | `app/sources` | `GET/POST /knowledge/sources`, `POST /ingest/{pdf,docx,image,text}` |
| settings | `app/settings` | client-side (тема/язык) + `GET /auth/me` |
| auth | `app/auth/{login,register}` | `POST /auth/{login,register,refresh}`, `GET /auth/me` |

## 5. Сеть / запуск (доступ с любого устройства)

- **llama-server**: `C:/OpenCode/llama-server` с GGUF тьютора, OpenAI-совместимый `/v1` на `127.0.0.1:8081` (turbo3-стек — см. reference в памяти проекта).
- **backend**: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`; `LLM_BACKEND=llamacpp`, `LLM_BASE_URL=http://127.0.0.1:8081/v1`.
- **frontend**: `next dev -H 0.0.0.0 -p 3000` (или `build && start`); `NEXT_PUBLIC_API_URL=http://192.168.8.167:8000`.
- **CORS**: добавить `http://192.168.8.167:3000`.
- **Устройства**: открывают `http://192.168.8.167:3000`.
- **Firewall**: разрешить входящие на 3000 и 8000 (Private network).

## 6. Фазы (самое рисковое и самое эффектное — раньше)

- **Ф0 — Поднять стек как есть (de-risk инфраструктуры).** llama-server + backend + frontend end-to-end на текущем дизайне; подтвердить живой чат.
- **Ф1 — Backend → llama-server.** OpenAI-совместимый путь + стриминг чата; затем проверить guided-режим (tool/JSON у 4 агентов — главный риск).
- **Ф2 — Глобальная тема.** Шелл + токены midnight → визуальный скачок на всех экранах сразу.
- **Ф3 — Рестайл по экранам.** Порядок: chat → graph → dashboard → tasks → sources → profile → settings.
- **Ф4 — LAN + demo-логин + проверка с устройства.**

Каждая фаза самодостаточна: если время кончится после Ф2, уже есть рабочий сайт в новом виде (чат живой).

## 7. Риски и подстраховки

- **llama-server для guided-режима** (tool-calling/JSON у агентов) — API llama.cpp ≠ Ollama. *Подстраховка:* чат-режим (прямой тьютор) заведётся гарантированно; guided — если tools заработают (`--jinja` + tool-template) или остаётся за рамками демо.
- **Объём рестайла 7 экранов** — ограничить темой **midnight** (остальные 3 темы new-ui — вне scope). 
- **Параллельный запуск трёх процессов** — задокументировать команды/порядок старта в quickstart.

## 8. Проверка (на каждой фазе)

- Прогон экрана через Playwright (скриншот, визуальная проверка раскладки).
- Smoke живого чата: отправить мат. вопрос → увидеть стриминговый сократический ответ.
- Финал: открыть с другого устройства по LAN, пройти все экраны.

## 9. Вне scope (YAGNI)

- Темы daylight/aurora/grimoire (только midnight).
- Продакшн-деплой, HTTPS, домен (только LAN-демо).
- `DesignCanvas`-обёртка прототипа (артборды не нужны).
- Изменения backend сверх LLM-switch + CORS + bind.
- Замена `frontend/` мокапом (категорически нет — переодеваем, не сносим).

## 10. Критерий готовности (demo-ready)

Сайт открывается с телефона/ноутбука по `http://192.168.8.167:3000`, выглядит как тема midnight new-ui, чат отвечает вживую через llama-server, read-экраны (graph/dashboard/tasks/profile) показывают реальные данные backend.
