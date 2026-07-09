# ── Base stage ──────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libpango/libcairo/libgdk-pixbuf — системные библиотеки WeasyPrint (PDF-отчёты)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Бэкенд импортирует src/* (агенты, RAG, SymPy) — нужны ОБА requirements,
# иначе образ падает на первом обращении к LLM-пайплайну
COPY requirements.txt ./requirements-root.txt
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements-root.txt -r requirements.txt

# ── Dev stage ───────────────────────────────────────────────
FROM base AS dev

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Prod stage ──────────────────────────────────────────────
FROM base AS prod

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
