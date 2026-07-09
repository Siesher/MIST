# MITS Design Handoff

Пакет дизайнерских файлов для передачи в Claude Design или дизайнеру.

## Структура

Все пути сохранены **относительно корня репозитория** (`C:\Work\MITS\`).
Когда дизайнер вернёт изменения — файлы кладутся обратно по тем же путям.

## Порядок важности

### 1. Сначала смотри эти два файла
Они управляют ~80% визуала:

- `frontend/src/app/globals.css` — **все CSS токены, 4 темы (grimoire/neo/acid/minimal), панели, кнопки, чипы, анимации**
- `frontend/tailwind.config.ts` — маппинг cyber palette в Tailwind utilities

### 2. Layout + темы
- `frontend/src/app/layout.tsx` — шрифты + `<html data-theme>`
- `frontend/src/components/cyber/ThemeProvider.tsx` — переключалка тем

### 3. Cyber-примитивы (атомы)
Директория `frontend/src/components/cyber/` — 9 переиспользуемых компонентов.

### 4. Конкретные страницы
`frontend/src/app/<route>/page.tsx` — один файл на одну страницу.

### 5. Chat UI
`frontend/src/components/chat/*` — всё что внутри `/chat/:id`.

## ⚠️ ВАЖНО для Claude Design

1. **Сохраняй CSS-переменные** (`var(--violet)`, `var(--surface)`, и т.д.) —
   их использует ~40 компонентов через inline styles. Если заменишь на hex —
   сломаешь переключение тем.
2. **Проект использует Tailwind 3.4** + custom cyber palette. Не добавляй
   новые классы без обновления `tailwind.config.ts`.
3. **Шрифты** — `JetBrains Mono` (моноширинный) + `Space Grotesk` (дисплейный).
   Они подключены через `next/font/google` в `layout.tsx`. Не меняй без консультации.
4. **Компоненты используют data-theme attribute** на `<html>`:
   `data-theme="grimoire"` | `"neo"` | `"acid"` | `"minimal"` — темы переопределяют
   CSS-переменные в `globals.css`. Новые темы добавляй туда же.
5. **NextJS App Router 14**: страницы — это `page.tsx` в директориях
   `app/<route>/`. Клиентские компоненты начинаются с `"use client";`.

## Что где рендерится

| Экран | URL | Файл |
|---|---|---|
| Главная | `/` | `app/page.tsx` |
| Логин | `/auth/login` | `app/auth/login/page.tsx` |
| Регистрация | `/auth/register` | `app/auth/register/page.tsx` |
| Чат | `/chat/[id]` | `app/chat/[sessionId]/page.tsx` + `components/chat/*` |
| Граф знаний | `/graph` | `app/graph/page.tsx` |
| Задачник | `/tasks` | `app/tasks/page.tsx` |
| Источники | `/sources` | `app/sources/page.tsx` |
| Профиль | `/profile` | `app/profile/page.tsx` |
| Настройки | `/settings` | `app/settings/page.tsx` |

## Темы (4 варианта)

Переключаются через `/settings`:
- **grimoire** (default) — фиолетово-золотой, с glow/scanlines
- **minimal** — плоский, без эффектов
- **neo** — монохром высококонтрастный
- **acid** — cyberpunk overdrive, яркий неон

Все определены в `globals.css` под `:root[data-theme="..."]`.

## Шрифты

- **Моно** (`var(--font-mono)`): JetBrains Mono — для кода, чипов, статуса
- **Дисплей** (`var(--font-display)`): Space Grotesk — для заголовков
- **Размеры сейчас**: 10-14px для UI, 16-22px для заголовков — может быть
  мелко для 4K/больших мониторов

## Палитра (Grimoire theme)

| Переменная | Hex | Применение |
|---|---|---|
| `--violet` | #a583ff | primary accent, nav active |
| `--violet-bright` | #c4a9ff | hover states |
| `--yellow` | #e8c668 | secondary accent, online dot |
| `--magenta` | #cf7fb8 | glitch before-layer |
| `--cyan` | #8dd4dc | glitch after-layer |
| `--success` | #6fe0a6 | OK states, online |
| `--error` | #e87093 | errors |
| `--bg-0` | #0a0612 | darkest background |
| `--surface` | #120a1f | panel background |

Полный список — см. `globals.css` `:root { ... }` блок.
