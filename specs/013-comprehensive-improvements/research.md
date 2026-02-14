# Research: MITS Comprehensive Improvements

**Date**: 2026-02-05
**Feature**: 013-comprehensive-improvements

## R1: QLoRA Fine-tuning GLM-4.7-Flash

**Decision**: Use Unsloth + TRL for QLoRA fine-tuning with ChatML format, export LoRA to GGUF for Ollama

**Rationale**:
- Unsloth delivers 2-5x faster training and 80% less VRAM vs standard PEFT
- TRL's SFTTrainer integrates directly with Unsloth
- GLM-4.7-Flash is supported by Unsloth as of 2026
- Ollama loads LoRA adapters via ADAPTER instruction in Modelfile (convert with `convert_lora_to_gguf.py`)
- ChatML format is native to GLM-4 and best for multi-turn tutor dialogs

**Alternatives considered**:
- PEFT alone: Slower (2-5x), no memory optimization
- LlamaFactory: Good for multi-GPU but less efficient on single A100
- Merging weights into GGUF: Loses adapter modularity

**Practical notes**:
- Training time: ~2-4 hours on A100 for 1000 dialogs
- Pipeline: Train (Unsloth) → Export LoRA → Convert to GGUF → Ollama create with ADAPTER
- Colab notebook in `notebooks/finetuning_glm.ipynb`

---

## R2: DKT Training on ASSISTments

**Decision**: LSTM-based DKT on ASSISTments 2009-2010 skill-builder dataset using PyTorch

**Rationale**:
- ASSISTments 2009: 346,860 attempts, 4,217 students, 123 skills — standard benchmark
- LSTM-DKT achieves AUC 0.84-0.86 (original paper: 0.86)
- Multiple open-source PyTorch implementations available
- Fast training: <1 hour on A100

**Alternatives considered**:
- DKT+: +2% AUC but more complex
- DKVMN: Higher performance but significantly more complex architecture
- Transformer-based KT: State-of-art but resource-intensive, overkill for our data size

**Practical notes**:
- Download: sites.google.com/site/assistmentsdata (skill-builder-data-2009-2010)
- Preprocessing: Remove scaffolding, map skills to IDs, create sequences, pad/truncate
- Export trained weights to `data/models/dkt_pretrained.pt`
- Reference: github.com/hcnoh/knowledge-tracing-collection-pytorch

---

## R3: RuBERT for Emotion Classification

**Decision**: Fine-tune DeepPavlov/rubert-base-cased for 5-class emotion detection

**Rationale**:
- DeepPavlov RuBERT: 180M params, trained on Russian Wikipedia + news
- Well-established for Russian text classification tasks
- Expected macro F1: 0.60-0.70 for 5-class emotion
- Bootstrap labeled data from existing rule-based annotations

**Alternatives considered**:
- Sberbank AI models: Similar performance, less community support
- Multilingual BERT: Lower performance on Russian-specific patterns
- blanchefort/rubert-base-cased-sentiment: Pre-trained for sentiment but only 3 classes

**Practical notes**:
- Dataset: Generate labels using existing rule-based detector on MITS sessions, target 3000-5000 examples
- Training: 3-5 epochs, lr=2e-5, ~30-60 min on A100
- Active learning: Use model uncertainty to select examples for manual review
- Colab notebook in `notebooks/affective_rubert.ipynb`

---

## R4: Vision Model for Math OCR

**Decision**: Qwen2.5-VL-7B via Ollama + SymPy verification pipeline

**Rationale**:
- Native Ollama support (`ollama pull qwen2.5vl`)
- Excellent math OCR (trained on OCRBench with formulas)
- Processes images and outputs LaTeX directly
- ~13GB GGUF (Q5_K_M quantization)

**Alternatives considered**:
- InternVL2: Strong but no explicit Ollama support
- Specialized HMER models: Research-grade, harder to deploy
- MathPix API: Proprietary, adds cost

**Practical notes**:
- Pipeline: Image → Qwen2.5-VL → LaTeX → SymPy parse → Verify/Compare
- CROHME dataset for evaluation: 11,000+ expressions, ~70-80% expression accuracy
- Vision model loaded on-demand (separate from tutoring model)
- Frontend: file upload component → base64 → WebSocket/REST

---

## R5: Synthetic Dialog Generation

**Decision**: GPT-4/Claude API for bootstrap (1000 dialogs), then self-generate with fine-tuned GLM

**Rationale**:
- Bootstrap with strong models ensures high-quality seed data
- ConvoLearn schema provides annotation template
- Cross-verification (Claude evaluates GPT-4 output) improves quality by 37%
- Cost: ~$50 for 1000 bootstrap dialogs
- After fine-tuning, GLM self-generates free dialogs for scaling

