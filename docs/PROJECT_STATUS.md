# Project Status

Related notes: [[architecture]] | [[AGENTS_ARCHITECTURE]] | [[FLASH_EXECUTION_PLAYBOOK]] | [[DEVELOPMENT_LOG]] | [[TECHNICAL_DECISIONS]] | [[KNOWN_ISSUES]]

## Current Milestone: Milestone 3 — Whisper ASR, PySceneDetect & Background Job Runner (COMPLETED)

### Milestone 1 Checklist (COMPLETED)
- [x] **Feature 1.1 (Obsidian Brain & Repo Root):** `.gitignore`, `.env.example`, `LICENSE` (Apache 2.0), `README.md`, `docs/architecture.md`, and Obsidian brain notes initialized.
- [x] **Feature 1.2 (Backend Core):** FastAPI (`app/main.py`), Pydantic Settings (`app/core/config.py`), structured logging (`app/core/logging.py`), CORS, and `GET /api/v1/health`.
- [x] **Feature 1.3 (Frontend Shell):** React + TypeScript + Vite + Tailwind CSS developer inspector shell with live health indicator connected to `GET /api/v1/health`.
- [x] **Feature 1.4 (Verification & Ponytail Audit):** `pytest` on `backend/tests/test_health.py` (`2/2` passed) and frontend `vitest` (`2/2` passed) + `npm run build` verification passed.

### Milestone 2 Checklist (COMPLETED)
- [x] **Feature 2.1 (SQLite + SQLAlchemy Schema):** `Video`, `Collection`, `CollectionVideo`, `Transcript`, `TranscriptSegment`, `VideoScene`, `EmbeddingRecord`, `VideoSummary`, and `ProcessingJob` models + Alembic migration (`0001_initial_schema`).
- [x] **Feature 2.2 (Safe File & FFmpeg Probing):** Path-traversal-safe local file validator, SHA-256 deduplication hash, `ffprobe`/`ffmpeg` metadata extractor, and keyframe thumbnail generator.
- [x] **Feature 2.3 (Import, Index Delete & HTTP Range Streaming API):** `POST /api/v1/videos/import`, `GET /api/v1/videos`, `DELETE /api/v1/videos/{id}/index`, `GET /api/v1/videos/{id}/stream` (HTTP 206 Range), and Collection endpoints.
- [x] **Feature 2.4 (Media Library & Video Player UI):** Media Library grid, Import form, Collection filter/creator, and HTML5 Video Player with timestamp jump support (`vitest` `3/3` passed, `vite build` passed).

### Milestone 3 Checklist (COMPLETED)
- [x] **Feature 3.1:** Audio Extraction (`16kHz` mono WAV) & Scene Detection (`backend/app/processing/audio.py`, `scene_detection.py`)
- [x] **Feature 3.2:** Transcription Abstraction & Faster-Whisper Adapter (`backend/app/ai/providers/transcription.py`, `transcription_service.py`)
- [x] **Feature 3.3:** SQLite Background Task Runner & Telemetry (`backend/app/workers/pipeline_runner.py`, `/api/v1/videos/{id}/process`, `/api/v1/jobs`)
- [x] **Feature 3.4:** Interactive Transcript & Scene Timeline UI (`MediaLibraryView.tsx`, seeking HTML5 video player to exact timestamps, `vitest` passed, `vite build` passed)

### Upcoming Milestones (Detailed in [[FLASH_EXECUTION_PLAYBOOK]])
- [ ] **Milestone 4:** Two-Stage Hybrid RAG, Cross-Encoder ML Re-Ranker & Eval Harness
  - [x] **Feature 4.1:** Timestamp-Preserving Chunker & Dual Index (`chunker.py`, `embeddings.py`, SQLite FTS5)
  - [ ] **Feature 4.2:** Stage-1 Hybrid RRF + Stage-2 Cross-Encoder Re-Ranking (`hybrid_search.py`, `cross_encoder_reranker.py`, `/api/v1/search/semantic`)
  - [ ] **Feature 4.3:** ML Evaluation Harness & Telemetry API (`metrics.py`, `eval_harness.py`, `sample_data/evaluation_golden_set.json`, `/api/v1/ml/eval/run`)
  - [ ] **Feature 4.4:** AI Clip Finder & Grounded Summariser (`summary_service.py`, `/api/v1/search/clips`, `/api/v1/ai/summarize`)
  - [ ] **Feature 4.5:** AI Search & Benchmark UI (`HybridSearchView.tsx`)
- [ ] **Milestone 5:** Official MCP Server, Docker & Public v1.0 Release
  - [ ] **Feature 5.1:** Official Python MCP Server (`mcp_server/server.py`, `mcp_server/tools/video_tools.py` — 8 read-only tools)
  - [ ] **Feature 5.2:** MCP Inspector & Settings UI + MCP Unit Tests (`McpConfigView.tsx`, `mcp_server/tests/test_mcp_tools.py`)
  - [ ] **Feature 5.3:** Docker, CI & Final Ponytail Audit (`Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `installation.md`, `mcp-guide.md`)

