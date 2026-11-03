# Arova Creator Intelligence — Product Scope & Capability Baseline

**Document Version:** `1.0.0`  
**Licence:** Apache 2.0 (Open-Source)  
**Maintained by:** Arova Open-Source Project  
**Repository:** [github.com/sidduambesange06/arova-creator-intelligence](https://github.com/sidduambesange06/arova-creator-intelligence)  

---

## 1. What Arova Creator Intelligence Is

Arova Creator Intelligence is an open-source, local-first video intelligence and persistent creator memory engine.

Its primary mission is to turn local video libraries into a searchable, queryable knowledge base, exposing timestamped facts, spoken dialogue, and visual scene context to AI agents and developer applications without uploading private video footage to cloud servers.

The system is designed for developers, researchers, AI agent builders, and technical content creators who require local-first privacy, timecode receipts, and open API/MCP interfaces.

---

## 2. Current Verified Capabilities (Alpha v0.1.0)

The engine provides the following functional capabilities, verified by automated unit and integration tests:

### 2.1 Local Media Ingestion & Metadata Probing
- **Safe Path Traversal Boundaries:** File system probing is strictly restricted to user-approved directories (`ALLOWED_MEDIA_ROOTS`). Traversal patterns (`../`, symlink escapes, absolute paths outside roots) are rejected with HTTP 400.
- **Source Media Immutability:** Source video files are treated as strictly read-only. Indexing, probing, thumbnail creation, and index deletion operations never modify or overwrite source media files.
- **Format Probing:** Automatic extraction of container format, duration, dimensions, framerate, video codecs (H.264, HEVC, VP9, AV1), and audio stream specifications via bundled FFmpeg.
- **SHA-256 Deduplication:** Computes an initial SHA-256 hash over the first 8 MB of video content to prevent duplicate indexing and ensure idempotent library imports.
- **HTTP 206 Streaming:** Supports partial content range requests (`Accept-Ranges: bytes`) for seeking in HTML5 video players.

### 2.2 Content-Aware Scene Detection & Thumbnails
- **Scene Cut Detection:** Content-aware boundary detection via FFmpeg filtergraph (`select='gt(scene,0.27)'`).
- **Midpoint Scrubbing Thumbnails:** Automatically generates JPEG thumbnails at scene midpoints for visual timeline navigation.
- **Relational Persistence:** Scene start, end, and duration boundaries are stored in SQLite.

### 2.3 Speech Transcription (ASR) Interface
- **Audio Extraction:** High-speed extraction of 16kHz mono 16-bit PCM WAV audio from source containers.
- **Transcription Abstraction:** Pluggable `TranscriptionProvider` protocol with timestamp-preserving segment tracking.
- **Execution Modes:**
  - *Neural Whisper Mode:* Supported via `faster-whisper` (CTranslate2 INT8/FP16) when the package and model weights are installed.
  - *Deterministic Acoustic Fallback:* When neural model weights are not present, the engine automatically falls back to deterministic WAV frame energy windowing (4.0s segments) to allow end-to-end pipeline execution without network dependencies.

### 2.4 Timestamp-Preserving Hybrid Indexing & Retrieval
- **Multimodal Chunking:** Sliding-window passage creation (32-second windows with 8-second step intervals) fusing spoken transcripts and on-screen scene context.
- **Dual-Store Indexing:**
  - *Lexical Search:* Native SQLite FTS5 BM25 virtual table (`transcript_chunks_fts`) for exact keyword and dialogue lookup.
  - *Vector Search:* Dense vector cosine similarity over chunk embeddings (persisted locally on disk).
- **Two-Stage Re-Ranking:** Stage-1 Reciprocal Rank Fusion ($k=60$) combining dense vector similarity with BM25 scores, followed by Stage-2 Cross-Encoder re-ranking.

### 2.5 Grounded Video Q&A Assistant
- **Factual Question Answering:** Synthesizes direct answers citing exact timestamp intervals (`[mm:ss - mm:ss]`).
- **Anti-Hallucination Design:** Questions targeting unmentioned topics return explicit negative disclosures rather than fabricating plausible answers.

### 2.6 Model Context Protocol (FastMCP) Integration
- **Default Read-Only Contract:** Exposes 8 read-only retrieval tools to AI agent environments (Claude Desktop, Cursor IDE, Copilot):
  1. `list_videos`: Discover indexed media.
  2. `get_video_metadata`: Technical specs and dimensions.
  3. `search_video_content`: Hybrid semantic search with timecode receipts.
  4. `search_transcripts`: Fast lexical keyword search across spoken segments.
  5. `find_video_clips`: Timestamped clip intervals matching duration constraints.
  6. `summarize_video`: Grounded factual video summaries.
  7. `get_video_chapters`: Chronological AI chapter markers.
  8. `get_media_library_stats`: Aggregated library metrics.
- **Gated Mutation Boundary:** Potentially destructive operations or disk exports (`export_video_clip`) are excluded from default registration and require explicit developer opt-in (`ALLOW_MCP_MUTATIONS=true`).

### 2.7 Developer Workstation & Diagnostics
- **CLI Diagnostics:** `arova doctor` validates Python version, bundled FFmpeg binary, SQLite WAL mode, disk space, and MCP readiness without modifying system state.
- **First-Use Synthetic Demo:** `arova demo` validates the end-to-end pipeline in $< 1\text{ second}$ using a generated synthetic test fixture.
- **Python Client SDK:** Zero-dependency `ArovaClient` for programmatic interaction.
- **Fullscreen Developer UI:** 12-column dark workstation UI (`#060911`) featuring custom precision scrubber, variable speed playback, and synchronized multi-track timeline.

---

## 3. Privacy & Network Security Baseline

Arova Creator Intelligence adheres to a strict privacy-first architecture:
1. **Localhost Binding by Default:** All backend services bind exclusively to loopback (`127.0.0.1`).
2. **Zero Telemetry:** The engine contains zero analytics tracking, zero usage beacons, and zero telemetry reporting.
3. **Zero Silent Cloud Fallbacks:** Processing never silently falls back to external cloud APIs without explicit user configuration.
4. **Untrusted Data Sanitization:** All media-derived text (transcripts, OCR, titles, metadata) is treated as untrusted and defanged prior to LLM prompt injection or query construction.

---

## 4. Current Limitations & Known Boundaries

To ensure complete transparency, the following limitations are present in the current release:

1. **Model Weights Deployment:**
   The default installation environment does not package heavy pre-trained neural model weights. When dependencies such as `faster-whisper` or `sentence-transformers` are offline, the engine transparently executes deterministic local fallbacks.
2. **Keyframe OCR Extraction:**
   Visual text extraction currently operates via heuristic template matching. Full scene text detection on slides and burned-in subtitles is pending local ONNX OCR model integration.
3. **Thumbnail Generation Overhead:**
   Scene midpoint thumbnails are currently generated via sequential FFmpeg subprocess invocations. On long videos with many scenes, thumbnail extraction constitutes the primary pipeline bottleneck.
4. **Single-Node Execution:**
   The engine is designed as a single-node developer tool and does not run as a distributed cluster.

---

## 5. Explicit Exclusions (What This Engine Is Not)

Arova Creator Intelligence is an open-source video intelligence engine, not a video editing suite or commercial content studio. The following capabilities are explicitly out of scope for this repository:
- **No Non-Linear Video Editor (NLE):** The project does not provide multi-track timeline video editing, audio mixing, color grading, or transitions.
- **No Commercial Idea Generators or CRM:** Commercial features such as hook/script generators, creator tone memory, and brand deal CRM belong to separate commercial products and will never be placed in this repository.
- **No Cloud Video Hosting:** The engine does not store, host, or stream media from cloud servers.

