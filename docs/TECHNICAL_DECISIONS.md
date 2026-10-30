# Technical Decisions

Related notes: [[PROJECT_STATUS]] | [[architecture]] | [[DEVELOPMENT_LOG]] | [[KNOWN_ISSUES]]

## ADR-001: Local-First Storage Stack (SQLite FTS5 + ChromaDB)
- **Context:** Developers evaluating the repository or running local MCP servers should not need Docker Compose with PostgreSQL, Redis, or cloud API keys just to index and search local videos.
- **Decision:** Use SQLite (with FTS5 for lexical search) alongside embedded ChromaDB for dense vectors, stored under `./data/`.
- **Consequences:** Zero-install local startup; single-process write concurrency is sufficient for a local developer desktop/workstation engine.

## ADR-002: Strict Open-Source / Commercial IP Boundary
- **Context:** `arova-creator-intelligence` is public under Apache 2.0 and powers media indexing/retrieval while keeping Arova Creator OS commercial workflows private.
- **Decision:** Expose only media probing, ASR transcription, scene detection, hybrid vector+FTS5 retrieval, cross-encoder re-ranking, evaluation benchmarks, and read-only MCP retrieval tools. Exclude all influencer SaaS features (idea/hook/script generators, brand deal CRM, tone memory).
- **Consequences:** Clean developer positioning as a local Video RAG & MCP engine.

## ADR-003: Self-Contained FFmpeg Fallback via `imageio-ffmpeg`
- **Context:** Windows/macOS developer laptops often do not have `ffmpeg` and `ffprobe` pre-installed on system `PATH`.
- **Decision:** Prefer `shutil.which("ffmpeg")` / `shutil.which("ffprobe")` when installed on system `PATH`, and automatically fall back to the bundled `imageio_ffmpeg.get_ffmpeg_exe()` binary for both metadata probing (`ffmpeg -i` stderr parser when `ffprobe` is absent) and frame/audio extraction.
- **Consequences:** Zero manual FFmpeg installation required to run tests or ingest local MP4/MOV/MKV/WebM videos.

