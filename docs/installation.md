# Installation & Deployment Guide

## Prerequisites

- **Python:** 3.11 or higher
- **Node.js:** 20.x or higher (Node.js 24 LTS recommended, with `npm`)
- **FFmpeg:** System binary recommended (`ffmpeg`, `ffprobe`); if not present on system `PATH`, Arova Creator Intelligence automatically falls back to bundled `imageio-ffmpeg` binaries.
- **Operating System:** Linux, macOS, or Windows 10/11.

---

## 1. Local Development Setup

### Backend (FastAPI + ML Engine)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sidduambesange06/arova-creator-intelligence.git
   cd arova-creator-intelligence
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Using Astral uv (recommended)
   uv sync --project backend --group dev --locked
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   ```

4. **Verify environment health:**
   ```bash
   python -m arova doctor
   ```

5. **Start the API backend:**
   ```bash
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
   The web workspace will run at `http://localhost:5173`.

---

## 2. Docker Deployment

Deploy the engine using Docker Compose:

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
This runs 7 automated checks:
1. Documentation Integrity
2. Strict Apache 2.0 IP Boundary Check
3. Security & Path-Traversal Protection
4. SQLite & Schema Integrity
5. Backend & MCP Pytest Suite
6. Frontend Vitest Suite & Production Build
7. FastMCP Server Contract & Tools
