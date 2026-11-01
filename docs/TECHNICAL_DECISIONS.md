# Technical Decisions

Related notes: [[PROJECT_STATUS]] | [[architecture]] | [[DEVELOPMENT_LOG]] | [[KNOWN_ISSUES]] | [[FEATURE_STATUS]] | [[MCP_TOOLS]]

## ADR-001: Local-First Storage Stack (SQLite FTS5 + ChromaDB)
- **Context:** Developers evaluating the repository or running local MCP servers should not need Docker Compose with PostgreSQL, Redis, or cloud API keys just to index and search local videos.
- **Decision:** Use SQLite (with FTS5 for lexical search) alongside embedded ChromaDB for dense vectors, stored under `./data/`.
- **Consequences:** Zero-install local startup; single-process write concurrency is sufficient for a local developer desktop/workstation engine.

## ADR-002: Strict Open-Source / Commercial IP Boundary
- **Context:** `arova-creator-intelligence` is public under Apache 2.0 and powers media indexing/retrieval while keeping Arova Creator OS commercial workflows private.
- **Decision:** Expose only media probing, ASR transcription, scene detection, hybrid vector+FTS5 retrieval, cross-encoder re-ranking, evaluation benchmarks, and read-only MCP retrieval tools. Exclude all commercial features (idea/hook/script generators, brand deal CRM, tone memory).
- **Consequences:** Clean developer positioning as a local Video RAG & MCP engine.

## ADR-003: Self-Contained FFmpeg Fallback via `imageio-ffmpeg`
- **Context:** Windows/macOS developer laptops often do not have `ffmpeg` and `ffprobe` pre-installed on system `PATH`.
- **Decision:** Prefer `shutil.which("ffmpeg")` / `shutil.which("ffprobe")` when installed on system `PATH`, and automatically fall back to the bundled `imageio_ffmpeg.get_ffmpeg_exe()` binary for both metadata probing and frame/audio extraction.
- **Consequences:** Zero manual FFmpeg installation required to run tests or ingest local MP4/MOV/MKV/WebM videos.

## ADR-004: Visual-Text Dual Memory Engine
- **Context:** Technical videos contain critical information presented visually in slide titles, code snippets, and diagrams that is never spoken aloud.
- **Decision:** Extract on-screen text from keyframe thumbnails and fuse it directly into sliding-window transcript chunks tagged with `[On-Screen Visual Text]: ...`. Tag search matches with their channel (`speech`, `visual`, `multimodal`).
- **Consequences:** Unifies speech and visual slide text in both dense vector and lexical FTS5 retrieval.

## ADR-005: FastMCP Default Read-Only Isolation & Developer Opt-In for Exports
- **Context:** Open Source Spec v1.1 (§3.2, §15.3) dictates that AI agents in Launch 01 must only have read-only tools. The `export_video_clip` tool writes MP4 subclips to disk.
- **Decision:** Isolate the default MCP toolset to strictly the 8 read-only retrieval tools. Gate `export_video_clip` behind an explicit developer opt-in (`AROVA_ENABLE_MCP_EXPORTS=1` or `--enable-exports`).
- **Consequences:** Strictly enforces the read-only agent contract while preserving subclip slicing capability for explicit developer opt-in. (Implemented in commit `13dd684`).

## ADR-006: Canonical Task Numbering & Deliverable Separation for Launch 01
- **Context:** Early drafts assigned `TASK-010` to the automated release gate, while community governance documents (`NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` per Spec §10.2) were informal deliverables.
- **Decision:** Reconcile task IDs into a single canonical sequence:
  - `TASK-006`: `arova doctor` diagnostic CLI command (`WS-CLI`, `REQ-024`) — `NOT IMPLEMENTED`
  - `TASK-007`: `arova demo` synthetic first-use flow (`WS-CLI`, `REQ-025`, `REQ-032`) — `NOT IMPLEMENTED`
  - `TASK-008`: Thin Python client wrapper `arova-client` (`WS-CLI`, `REQ-023`) — `NOT IMPLEMENTED` (frozen scope: thin REST client only)
  - `TASK-009`: Tested client integration matrices in `docs/INTEGRATIONS.md` (`WS-DOC`, `REQ-033`) — `NOT IMPLEMENTED`
  - `TASK-010`: Open-source community governance files (`WS-DOC`, `REQ-031`) — `NOT IMPLEMENTED`
  - `TASK-011`: Automated release gate verification script (`WS-QA`, `REQ-029`) — `NOT IMPLEMENTED`
- **Consequences:** Provides exact 1:1 requirement traceability across all registers and eliminates ambiguity between release verification and community documentation.
