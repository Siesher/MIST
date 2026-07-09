# MITS Quick Start

## Требования

- Python 3.11+
- Node.js 18+ (для фронтенда)
- llama-server или llama-swap (локальный GGUF-сервер, конфигурация хранится вне репозитория)
- 16 GB RAM рекомендуется

---

## 1. Клонирование и зависимости

```bash
git clone https://github.com/Siesher/MITS.git
cd MITS

# Python-зависимости (корень + бэкенд)
pip install -r requirements.txt -r backend/requirements.txt
```

---

## 2. LLM-сервер (llama-swap / llama-server)

Модели раздаются локальным GGUF-сервером на порту **:8090**.
Конфигурация llama-swap (пути к GGUF-файлам, профили моделей) хранится вне репозитория — в вашей локальной установке llama-swap.

Убедитесь, что сервер запущен и отвечает перед стартом бэкенда:

```bash
curl http://localhost:8090/v1/models
```

---

## 3. Бэкенд

Запускать из **корня репозитория**:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Smoke-check:

```bash
curl http://localhost:8000/api/v1/health
```

---

## 4. Фронтенд

```bash
cd frontend
npm install
npm run dev
```

Открыть в браузере: **http://localhost:3000**

---

## 5. Переменные окружения (фронтенд)

Создайте `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## 6. Тесты

Запускать из **корня репозитория**:

```bash
pytest
```

---

## Стек в двух словах

| Компонент | Адрес | Описание |
|-----------|-------|----------|
| llama-swap / llama-server | :8090 | GGUF Q4_K_M, Qwen3.5-9B fine-tuned |
| FastAPI backend | :8000 | REST + WebSocket, агентный пайплайн |
| Next.js frontend | :3000 | UI (shadcn/ui + Zustand) |
