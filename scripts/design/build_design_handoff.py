"""Build design handoff package — copies all design-relevant files with preserved
directory structure into ./design_handoff/.

Usage:
    python scripts/build_design_handoff.py

Output:
    ./design_handoff/         — ready to zip and hand off
    ./design_handoff/README.md — map of what's inside
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DST = REPO / "design_handoff"
FRONTEND = REPO / "frontend"


# Files to include — (source path relative to repo, description)
FILES: list[tuple[str, str]] = [
    # ── Core design system ─────────────────────────────────────
    ("frontend/src/app/globals.css", "MAIN: all CSS tokens, 4 themes, panel/button/chip utilities"),
    ("frontend/tailwind.config.ts", "Tailwind config — maps cyber palette to utility classes"),
    (
        "frontend/src/app/layout.tsx",
        "Root layout: fonts (JetBrains Mono + Space Grotesk), Scene, ThemeProvider",
    ),
    # ── Cyber primitives ───────────────────────────────────────
    ("frontend/src/components/cyber/Scene.tsx", "Background: gradients + scanlines + grid"),
    ("frontend/src/components/cyber/Particles.tsx", "Floating particles canvas"),
    ("frontend/src/components/cyber/MitsMark.tsx", "Logo SVG (hex + triangle + core)"),
    ("frontend/src/components/cyber/Glitch.tsx", "Glitch-text effect wrapper"),
    ("frontend/src/components/cyber/Typed.tsx", "Typewriter animation"),
    ("frontend/src/components/cyber/StatusBar.tsx", "Top status bar: model/cache/latency/view"),
    ("frontend/src/components/cyber/AppShell.tsx", "Page wrapper: StatusBar + Sidebar + main"),
    ("frontend/src/components/cyber/ThemeProvider.tsx", "4 themes + glow/scanlines/glitch toggles"),
    ("frontend/src/components/cyber/TweaksPanel.tsx", "Legacy theme tweaks panel"),
    # ── Pages ──────────────────────────────────────────────────
    ("frontend/src/app/page.tsx", "Home: hero + terminal + topic grid"),
    ("frontend/src/app/auth/login/page.tsx", "Login: 2-panel grimoire design"),
    ("frontend/src/app/auth/register/page.tsx", "Register"),
    ("frontend/src/app/chat/[sessionId]/page.tsx", "Chat wrapper (uses ChatContainer)"),
    ("frontend/src/app/graph/page.tsx", "Interactive SVG knowledge graph"),
    ("frontend/src/app/tasks/page.tsx", "Task bank + generator modal"),
    ("frontend/src/app/sources/page.tsx", "Knowledge Forge sources + upload modal"),
    ("frontend/src/app/profile/page.tsx", "Profile: stats + timeline + focus chart"),
    ("frontend/src/app/settings/page.tsx", "Theme cards + effects sliders"),
    ("frontend/src/app/dashboard/page.tsx", "Dashboard (legacy shadcn style)"),
    # ── Chat UI ────────────────────────────────────────────────
    ("frontend/src/components/chat/ChatContainer.tsx", "Chat header + messages + input"),
    ("frontend/src/components/chat/Message.tsx", "Individual message bubble (user/tutor)"),
    ("frontend/src/components/chat/ChatInput.tsx", "Textarea + SEND + attachment + mode tabs"),
    ("frontend/src/components/chat/AttachmentButton.tsx", "Paperclip attachment button"),
    ("frontend/src/components/chat/ModeSelector.tsx", "Free chat / Guided / Task tabs"),
    ("frontend/src/components/chat/ThinkingPanel.tsx", "Claude-style reasoning panel with timer"),
    ("frontend/src/components/chat/SmartContent.tsx", "Markdown/Mermaid/Plotly router"),
    ("frontend/src/components/chat/MermaidBlock.tsx", "Mermaid diagram renderer"),
    ("frontend/src/components/chat/PlotlyBlock.tsx", "Plotly chart renderer"),
    ("frontend/src/components/chat/MathRenderer.tsx", "KaTeX for $...$ formulas"),
    ("frontend/src/components/chat/ImageUpload.tsx", "Image upload (legacy, for vision endpoint)"),
    # ── Navigation ─────────────────────────────────────────────
    (
        "frontend/src/components/layout/Sidebar.tsx",
        "Left sidebar: brand, nav, session list, logout",
    ),
    # ── Data-driven design ─────────────────────────────────────
    ("frontend/src/lib/domains.ts", "Domain colors (math=violet, phys=yellow, etc.)"),
    ("frontend/src/lib/i18n.ts", "UI text labels (RU/EN) — for text content reference"),
]


README = """# MITS Design Handoff

Пакет дизайнерских файлов для передачи в Claude Design или дизайнеру.

## Структура

Все пути сохранены **относительно корня репозитория** (`C:\\Work\\MITS\\`).
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
"""


def main() -> None:
    print(f"Building design handoff at: {DST}\n")

    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    copied = 0
    missing = []

    for rel_path, desc in FILES:
        src = REPO / rel_path
        dst = DST / rel_path
        if not src.exists():
            missing.append(rel_path)
            print(f"  MISSING  {rel_path}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        size_kb = src.stat().st_size / 1024
        print(f"  OK       {rel_path}  ({size_kb:.1f} KB) — {desc}")
        copied += 1

    # Write README
    (DST / "README.md").write_text(README, encoding="utf-8")

    # Summary
    print(f"\nCopied: {copied} files")
    if missing:
        print(f"Missing: {len(missing)}")

    total_size = sum(f.stat().st_size for f in DST.rglob("*") if f.is_file()) / 1024
    print(f"Total size: {total_size:.1f} KB")
    print(f"\nReady at: {DST}")
    print("\nNext steps:")
    print(f"  1. Review:   Start-Process {DST}")
    print(f"  2. Zip it:   Compress-Archive -Path '{DST}\\*' -DestinationPath design_handoff.zip")
    print("  3. Upload zip to Claude Design with the README as context.")


if __name__ == "__main__":
    main()
