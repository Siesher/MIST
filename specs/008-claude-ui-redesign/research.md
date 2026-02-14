# Research: Claude-Style UI Redesign

**Feature**: 008-claude-ui-redesign
**Date**: 2026-02-03

## Research Questions

### 1. Gradio 4.x Theming Capabilities

**Question**: Как создать custom theme в Gradio 4.x для Claude-like дизайна?

**Findings**:
- Gradio 4.x поддерживает `gr.themes.Base` для создания custom тем
- Можно переопределить цвета, шрифты, border-radius, shadows
- CSS можно инжектировать через `gr.Blocks(css=...)` параметр
- JavaScript можно добавить через `gr.Blocks(js=...)` для интерактивности

**Decision**: Использовать комбинацию:
1. `gr.themes.Base` для базовых цветов и типографики
2. Custom CSS для продвинутых стилей (анимации, sticky input)
3. JavaScript для copy-to-clipboard функциональности

**Alternatives Considered**:
- Чистый CSS без custom theme: Отклонено — сложнее поддерживать
- Сторонние UI библиотеки: Отклонено — несовместимы с Gradio

---

### 2. Sticky Input Implementation

**Question**: Как реализовать sticky input внизу экрана в Gradio?

**Findings**:
- Gradio использует flexbox layout для компонентов
- CSS `position: sticky` работает с правильной структурой DOM
- Нужно переопределить контейнер чата с `height: calc(100vh - input_height)`
- Скролл должен быть внутри chatbot контейнера

**Decision**: CSS-based решение:
```css
.chat-container {
  height: calc(100vh - 120px);
  overflow-y: auto;
}
.input-container {
  position: sticky;
  bottom: 0;
  background: var(--background-fill-primary);
}
```

**Alternatives Considered**:
- JavaScript scroll management: Отклонено — избыточная сложность
- Absolute positioning: Отклонено — проблемы с responsive

---

### 3. Dark/Light Theme Switching

**Question**: Как реализовать переключение тем с сохранением в localStorage?

**Findings**:
- Gradio 4.x поддерживает runtime theme switching через `gr.Blocks.theme`
- localStorage API доступен через JavaScript
- Можно использовать CSS variables для мгновенного переключения
- Gradio state может синхронизироваться с localStorage

**Decision**: Dual approach:
1. CSS variables для всех цветов (мгновенное переключение)
2. JavaScript для сохранения/загрузки из localStorage
3. Python callback для синхронизации с Gradio state

**Alternatives Considered**:
- Server-side theme storage: Отклонено — лишняя latency
- Cookie-based: Отклонено — localStorage проще и безопаснее

---

### 4. Code Copy Button

**Question**: Как добавить кнопку копирования для блоков кода в Gradio Chatbot?

**Findings**:
- Gradio Chatbot рендерит markdown включая code blocks
- Code blocks получают класс `.code-block` или `pre code`
- JavaScript может добавить кнопку через DOM manipulation
- Clipboard API (`navigator.clipboard.writeText`) работает в современных браузерах

**Decision**: JavaScript injection:
```javascript
// Добавляем кнопки ко всем code blocks при появлении
const observer = new MutationObserver(addCopyButtons);
observer.observe(chatContainer, { childList: true, subtree: true });
```

**Alternatives Considered**:
- Gradio custom component: Отклонено — избыточно для одной кнопки
- Backend-generated buttons: Отклонено — не работает с streaming

---

### 5. Message Animation

**Question**: Как анимировать появление новых сообщений?

**Findings**:
- CSS animations работают с Gradio
- Нужен MutationObserver для детекции новых сообщений
- `@keyframes` для slide-up + fade-in эффекта
- `animation-duration: 200ms` для плавности без заметной задержки

**Decision**: CSS + MutationObserver:
```css
@keyframes messageAppear {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.message { animation: messageAppear 200ms ease-out; }
```

**Alternatives Considered**:
- React Spring: Отклонено — не совместимо с Gradio
- No animation: Отклонено — требование спецификации

---

### 6. Avatar Implementation

**Question**: Как добавить аватары к сообщениям в Gradio Chatbot?

**Findings**:
- Gradio 4.x Chatbot поддерживает `avatar_images` параметр
- Можно передать tuple (user_avatar, bot_avatar)
- Аватары могут быть URL или локальные файлы
- SVG аватары работают и легковесны

**Decision**: Использовать `avatar_images` параметр:
```python
gr.Chatbot(
    avatar_images=("assets/user_avatar.svg", "assets/bot_avatar.svg")
)
```

**Alternatives Considered**:
- CSS псевдо-элементы: Отклонено — сложнее, менее надёжно
- Emoji аватары: Отклонено — непрофессионально для Claude-style

---

### 7. Collapsible Sidebar

**Question**: Как реализовать сворачиваемый sidebar в Gradio?

**Findings**:
- `gr.Column(visible=...)` может скрывать элементы
- CSS transitions работают с `width` property
- Нужен state для хранения sidebar_collapsed
- JavaScript может анимировать transition

**Decision**: Gradio state + CSS transitions:
```python
sidebar_state = gr.State(value=False)
with gr.Column(visible=True, elem_classes=["sidebar"]) as sidebar:
    ...
toggle_btn.click(toggle_sidebar, [sidebar_state], [sidebar, sidebar_state])
```

**Alternatives Considered**:
- gr.Accordion: Отклонено — не подходит для layout sidebar
- Overlay sidebar: Отклонено — не соответствует Claude desktop style

---

## Technology Stack Summary

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Theme base | gr.themes.Base | Нативная поддержка Gradio |
| Custom styles | CSS3 | Гибкость, анимации |
| Interactivity | JavaScript ES6 | Copy button, localStorage |
| Avatars | SVG files | Лёгкие, масштабируемые |
| State | Gradio State + localStorage | Persistence across sessions |

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Gradio update breaks CSS | Low | Medium | Pin Gradio version, test on updates |
| Browser compatibility | Low | Low | Target modern browsers only |
| Performance on mobile | Medium | Medium | Test animations, reduce if needed |
| Accessibility concerns | Low | Medium | Maintain ARIA labels, keyboard nav |
