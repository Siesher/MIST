# Quickstart: Claude-Style UI Redesign

**Feature**: 008-claude-ui-redesign
**Date**: 2026-02-03

## Prerequisites

- Python 3.11+
- Gradio 4.x installed (`pip install gradio>=4.0`)
- Existing MITS codebase with `interface/unified_app.py`

## Directory Setup

```bash
# Создать новые директории
mkdir -p interface/themes
mkdir -p interface/styles
mkdir -p interface/assets
```

## Implementation Order

### Phase 1: Theme Foundation (US1, US4)

1. **Создать базовые темы**
   - `interface/themes/claude_dark.py` — тёмная тема
   - `interface/themes/claude_light.py` — светлая тема

2. **Создать CSS стили**
   - `interface/styles/claude.css` — кастомные стили

3. **Добавить аватары**
   - `interface/assets/user_avatar.svg`
   - `interface/assets/bot_avatar.svg`

### Phase 2: Core Layout (US1, US2)

1. **Модифицировать `unified_app.py`**
   - Применить custom theme
   - Добавить CSS через `gr.Blocks(css=...)`
   - Настроить `gr.Chatbot(avatar_images=...)`
   - Реализовать sticky input

2. **Добавить typing indicator**
   - Использовать "🧠 *Думаю...*" placeholder

### Phase 3: Interactivity (US3, US5)

1. **Добавить JavaScript**
   - Copy button для code blocks
   - Theme toggle с localStorage
   - Sidebar collapse animation

2. **Реализовать sidebar**
   - Gradio state для collapsed
   - CSS transitions

### Phase 4: Polish (US6)

1. **Добавить анимации**
   - Message appear animation
   - Theme transition
   - Sidebar toggle

2. **Тестирование**
   - Visual testing на разных экранах
   - Performance testing (60fps)

## Quick Verification

```bash
# Запустить приложение
python run.py

# Открыть в браузере
# http://localhost:7860

# Проверить:
# [ ] Тёмная тема по умолчанию
# [ ] Чат по центру (max-width 800px)
# [ ] Input sticky внизу
# [ ] Аватары у сообщений
```

## Key Files to Modify

| File | Changes |
|------|---------|
| `interface/unified_app.py` | Apply theme, CSS, JS, avatar_images |
| `src/config.py` | Add UI settings if needed |

## Key Files to Create

| File | Purpose |
|------|---------|
| `interface/themes/claude_dark.py` | Dark theme definition |
| `interface/themes/claude_light.py` | Light theme definition |
| `interface/styles/claude.css` | Custom CSS styles |
| `interface/assets/user_avatar.svg` | User avatar icon |
| `interface/assets/bot_avatar.svg` | Bot avatar icon |

## Testing Checklist

- [ ] Dark theme renders correctly
- [ ] Light theme renders correctly
- [ ] Theme switch works and persists
- [ ] Chat centered with max-width
- [ ] Input sticky at bottom
- [ ] Avatars display correctly
- [ ] Code copy button appears on hover
- [ ] Copy button works
- [ ] Typing indicator shows during generation
- [ ] Sidebar collapses/expands
- [ ] Sidebar state persists
- [ ] Animations are smooth (60fps)
- [ ] Responsive on mobile (320px)
- [ ] Responsive on desktop (2560px)
