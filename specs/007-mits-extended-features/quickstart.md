# Quickstart: MITS Extended Features

**Date**: 2026-02-02
**Feature**: 007-mits-extended-features

## Prerequisites

- Python 3.11+
- CUDA-capable GPU (RTX 2080 or better, 8GB VRAM)
- Ollama installed and running
- Git

## Installation

### 1. Clone and Setup Environment

```bash
git clone https://github.com/your-org/mits.git
cd mits
git checkout 007-mits-extended-features

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Install New Dependencies

```bash
# Tools
pip install sympy duckduckgo-search

# Voice I/O
pip install vosk SpeechRecognition gTTS pyttsx3

# Visualization
pip install plotly networkx

# Telegram
pip install python-telegram-bot

# REST API
pip install fastapi uvicorn python-jose[cryptography] slowapi

# Download Vosk Russian model (optional, for voice)
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
unzip vosk-model-small-ru-0.22.zip
mv vosk-model-small-ru-0.22 vosk-model-small-ru
cd ..
```

### 3. Configure Environment

Copy and edit `.env`:

```bash
cp .env.example .env
```

Add new settings:

```env
# Telegram Bot (get from @BotFather)
TELEGRAM_BOT_TOKEN=your_token_here

# REST API
API_SECRET_KEY=your-secret-key-min-32-chars
API_RATE_LIMIT=60  # requests per minute

# Voice (optional)
VOICE_ENABLED=true
VOSK_MODEL_PATH=./models/vosk-model-small-ru

# Gamification
XP_MULTIPLIER=1.0
STREAK_FREEZE_COUNT=3
```

### 4. Initialize Database

```bash
# Run migrations for new tables
python scripts/init_db.py --extended
```

### 5. Verify Installation

```bash
# Run tests
pytest tests/unit/test_tools.py -v
pytest tests/unit/test_gamification.py -v

# Check all imports
python -c "from src.tools import calculator, web_search; print('Tools OK')"
python -c "from src.gamification import xp_system, achievements; print('Gamification OK')"
```

---

## Running the Application

### Main Gradio App (with extended features)

```bash
python run.py
# or: python interface/unified_app.py
```

Access at: http://localhost:7860

### REST API Server

```bash
uvicorn interface.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Access at: http://localhost:8000

API Docs: http://localhost:8000/docs

### Telegram Bot

```bash
python telegram_bot/bot.py
```

Or with webhook mode:

```bash
WEBHOOK_URL=https://your-domain.com python telegram_bot/bot.py --webhook
```

---

## Feature-Specific Setup

### Calculator Tool

No setup required. Uses SymPy (pure Python).

```python
from src.tools.calculator import calculate
result = calculate("diff(x**2 + 3*x, x)")  # "2*x + 3"
```

### Web Search Tool

No API key required. Uses DuckDuckGo.

```python
from src.tools.web_search import search
results = search("квадратные уравнения примеры", max_results=5)
```

### Voice Input

Requires Vosk model download (see step 2).

```python
from src.voice.speech_to_text import transcribe_audio
text = transcribe_audio("audio.wav")  # Russian supported
```

### Voice Output

Works out of the box with gTTS (requires internet) or pyttsx3 (offline).

```python
from src.voice.text_to_speech import speak
audio_bytes = speak("Привет! Давай решим задачу.")
```

### Progress Dashboard

Integrated into Gradio app. Access via "Dashboard" tab.

```python
from interface.components.dashboard import create_dashboard
dashboard = create_dashboard(student_id="test")
```

### Spaced Repetition

Automatic after mastering topics. Check due reviews:

```python
from src.spaced_repetition.scheduler import get_due_cards
cards = get_due_cards(student_id="test")
```

### Profile Export

```python
from src.export.json_export import export_profile
data = export_profile(student_id="test")
# Save to file
with open("profile.json", "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

---

## Development Workflow

### Adding New Achievements

Edit `data/gamification/achievements.json`:

```json
{
  "id": "new_achievement",
  "name": "New Achievement",
  "description": "Earned by doing X",
  "icon": "🏆",
  "category": "progress",
  "criteria": {"type": "problems_solved", "count": 50},
  "xp_reward": 100,
  "rarity": "rare"
}
```

Reload:
```bash
python scripts/reload_achievements.py
```

### Testing Tools

```bash
# Test calculator
pytest tests/unit/test_tools.py::test_calculator -v

# Test web search
pytest tests/unit/test_tools.py::test_web_search -v

# Test gamification
pytest tests/unit/test_gamification.py -v
```

### Running Integration Tests

```bash
# Requires running services
pytest tests/integration/ -v --slow
```

---

## Troubleshooting

### Voice not working

1. Check Vosk model path:
   ```bash
   ls models/vosk-model-small-ru/
   ```
2. Check microphone permissions
3. Test with Google STT (requires internet):
   ```python
   from src.voice.speech_to_text import transcribe_google
   ```

### Telegram bot not responding

1. Verify token: `echo $TELEGRAM_BOT_TOKEN`
2. Check bot is running: `ps aux | grep telegram`
3. Test webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

### API returns 401

1. Generate new token:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/token \
     -H "Content-Type: application/json" \
     -d '{"student_id": "test"}'
   ```
2. Use token in header: `Authorization: Bearer <token>`

### Dashboard charts not loading

1. Check Plotly installed: `python -c "import plotly"`
2. Verify student has activity data
3. Check browser console for JS errors

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Entry Points                             │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│  Gradio UI  │  REST API   │ Telegram Bot│    CLI           │
│  (unified)  │  (FastAPI)  │  (aiogram)  │  (scripts/)      │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │               │
       └─────────────┴─────────────┴───────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
┌─────────────┐                        ┌─────────────┐
│   Agents    │                        │  Services   │
│ Orchestrator│                        │ - Tools     │
│ - Profiler  │                        │ - Gamify    │
│ - Planner   │◄──────────────────────►│ - SR        │
│ - Tutor     │                        │ - Voice     │
│ - Verifier  │                        │ - Export    │
└──────┬──────┘                        └──────┬──────┘
       │                                      │
       └──────────────────┬───────────────────┘
                          ▼
                   ┌─────────────┐
                   │   Storage   │
                   │ - SQLite    │
                   │ - ChromaDB  │
                   │ - JSON      │
                   └─────────────┘
```

---

## Next Steps

After setup, proceed to:

1. **Run existing tests**: `pytest tests/ -v`
2. **Explore the dashboard**: Start app and check Dashboard tab
3. **Test Telegram bot**: Send `/start` to your bot
4. **Check API docs**: Visit http://localhost:8000/docs

For implementation tasks, see [tasks.md](./tasks.md) (generated by `/speckit.tasks`).
