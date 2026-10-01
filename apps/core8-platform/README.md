# Core8-AI

Multi-agent AI platform for business automation — built with aerospace-grade precision.

## Stack
- **Backend:** Python 3.12 + FastAPI + WebSocket + SQLite
- **Frontend:** Next.js 15 + Tailwind + shadcn/ui
- **AI:** Anthropic Claude API (claude-sonnet-4-6)

## Structure
```
core8-ai/
├── backend/          # FastAPI server
│   ├── agents/       # Sub-agent implementations
│   ├── security/     # Auth, injection gate, log redaction
│   ├── tools/        # Tool registry & dispatcher
│   └── main.py       # App entry point
├── frontend/         # Next.js dashboard
└── docs/             # Architecture & runbooks
```

## Quick Start

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY and BEARER_TOKEN
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables
| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `BEARER_TOKEN` | Auth token for the API |
| `DEV_MODE` | `true` in development (localhost only) |
| `BIND_HOST` | Server bind address (default `127.0.0.1`) |
| `BIND_PORT` | Server port (default `8000`) |
