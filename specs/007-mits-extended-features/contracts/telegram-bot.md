# Telegram Bot Command Reference

**Bot Name**: @MITSTutorBot (configurable)
**Date**: 2026-02-02

## Overview

The MITS Telegram bot provides full tutoring capabilities through Telegram, including:
- Text-based math tutoring with LaTeX rendering
- Voice message support (speech-to-text and text-to-speech)
- Progress tracking and gamification
- Review reminders (spaced repetition)

## Commands

### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Initialize bot, create profile | `/start` |
| `/help` | Show available commands | `/help` |
| `/settings` | Configure preferences | `/settings` |

### Tutoring Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/problem` | Get a new problem | `/problem algebra easy` |
| `/hint` | Request a hint for current problem | `/hint` |
| `/skip` | Skip current problem | `/skip` |
| `/solution` | Show solution (affects stats) | `/solution` |

### Progress Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/stats` | Show progress summary | `/stats` |
| `/streak` | Show streak status | `/streak` |
| `/achievements` | List achievements | `/achievements` |
| `/review` | Start review session | `/review` |

### Export Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/export` | Export profile as JSON | `/export` |
| `/backup` | Create full backup | `/backup` |

---

## Message Handling

### Text Messages

Any text message not starting with `/` is treated as a tutoring conversation.

**Input**: User's math question or response
**Output**: Socratic tutoring response with LaTeX-rendered formulas

**Example Interaction**:
```
User: Как решить уравнение x^2 - 5x + 6 = 0?
Bot: [Image: x² - 5x + 6 = 0]

Отличный вопрос! Давай разберём это вместе.

Посмотри на уравнение. Можешь ли ты представить его как произведение двух скобок?

Подсказка: подумай, какие два числа дают в сумме -5, а при умножении +6?
```

### Voice Messages

Voice messages are transcribed and processed as text.

**Input**: Voice message (Russian supported)
**Output**: Text response + optional TTS audio

**Flow**:
1. Receive voice message
2. Transcribe using Vosk/Google STT
3. Process as tutoring message
4. Return text response
5. Optionally return voice response (if enabled in settings)

### Images

Images with math problems are processed with OCR.

**Input**: Photo with handwritten or printed math
**Output**: Extracted problem + tutoring response

**Note**: OCR accuracy depends on image quality. Users should confirm extracted text.

---

## Inline Queries

Support for inline LaTeX rendering in any chat.

**Usage**: `@MITSTutorBot \frac{a}{b}`
**Result**: Rendered image of the formula

---

## Callback Queries (Button Interactions)

### Problem Difficulty Selection
```
difficulty:easy
difficulty:medium
difficulty:hard
```

### Topic Selection
```
topic:algebra
topic:geometry
topic:calculus
```

### Review Quality Rating (SM-2)
```
review:0  # Complete failure
review:1  # Major errors
review:2  # Several errors
review:3  # Difficult, correct
review:4  # Correct, some hesitation
review:5  # Perfect recall
```

### Settings
```
settings:voice_on
settings:voice_off
settings:notifications_on
settings:notifications_off
settings:language:ru
settings:language:en
```

---

## Notifications

### Types

| Type | Trigger | Message Template |
|------|---------|-----------------|
| Review Due | Topics due for review | "У тебя {count} тем на повторение! /review" |
| Streak Reminder | No activity today (8 PM) | "Не забудь позаниматься сегодня! Серия: {streak} дней" |
| Achievement | New achievement unlocked | "🏆 Новое достижение: {name}!" |
| Level Up | Level increased | "🎉 Поздравляю! Уровень {level}!" |

### User Preferences

Users can configure notifications via `/settings`:
- Enable/disable all notifications
- Set reminder time
- Choose notification types

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| Messages | 30 | 1 minute |
| Voice transcription | 10 | 1 minute |
| Image OCR | 5 | 1 minute |
| Export | 1 | 1 hour |

---

## Error Messages

| Code | Russian Message | English Message |
|------|-----------------|-----------------|
| `rate_limit` | "Слишком много сообщений. Подожди минутку." | "Too many messages. Wait a moment." |
| `voice_failed` | "Не удалось распознать речь. Попробуй текстом." | "Speech recognition failed. Try text." |
| `ocr_failed` | "Не удалось прочитать изображение." | "Could not read the image." |
| `server_error` | "Ошибка сервера. Попробуй позже." | "Server error. Try again later." |

---

## LaTeX Rendering

Math formulas are rendered to PNG images using matplotlib.

**Supported Formats**:
- Inline: `$x^2$` or `\(x^2\)`
- Display: `$$\frac{a}{b}$$` or `\[\frac{a}{b}\]`

**Rendering Pipeline**:
1. Detect LaTeX in response
2. Extract formula segments
3. Render each to PNG (150 DPI, transparent background)
4. Send as inline images or separate media

**Size Limits**:
- Maximum formula length: 500 characters
- Maximum formulas per message: 5

---

## Data Storage

### Per-User Data

| Data | Storage | Retention |
|------|---------|-----------|
| Profile | SQLite | Permanent |
| Chat history | SQLite | 30 days |
| Voice files | Temp | 1 hour |
| Images | Temp | 1 hour |

### Privacy

- No message content logged beyond tutoring context
- Voice files deleted after transcription
- GDPR-compliant data export via `/export`
- Account deletion via `/settings` -> "Delete account"

---

## Webhook vs Polling

**Development**: Long polling (`bot.polling()`)
**Production**: Webhook mode recommended

```python
# Webhook setup
app = web.Application()
app.router.add_post('/webhook/{token}', handle_update)
await bot.set_webhook(f'https://your-domain.com/webhook/{TOKEN}')
```

**Requirements for Webhook**:
- HTTPS endpoint
- Valid SSL certificate
- Port 443, 80, 88, or 8443
