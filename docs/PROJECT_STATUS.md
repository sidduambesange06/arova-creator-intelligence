# Project Status

Related notes: [[architecture]] | [[DEVELOPMENT_LOG]] | [[TECHNICAL_DECISIONS]] | [[KNOWN_ISSUES]]

## Current Milestone: Milestone 1 — Foundation, Obsidian Brain & Connectivity (COMPLETED)

### Milestone 1 Checklist
- [x] **Feature 1.1 (Obsidian Brain & Repo Root):** `.gitignore`, `.env.example`, `LICENSE` (Apache 2.0), `README.md`, `docs/architecture.md`, and Obsidian brain notes initialized.
- [x] **Feature 1.2 (Backend Core):** FastAPI (`app/main.py`), Pydantic Settings (`app/core/config.py`), structured logging (`app/core/logging.py`), CORS, and `GET /api/v1/health`.
- [x] **Feature 1.3 (Frontend Shell):** React + TypeScript + Vite + Tailwind CSS developer inspector shell with live health indicator connected to `GET /api/v1/health`.
- [x] **Feature 1.4 (Verification & Ponytail Audit):** `pytest` on `backend/tests/test_health.py` (`2/2` passed) and frontend `vitest` (`2/2` passed) + `npm run build` verification passed.

### Upcoming Milestones
- [ ] **Milestone 2:** Media Ingestion, FFmpeg Pipeline & Video Inspector UI (Features 2.1–2.4)
  - [x] **Feature 2.1 (SQLite + SQLAlchemy Schema):** `Video`, `Collection`, `CollectionVideo`, `Transcript`, `TranscriptSegment`, `VideoScene`, `EmbeddingRecord`, `VideoSummary`, and `ProcessingJob` models + Alembic migration (`0001_initial_schema`).
  - [ ] **Feature 2.2 (Safe File & FFmpeg Probing):** Path-traversal-safe local file validator, SHA-256 deduplication hash, `ffprobe`/`ffmpeg` metadata extractor, and keyframe thumbnail generator.
  - [ ] **Feature 2.3 (Import, Index Delete & HTTP Range Streaming API):** `POST /api/v1/videos/import`, `GET /api/v1/videos`, `DELETE /api/v1/videos/{id}/index`, `GET /api/v1/videos/{id}/stream` (HTTP 206 Range), and Collection endpoints.
  - [ ] **Feature 2.4 (Media Library & Video Player UI):** Media Library grid, Import modal, Collection filter, and HTML5 Video Player with timestamp jump support.
- [ ] **Milestone 3:** Whisper ASR, PySceneDetect & Background Job Runner (Features 3.1–3.4)
- [ ] **Milestone 4:** Two-Stage Hybrid RAG, Cross-Encoder ML Re-Ranker & Eval Harness (Features 4.1–4.5)
- [ ] **Milestone 5:** Official MCP Server, Docker & Public v1.0 Release (Features 5.1–5.3)

