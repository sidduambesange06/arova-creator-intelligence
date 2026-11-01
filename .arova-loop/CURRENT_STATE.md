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
1. **Local Media Ingestion & Metadata:** Probe duration, dimensions, framerate, codecs via `ffprobe` (with ffmpeg stderr parsing fallback); SHA-256 deduplication.
2. **Keyframe Thumbnails & Streaming:** HTTP 206 Partial Content Range streaming.
3. **Scene Detection & ASR:** Content-aware scene cuts (`PySceneDetect`) and speech transcription (`faster-whisper`) preserving millisecond timestamps.
4. **Visual-Text Dual Memory:** OCR frame text fusion with `[On-Screen Visual Text]` annotation.
5. **Two-Stage Hybrid Search:** Stage-1 Dense vector search (ChromaDB + all-MiniLM-L6-v2) + SQLite FTS5 BM25 combined via Reciprocal Rank Fusion ($k=60$), followed by Stage-2 PyTorch Cross-Encoder re-ranking.
6. **Grounded Video Q&A:** Synthesize factual answers with exact timecode intervals `[mm:ss - mm:ss]`.
7. **Official FastMCP Server:** 8 read-only tools over local STDIO (exports gated behind developer opt-in; ADR-005).
8. **Hallmark Fullscreen Workstation:** 12-column dark workstation UI with precision scrubber, variable speeds, and multi-track synchronized timeline.
9. **Minimal CLI & SDK:** Diagnostic CLI (`arova doctor`, `arova demo`) and thin Python REST client wrapper (frozen scope: health, search, videos, ask).

### 1.4 Explicit Exclusions
- **No Commercial Creator OS / Molty AI Features:** Zero idea generators, script hook generators, creator tone memory, or brand deal CRM.
- **No Cloud Video Hosting or Cloud Ingestion:** 100% local processing; zero automatic video uploads.
- **No Night Shift Background Watcher:** Deferred as a gated research track post-Release 3.
- **No Unattended Agent Mutations:** Read-only MCP contract for agents.

---

## 2. Current Verified State

### 2.1 Codebase Health
- **Backend, CLI, MCP, Stress & Benchmark Tests:** 64 passed out of 64 unit/integration/stress tests (`pytest backend/tests mcp_server/tests -q`, 12.79s).
- **Frontend Tests:** 4 test suites passed (6 tests) (`vitest run`, 3.53s).
- **Production Web Build:** `tsc -b && vite build` succeeded (bundle size 202.57 KB, 0 errors).
- **Hardened Release Gate:** `scripts/release_gate.py` passed all 12 automated checks with zero automated failures.
- **Git Working Tree:** Branch `main`, tracking `origin/main`.

### 2.2 Active Services
- **Backend API:** FastAPI running locally on `http://127.0.0.1:8000` (loopback bound).
- **Frontend Workstation:** Vite running locally on `http://127.0.0.1:5173`.
- **MCP Server:** Available via `python -m mcp_server.server` over STDIO (8 read-only tools by default).
- **CLI & SDK:** Available via `python -m arova` and `from arova import ArovaClient` (`arova doctor`, `arova demo`, `ArovaClient` verified).

### 2.3 Phase 1 Sequential Backlog Status
- `TASK-006` (`arova doctor` diagnostic CLI): `DONE` (Verified by 10 unit tests)
- `TASK-007` (`arova demo` synthetic first-use flow): `DONE` (Verified by 4 unit/integration tests; completed in < 1s)
- `TASK-008` (Thin Python REST client wrapper): `DONE` (Verified by 4 unit tests; zero-dependency `ArovaClient`)
- `TASK-009` (Client setup matrices in `docs/INTEGRATIONS.md`): `DONE` (4-tier support policy and configurations verified; desktop GUI pending manual verification)
- `TASK-010` (Open-source governance: `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`): `DONE` (All files verified)
- `TASK-011` (Hardened release gate script `scripts/release_gate.py`): `DONE` (12/12 automated baseline and stress checks passed)

---

## 3. Dedicated Launch 01 Release Readiness Audit Status

| Dimension | Audit Status | Evidence & Summary |
|---|---|---|
| **Phase 1 Implementation** | **COMPLETE** | All backlog tasks (TASK-006 through TASK-011) implemented and verified. |
| **Automated Tests** | **PASSING** | 64 backend/CLI/MCP/stress/benchmark tests passing; 6 frontend Vitest tests passing; 0 regressions. |
| **Essential Security Audit** | **VERIFIED (8 Pillars)** | Parameterized SQL, path traversal boundary, safe subprocesses, prompt injection defanging, 8 read-only MCP tools, loopback binding (`127.0.0.1; static audit`), zero committed secrets/weights, and qualified CycloneDX SBOM. |
| **Stress & Resiliency** | **COMPLETE** | 500-video discovery/recovery test (non-indexing), 215 prompt-injection red-team cases, 100-query synthetic visual retrieval benchmark, and fault injection tests implemented and passing. |
| **Initial Open-Source Alpha** | **APPROVED (v0.1.0-alpha)** | All 12 automated checks pass (100% automated coverage); ready for developer preview testing. |
| **Beta Roadmap Gates** | **DEFERRED (v0.2.0-beta)** | 3 external non-developer physical installs, live Claude/Cursor desktop GUI QA, 500-video full ASR indexing, real-world video benchmark, and dynamic packet inspection deferred to Beta. |
| **Public Release Authorization** | **STRICTLY BLOCKED** | No remote push to GitHub or public registry publication without explicit user approval. |
