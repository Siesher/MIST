# 🎓 MITS - Mathematics Intelligent Tutoring System

An AI-powered tutoring system that teaches mathematics through the Socratic method - guiding students to discover solutions through questions, not answers.

## ✨ Features

- **Socratic Tutoring**: Guides students through questions, never gives direct answers
- **Multi-Agent Architecture**: Specialized agents for task generation, tutoring, and knowledge tracking
- **Adaptive Learning**: Tracks student knowledge and adjusts difficulty
- **MoE Model**: Uses Qwen3-30B-A3B for efficient, high-quality responses
- **Local Deployment**: Runs on consumer hardware (RTX 2080+)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                      │
└──────────────────────┬──────────────────────────────┘
                       │
     ┌─────────────────┼─────────────────┐
     ▼                 ▼                 ▼
┌─────────┐     ┌──────────┐     ┌──────────────┐
│  Task   │     │ SOCRATIC │     │   Student    │
│Generator│     │  TUTOR   │     │   Modeler    │
└─────────┘     └────┬─────┘     └──────────────┘
                     │
                ┌────▼─────┐
                │ Response │
                │ Verifier │
                └──────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- NVIDIA GPU with 8GB+ VRAM (RTX 2080 or better)
- [Ollama](https://ollama.com/) installed

### Installation

```bash
# 1. Clone repository
git clone <your-repo-url>
cd MITS

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Ollama and download model
# Download from: https://ollama.com/
ollama pull qwen3:30b-a3b

# 5. Create .env file
copy .env.example .env
```

### Running

```bash
# Start Ollama server (if not running)
ollama serve

# Run Gradio interface
python -m interface.gradio_app

# Or run API server
python -m interface.api
```

## 📁 Project Structure

```
MITS/
├── src/
│   ├── agents/          # Multi-agent components
│   ├── models/          # LLM clients and prompts
│   ├── data/            # Schemas and databases
│   ├── knowledge_tracing/  # LLMKT implementation
│   └── utils/           # Helper functions
├── interface/           # Gradio & FastAPI
├── training/            # Fine-tuning scripts
├── evaluation/          # Metrics and benchmarks
├── tests/               # Unit tests
└── data/                # Datasets and vector DB
```

## 📊 Metrics

| Metric | Target | Description |
|--------|--------|-------------|
| Success@10 | >60% | Tasks solved within 10 turns |
| Telling@10 | <15% | Sessions with direct answer |
| KT AUC | >0.75 | Knowledge tracking accuracy |

## 📚 References

- [SocraticLLM](https://arxiv.org/abs/2407.17349) - Socratic Method for Math Teaching
- [MathDial](https://github.com/eth-nlped/mathdial) - Tutoring Dialog Dataset
- [GenMentor](https://arxiv.org/abs/2501.15749) - Multi-agent ITS Framework

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.