**Alternatives considered**:
- Self-generation only: Lower initial quality, risks error amplification
- Human-only: $25-50/dialog, prohibitively expensive
- Existing datasets: CIMA/MetaTutor available but not math-focused

**Practical notes**:
- Schema: dialog_id, topic, difficulty, turns (speaker, text, move_type, correctness, knowledge_component)
- Quality filtering: min 10 turns, balanced speaker ratio, LLM cross-verification
- Output: `data/training/synthetic_dialogs.jsonl`

---

## R6: Session Persistence

**Decision**: SQLAlchemy ORM + Alembic migrations

**Rationale**:
- FastAPI official recommendation for database integration
- Async support via `async_scoped_session`
- Alembic auto-generates migrations with manual review
- Type safety with SQLModel (Pydantic + SQLAlchemy)

**Alternatives considered**:
- Raw sqlite3: No migration management, no connection pooling
- Manual migration scripts: Error-prone vs Alembic's versioned approach

**Practical notes**:
- Tables: sessions, messages, session_state
- Keep StoredSession dataclass as Pydantic model, map to SQLAlchemy models
- Install: `pip install sqlalchemy[asyncio] alembic`

---

## R7: JWT Authentication

**Decision**: PyJWT + Argon2 password hashing

**Rationale**:
- python-jose is abandoned (3+ years) — PyJWT is the current standard
- Argon2 won Password Hashing Competition 2015, GPU-resistant
- Simple flow: register → login → access/refresh tokens
- WebSocket auth via query param or first message

**Alternatives considered**:
- fastapi-users: Full-featured but overkill for student accounts
- bcrypt: 72-char limit, vulnerable to modern GPU attacks

**Practical notes**:
- Access tokens: 15-30 min, refresh tokens: 7-30 days
- WebSocket: verify JWT on connection, refresh proactively
- Install: `pip install PyJWT argon2-cffi`

---

## R8: Docker Deployment

**Decision**: Docker Compose with 3 services (backend, frontend, ollama)

**Rationale**:
- Ollama has official Docker image with NVIDIA GPU passthrough
- Independent scaling per service
- Volume mounts for model persistence (10-20GB)

**Alternatives considered**:
- Monolithic container: Can't scale LLM independently
- Kubernetes: Overkill for single-node deployment

**Practical notes**:
- GPU passthrough: `deploy.resources.reservations.devices` in compose
- Multi-stage builds for frontend (deps → build → serve)
- Volume: `ollama_models` for persistent model storage

---

## R9: PDF Export

**Decision**: WeasyPrint (HTML/CSS → PDF)

**Rationale**:
- HTML/CSS templating is faster than programmatic layout (ReportLab)
- Easy chart embedding (matplotlib → base64 PNG in `<img>`)
- Math rendering via KaTeX/MathJax in HTML

**Alternatives considered**:
- ReportLab: More control but steep learning curve
- fpdf2: No HTML support, manual positioning

**Practical notes**:
- Template: Jinja2 HTML → WeasyPrint → PDF bytes → FastAPI StreamingResponse
- Install: `pip install weasyprint matplotlib jinja2`

---

## R10: Analytics Dashboard

**Decision**: Recharts + react-activity-calendar

**Rationale**:
- Recharts dominates React charts: composable, TypeScript, SVG
- react-activity-calendar: standard GitHub-style heatmap
- Next.js 14 compatible

**Alternatives considered**:
- Chart.js: Canvas-based, better for >10K data points
- Visx: Lower-level D3 primitives, steeper curve

**Practical notes**:
- Install: `npm install recharts react-activity-calendar`
- API: `/api/v1/analytics/activity`, `/api/v1/analytics/performance`
- Polling every 60s for dashboard updates

---

## R11: Optimization Modules

**Decision**: In-memory LRU cache + sliding window context compression + FastAPI BackgroundTasks

**Rationale**:
- LRU cache (async_lru) for sub-ms repeated queries
- Sliding window: keep system prompt + recent N turns + key events summary
- BackgroundTasks sufficient for single-server (no Celery needed)

**Alternatives considered**:
- Redis semantic cache: Adds infra complexity, use only if multi-worker
- Celery: Overkill for current scale
- LLM summary compression: Requires LLM call, defeats purpose

**Practical notes**:
- Cache: `@alru_cache(maxsize=128)` for profiles, custom dict for LLM responses
- Compression: Keep last 5 turns + extract key events from older turns
- Prefetcher: BackgroundTask on task assignment to pre-compute 3 hint levels
