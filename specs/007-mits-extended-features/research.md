# Research: MITS Extended Features

**Date**: 2026-02-02
**Feature**: 007-mits-extended-features

## 1. Streaming Responses

### Decision
Use Gradio's native streaming with `yield` in chat function combined with Ollama's streaming API.

### Rationale
- Gradio 4.x+ has built-in streaming support via `gr.ChatInterface` with `stream=True`
- Ollama Python client supports `stream=True` returning token-by-token generator
- No additional dependencies needed

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Server-Sent Events (SSE) | Overkill for single-user; Gradio handles this internally |
| WebSockets | More complex; Gradio already uses WebSockets under the hood |
| Custom chunking | Reinventing the wheel; native support is better |

### Implementation Notes
```python
# Ollama streaming
for chunk in client.chat(messages=messages, stream=True):
    yield chunk['message']['content']
```

---

## 2. Calculator Tool

### Decision
Use SymPy for symbolic and numerical mathematics.

### Rationale
- Pure Python, no external services
- Handles symbolic math (derivatives, integrals, simplification)
- Supports arbitrary precision arithmetic
- Already commonly used in educational contexts
- Offline-capable

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| eval() | Security risk; arbitrary code execution |
| NumPy only | No symbolic computation |
| Wolfram Alpha API | Requires API key; not free for high volume |
| mathjs | JavaScript; would need subprocess or API |

### Implementation Notes
```python
from sympy import sympify, simplify, solve, diff, integrate
from sympy.parsing.sympy_parser import parse_expr

def calculate(expression: str) -> str:
    try:
        result = sympify(expression)
        return str(simplify(result))
    except Exception as e:
        return f"Error: {e}"
```

---

## 3. Web Search Tool

### Decision
Use DuckDuckGo Search via `duckduckgo-search` Python package.

### Rationale
- Free, no API key required
- Privacy-focused (aligns with educational use)
- Python package available: `pip install duckduckgo-search`
- Supports Russian language queries

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Google Custom Search | Requires API key; paid after free tier |
| Bing Search API | Requires Azure subscription |
| SerpAPI | Paid service |
| Web scraping | Fragile; ToS violations |

### Implementation Notes
```python
from duckduckgo_search import DDGS

def web_search(query: str, max_results: int = 5) -> list:
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return results
```

---

## 4. Voice Input (Speech-to-Text)

### Decision
Use Vosk for offline Russian speech recognition, with fallback to Google Speech Recognition for online.

### Rationale
- Vosk: Free, offline, supports Russian, reasonable accuracy
- Model size: ~50MB for Russian small model
- No API keys or internet required for core functionality
- Google fallback for better accuracy when online

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| OpenAI Whisper local | 1-2GB VRAM usage; conflicts with LLM |
| Google Cloud STT | Paid; requires API key |
| Azure Speech | Paid; requires subscription |
| CMU Sphinx | Lower accuracy for Russian |

### Implementation Notes
```python
# Offline with Vosk
from vosk import Model, KaldiRecognizer
model = Model("models/vosk-model-small-ru")
recognizer = KaldiRecognizer(model, 16000)

# Online fallback
import speech_recognition as sr
recognizer = sr.Recognizer()
recognizer.recognize_google(audio, language="ru-RU")
```

---

## 5. Voice Output (Text-to-Speech)

### Decision
Use gTTS (Google Text-to-Speech) for Russian synthesis; offline fallback with pyttsx3.

### Rationale
- gTTS: Free, good quality Russian, simple API
- pyttsx3: Offline fallback using system voices
- Both support Russian language

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Coqui TTS | Requires GPU; conflicts with LLM |
| Azure TTS | Paid service |
| Amazon Polly | Paid service |
| eSpeak | Poor quality for Russian |

### Implementation Notes
```python
from gtts import gTTS
import pyttsx3

def text_to_speech(text: str, lang: str = "ru") -> bytes:
    try:
        tts = gTTS(text=text, lang=lang)
        # Return audio bytes
    except:
        # Fallback to pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('voice', 'ru')
```

---

## 6. Spaced Repetition (SM-2)

### Decision
Implement standard SM-2 algorithm with SQLite storage for review schedules.

### Rationale
- SM-2 is well-documented, proven effective
- Simple to implement (~50 lines of Python)
- No external dependencies beyond SQLite
- Parameters can be tuned per-topic

