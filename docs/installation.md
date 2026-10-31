# Installation & Deployment Guide

Related notes: [[architecture]] | [[PROJECT_STATUS]] | [[mcp-guide]]

## Prerequisites

- **Python:** 3.11 or higher
- **Node.js:** 20.x or higher (with `npm`)
- **FFmpeg:** System binary recommended (`ffmpeg`, `ffprobe`); if not present on system `PATH`, Arova Creator Intelligence automatically falls back to bundled `imageio-ffmpeg` binaries.
- **Operating System:** Linux, macOS, or Windows 10/11.

---

## 1. Local Development Setup

### Backend (FastAPI + ML Engine)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/arova/arova-creator-intelligence.git
   cd arova-creator-intelligence
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Using Astral uv (recommended)
   uv venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -r backend/pyproject.toml --group dev
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

4. **Start the API backend:**
   ```bash
   # From root or backend/
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   The backend API will be live at `http://127.0.0.1:8000`. API docs available at `http://127.0.0.1:8000/docs`.

### Frontend (React + Vite + Tailwind)

1. **Install dependencies and launch dev server:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   The developer UI inspector will run at `http://localhost:5173`.

---

## 2. Docker Deployment

Deploy the fully self-contained engine (FastAPI + compiled SPA + SQLite + FFmpeg) using Docker Compose:

```bash
docker compose up --build -d
```

- Accessible at: `http://localhost:8000`
- Persistent video storage, transcripts, and embeddings are mounted at `./data`.
- Video files can be mounted read-only into `./media`.

---

## 3. Verification & Health Auditing

Verify your installation by running the comprehensive system health audit:

```bash
python scripts/system_health_audit.py
```
This runs 7 rigorous automated checks:
1. Documentation & Ledger Sync
2. Strict Apache 2.0 IP Boundary Check
3. Security & Path-Traversal Protection
4. SQLite & Schema Integrity
5. Backend Pytest Suite (21 tests)
6. Frontend Vitest Suite (6 tests) & Production Build
7. TinyFish Web Agent / Local Fallback Connector

