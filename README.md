# Arova Creator Intelligence

**The Local Video RAG & MCP Engine for AI Agents and Developers.**

> Index local video libraries into timestamped transcripts, visual scenes, and hybrid vector embeddings—accessible via REST API, Web Inspector, and Model Context Protocol (MCP).

Licensed under the [Apache License 2.0](./LICENSE).

---

## Core Capabilities

- **Local Video Ingestion & Metadata (`ffprobe` + `ffmpeg`):** SHA-256 deduplication, technical media probing, keyframe thumbnails, and HTTP 206 Range streaming.
- **Visual Scene Detection & ASR (`PySceneDetect` + `faster-whisper`):** Content-aware scene boundary detection and timestamp-accurate speech transcription (English, Hindi, Hinglish).
- **Two-Stage Hybrid Video RAG:**
  - *Stage 1:* Dense semantic vectors (`ChromaDB` + `all-MiniLM-L6-v2`) merged with lexical `SQLite FTS5` via Reciprocal Rank Fusion (RRF).
  - *Stage 2:* Local PyTorch Cross-Encoder re-ranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
- **ML Evaluation Harness:** Reproducible `MRR@10`, `NDCG@10`, `Recall@K`, and latency breakdown benchmarks.
- **Official Python MCP Server:** STDIO server exposing 8 read-only retrieval and inspection tools for Claude Desktop, Cursor, and Gemini Antigravity.

---

## Quick Start

### 1. Backend API (`FastAPI` + `uv`)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Run backend tests:
```bash
cd backend
uv run pytest
```

### 2. Web Inspector (`React` + `Vite` + `TypeScript`)

```bash
cd frontend
npm install
npm run dev
```

Run frontend tests & production build check:
```bash
cd frontend
npm test
npm run build
```

---

## Documentation & Engineering Brain (`docs/`)

- [System Architecture](./docs/architecture.md)
- [Project Status](./docs/PROJECT_STATUS.md)
- [Development Log](./docs/DEVELOPMENT_LOG.md)
- [Technical Decisions](./docs/TECHNICAL_DECISIONS.md)
- [Known Issues](./docs/KNOWN_ISSUES.md)

