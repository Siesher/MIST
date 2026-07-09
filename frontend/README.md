# MITS Frontend

Next.js 14 frontend for the MITS (Math Intelligent Tutoring System) — a Socratic AI tutor
for STEM subjects (math, physics, chemistry, CS).

Built with: Next.js 14, TypeScript 5, Tailwind CSS, shadcn/ui, Zustand.
Real-time responses via WebSocket streaming from the backend.

## Requirements

- Node.js 18+
- MITS backend running on port 8000 (see `backend/`)

## Environment

Create `frontend/.env.local` with the following variables.
These are **base URLs only** — all paths (`/api/v1/...`) are appended by the code
(see `frontend/src/lib/api.ts`).

```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

For Docker or remote deployments replace `localhost` with the actual host.

## Commands

```bash
# Install dependencies
npm install

# Start development server (hot-reload)
npm run dev

# Production build
npm run build

# Type-check without emitting (CI)
npx tsc --noEmit
```

Development server starts at http://localhost:3000.

## Chat modes

- **chat** — direct LLM conversation
- **guided_learning** — full Socratic agent pipeline (planner + tutor + diagnostics)
- **task_generator** — on-demand STEM problem generation
