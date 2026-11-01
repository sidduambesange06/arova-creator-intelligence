# Arova Creator Intelligence — Project Charter & Current State

**Operational Control Document:** `.arova-loop/CURRENT_STATE.md`  
**Date of Audit:** 2026-11-01  
**Lead Engineer / Autonomous Coordinator:** Antigravity IDE  

---

## 1. Project Charter

### 1.1 Purpose
Arova Creator Intelligence is an open-source, local-first video intelligence engine that makes local video libraries searchable and exposes timestamped evidence to AI agents and developer applications.

### 1.2 Target Users
- **Developers & AI Engineers:** Connecting local media to LLMs, autonomous agents, and RAG pipelines via open standards.
- **AI Agent Builders:** Claude, Cursor, Antigravity, and Copilot users seeking verified video facts with timecode receipts.
- **Technical Content Creators & Researchers:** Users needing precise navigation through technical lectures, recordings, and tutorials without cloud uploads.

### 1.3 Approved Launch 01 Scope
1. **Local Media Ingestion & Metadata:** Probe duration, dimensions, framerate, codecs via `ffprobe`; SHA-256 deduplication.
2. **Keyframe Thumbnails & Streaming:** HTTP 206 Partial Content Range streaming.
3. **Scene Detection & ASR:** Content-aware scene cuts (`PySceneDetect`) and speech transcription (`faster-whisper`) preserving millisecond timestamps.
4. **Visual-Text Dual Memory:** OCR frame text fusion with `[On-Screen Visual Text]` annotation.
5. **Two-Stage Hybrid Search:** Stage-1 Dense vector search (ChromaDB + all-MiniLM-L6-v2) + SQLite FTS5 BM25 combined via Reciprocal Rank Fusion ($k=60$), followed by Stage-2 PyTorch Cross-Encoder re-ranking.
6. **Grounded Video Q&A:** Synthesize factual answers with exact timecode intervals `[mm:ss - mm:ss]`.
7. **Official FastMCP Server:** 8 read-only tools over local STDIO.
8. **Hallmark Fullscreen Workstation:** 12-column dark workstation UI with precision scrubber, variable speeds, and multi-track synchronized timeline.
9. **Minimal CLI & SDK:** Diagnostic CLI (`arova doctor`, `arova demo`) and thin Python REST client wrapper.

### 1.4 Explicit Exclusions
- **No Commercial Creator OS / Molty AI Features:** No idea generators, script hook generators, creator tone memory, or brand deal CRM.
- **No Cloud Video Hosting or Cloud Ingestion:** 100% local processing; zero automatic video uploads.
- **No Night Shift Background Watcher:** Deferred as a gated research track post-Release 3.
- **No Unattended Agent Mutations:** Read-only MCP contract for agents.

---

## 2. Current Verified State

### 2.1 Codebase Health
- **Backend Tests:** 28 passed out of 28 unit/integration tests (`pytest backend/tests -v`, 5.00s).
- **Frontend Tests:** 4 test suites passed (6 tests) (`vitest run`, 6.81s).
- **Production Web Build:** `tsc -b && vite build` succeeded (bundle size 202.57 KB, 0 errors).
- **System Health Audit:** `scripts/system_health_audit.py` passed with status `HEALTHY` (7/7 checks passed).
- **Git Working Tree:** Branch `main`, tracking `origin/main`.

### 2.2 Active Services
- **Backend API:** FastAPI running locally on `http://127.0.0.1:8000` (loopback bound).
- **Frontend Workstation:** Vite running locally on `http://127.0.0.1:5173`.
- **MCP Server:** Available via `python -m mcp_server.server` over STDIO.

