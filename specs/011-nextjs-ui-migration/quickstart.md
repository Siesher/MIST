# Quickstart: Next.js UI Migration

**Feature**: 011-nextjs-ui-migration
**Prerequisites**: Python 3.11+, Node.js 18+, Ollama running

## Project Setup

### 1. Clone and Checkout Branch

```bash
cd C:\Work\MITS
git checkout 011-nextjs-ui-migration
```

### 2. Backend Setup

```bash
# Create backend directory
mkdir -p backend/app

# Create virtual environment (optional, can use existing)
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install fastapi uvicorn python-jose websockets pydantic-settings

# Or use requirements.txt when created
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend

# Create Next.js project
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"

# Install additional dependencies
npm install zustand @tanstack/react-query katex
npm install -D @types/katex

# Install shadcn/ui
npx shadcn-ui@latest init
# Choose: TypeScript, Default style, CSS variables: Yes

# Add shadcn components
npx shadcn-ui@latest add button input card scroll-area dialog dropdown-menu avatar tooltip
```

### 4. Environment Configuration

**backend/.env**:
```env
OLLAMA_HOST=http://localhost:11434
DEBUG=true
CORS_ORIGINS=http://localhost:3000
```

**frontend/.env.local**:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## Development

### Start Backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

### Start Frontend

```bash
cd frontend
npm run dev
```

Frontend runs at: http://localhost:3000

### Verify Setup

1. **Check backend health**:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

2. **Open frontend**: http://localhost:3000

3. **Test WebSocket** (browser console):
   ```javascript
   const ws = new WebSocket('ws://localhost:8000/api/v1/ws/test-session');
   ws.onmessage = (e) => console.log(JSON.parse(e.data));
   ```

## Project Structure After Setup

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Settings from env
│   ├── dependencies.py      # DI container
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py    # Main router
│   │       ├── sessions.py
│   │       ├── chat.py
│   │       └── websocket.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── chat.py
│   └── services/
│       ├── __init__.py
│       └── orchestrator_service.py
├── requirements.txt
└── .env

frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── globals.css
│   │   └── chat/
│   │       └── [sessionId]/
│   │           └── page.tsx
│   ├── components/
│   │   ├── ui/              # shadcn components
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── Message.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── MathRenderer.tsx
│   │   └── layout/
│   │       └── Sidebar.tsx
│   ├── hooks/
│   │   ├── useChat.ts
│   │   └── useWebSocket.ts
│   ├── store/
│   │   └── chatStore.ts
│   ├── lib/
│   │   ├── api.ts
│   │   └── utils.ts
│   └── types/
│       └── api.ts
├── public/
├── package.json
├── tailwind.config.ts
├── next.config.js
└── .env.local
```

## Common Tasks

### Add New API Endpoint

1. Define schema in `backend/app/schemas/`
2. Add route in `backend/app/api/v1/`
3. Register in router
4. Add TypeScript type in `frontend/src/types/`
5. Add API function in `frontend/src/lib/api.ts`

### Add New UI Component

1. Create in `frontend/src/components/`
2. Export from component index
3. Use in page or other component

### Test Streaming

```bash
# Terminal 1: Start backend
cd backend && uvicorn app.main:app --reload

# Terminal 2: Test WebSocket with wscat
npm install -g wscat
wscat -c ws://localhost:8000/api/v1/ws/test-session
> {"type": "message", "content": "hello", "timestamp": 1706745600000}
```

## Troubleshooting

### "CORS error"
Check `CORS_ORIGINS` in backend `.env` includes frontend URL.

### "WebSocket connection failed"
1. Verify backend is running
2. Check session ID exists
3. Verify WS URL in frontend `.env.local`

### "Ollama unavailable"
```bash
# Check Ollama status
curl http://localhost:11434/api/version

# Start Ollama if needed
ollama serve
```

### "Module not found" (Python)
Ensure MITS `src/` is in Python path:
```python
# backend/app/main.py
import sys
sys.path.insert(0, '../')  # Add parent for src/ access
```

## Next Steps

1. Implement basic endpoints (see contracts/api.yaml)
2. Create chat components
3. Add WebSocket streaming
4. Style with Tailwind
5. Test end-to-end flow
