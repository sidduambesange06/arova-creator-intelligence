# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-01

### Added
- **Local Video Ingestion & Probe:** Non-destructive media probing via `ffprobe`, keyframe thumbnail extraction, and SHA-256 deduplication.
- **Audio Extraction & Speech ASR:** 16kHz mono audio extraction, content-aware visual scene cut detection (`PySceneDetect`), and offline speech transcription (`faster-whisper`) with deterministic fallback.
- **Visual-Text Dual Memory Engine:** Frame OCR extraction and fusion into sliding-window transcript chunks tagged with `[On-Screen Visual Text]`.
- **Two-Stage Hybrid Search:** Stage-1 Dense vector embeddings (ChromaDB + `all-MiniLM-L6-v2`) and Lexical BM25 (SQLite FTS5) merged via Reciprocal Rank Fusion ($k=60$), followed by Stage-2 Cross-Encoder re-ranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
- **Grounded Video Q&A Assistant:** Factual answer synthesis strictly tied to verified video passages with clickable timestamp citations `[mm:ss - mm:ss]`.
- **FastMCP STDIO Server:** 8 official read-only retrieval tools (`list_videos`, `get_video_metadata`, `search_video_content`, `search_transcripts`, `find_video_clips`, `summarize_video`, `get_video_chapters`, `get_media_library_stats`) with subclip export gated behind developer opt-in.
- **Arova Web Workstation UI:** Mastercraft dark workstation design with precision range scrubber, variable playback speeds, and synchronized multi-track timeline.
- **CLI Diagnostics & Demo:** `arova doctor` for non-destructive system health checks and `arova demo` for sub-1-second synthetic first-use workflow verification.
- **Thin Python SDK Wrapper:** Zero-dependency `ArovaClient` for REST API integration.
- **Governance & Legal Baseline:** Full Apache 2.0 license, `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md`.