### Algorithm Summary
```
After each review:
1. User rates quality (0-5)
2. If quality >= 3: interval increases by easiness factor
3. If quality < 3: interval resets to 1 day
4. Easiness factor adjusts based on performance
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Anki integration | External dependency; complex |
| SM-15/SM-18 | Overly complex; marginal gains |
| Leitner system | Less adaptive than SM-2 |
| FSRS | Newer, less tested; SM-2 sufficient |

---

## 7. Gamification System

### Decision
Custom XP/achievement system with SQLite storage and JSON-defined achievements.

### Rationale
- Specific to educational context (not generic gaming)
- XP tied to problem difficulty and educational value
- Achievements encourage positive learning behaviors
- Simple SQLite schema; no external services

### XP Formula
```python
base_xp = {
    "easy": 10,
    "medium": 25,
    "hard": 50,
    "olympiad": 100
}
# Bonus for streaks, first attempts, etc.
xp = base_xp[difficulty] * streak_multiplier * first_attempt_bonus
```

### Achievement Categories
1. **Progress**: First problem, 10 problems, 100 problems
2. **Mastery**: Topic mastered, all algebra mastered
3. **Streaks**: 7 days, 30 days, 100 days
4. **Challenge**: Hard problem solved, no hints used

---

## 8. Progress Dashboard

### Decision
Use Plotly for charts embedded in Gradio via `gr.Plot`.

### Rationale
- Plotly integrates well with Gradio
- Interactive charts (hover, zoom)
- Supports all needed chart types (bar, line, heatmap, treemap)
- No additional frontend framework needed

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Matplotlib | Static images; less interactive |
| Chart.js | Requires JavaScript; complex integration |
| Bokeh | Heavier; Plotly sufficient |
| Custom SVG | Reinventing the wheel |

---

## 9. Knowledge Graph Visualization

### Decision
Use Plotly with networkx for graph layout, rendered in Gradio.

### Rationale
- networkx for graph algorithms and layout
- Plotly for interactive rendering
- Can highlight completed/pending/locked skills
- Gradio-compatible

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| D3.js | JavaScript; complex Gradio integration |
| vis.js | JavaScript; same issues |
| Graphviz | Static images; not interactive |
| Cytoscape | Overkill for simple skill tree |

---

## 10. Telegram Bot

### Decision
Use `python-telegram-bot` library with webhook mode for production.

### Rationale
- Official, well-maintained library
- Async support for handling multiple users
- Supports inline queries, voice messages
- Good documentation and community

### LaTeX Rendering
Use `matplotlib` to render LaTeX to PNG images for Telegram.

```python
import matplotlib.pyplot as plt
from io import BytesIO

def latex_to_image(latex: str) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 1))
    ax.text(0.5, 0.5, f"${latex}$", fontsize=20, ha='center', va='center')
    ax.axis('off')
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    return buf.getvalue()
```

---

## 11. REST API

### Decision
Use FastAPI with JWT authentication and rate limiting via slowapi.

### Rationale
- FastAPI: Modern, async, auto-generates OpenAPI docs
- JWT: Stateless, widely supported
- slowapi: Simple rate limiting middleware
- Pydantic models already used in MITS

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Flask | Synchronous; no auto OpenAPI |
| Django REST | Heavy; overkill for this API |
| gRPC | Overkill; REST sufficient for use case |

---

## 12. Profile Export/Import

### Decision
JSON as primary format; Obsidian markdown as secondary.

### Rationale
- JSON: Universal, preserves all data types
- Obsidian: Markdown files with wiki-links, popular among students
- Notion: Complex API; lower priority (SHOULD, not MUST)

### Export Schema
```json
{
  "version": "1.0",
  "exported_at": "2026-02-02T12:00:00Z",
  "profile": {
    "student_id": "...",
    "mastery": {...},
    "xp": 1234,
    "level": 5,
    "achievements": [...],
    "streak": {...},
    "history": [...]
  }
}
```

---

## 13. Embedding Cache

### Decision
Use ChromaDB's persistent storage with LRU eviction policy.

### Rationale
- ChromaDB already in stack for RAG
- Persistent by default with `persist_directory`
- Efficient similarity search for cache lookup
- No additional dependencies

### Cache Strategy
```python
# On query:
1. Hash the input text
2. Check ChromaDB for existing embedding
3. If found: return cached embedding
4. If not: compute, store, return

# Eviction: by access timestamp when cache exceeds limit
```

---

## 14. Batch Inference

### Decision
Use Ollama's batch API (when available) or sequential with async gathering.

### Rationale
- Ollama 0.14+ supports batch requests
- For older versions: asyncio.gather for concurrent requests
- GPU utilization improves with batching

### Implementation Notes
```python
import asyncio

async def batch_generate(prompts: list[str]) -> list[str]:
    tasks = [generate_async(p) for p in prompts]
    return await asyncio.gather(*tasks)
```

---

## 15. Hint Prefetching

### Decision
Background task triggered when problem is displayed; results cached.

### Rationale
- User typically reads problem for 5-30 seconds
- Sufficient time to prefetch 3-5 hint levels
- Stored in session memory for instant retrieval

### Implementation Notes
```python
import threading

def prefetch_hints(problem_id: str, session: Session):
    def _prefetch():
        hints = generate_hints(problem_id)
        session.cache_hints(problem_id, hints)

    thread = threading.Thread(target=_prefetch)
    thread.start()
```

---

## Dependencies Summary

### New Packages Required
```
# Tools
sympy>=1.12
duckduckgo-search>=4.0

# Voice
vosk>=0.3.45
SpeechRecognition>=3.10
gTTS>=2.4
pyttsx3>=2.90

# Visualization
plotly>=5.18
networkx>=3.2

# Telegram
python-telegram-bot>=20.7

# REST API
fastapi>=0.109
uvicorn>=0.27
python-jose[cryptography]>=3.3
slowapi>=0.1.9

# Export
# (no new deps - uses json, pathlib)
```

### VRAM Impact Assessment
| Component | VRAM Usage | Notes |
|-----------|------------|-------|
| LLM (Ollama) | ~4-5GB | Existing |
| Embeddings | ~0.3GB | Existing |
| Vosk STT | 0GB | CPU only |
| Plotly | 0GB | CPU only |
| **Total** | ~5-6GB | Within 8GB limit |
