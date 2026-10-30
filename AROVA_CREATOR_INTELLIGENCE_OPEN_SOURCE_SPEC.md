# AROVA CREATOR INTELLIGENCE (OPEN-SOURCE ENGINE)
**Master Product Requirements, Technical Architecture & Development Roadmap (Updated — IP-Safe & Developer-Viral Edition)**

- **Project:** Arova Creator Intelligence
- **Repository:** `arova-solutions/arova-creator-intelligence` (Public)
- **Organisation:** Arova Solutions
- **Project Type:** Open-source multimodal video indexing, semantic search & MCP engine
- **Licence:** Apache License 2.0
- **Development Environment:** Gemini Antigravity
- **Primary Languages:** Python and TypeScript
- **Target Users:** AI developers, MCP builders, software engineers, researchers, and technical creators

---

## 0. STRATEGIC BOUNDARY (WHY THIS REPO EXISTS & WHAT IT NEVER LEAKS)

This repository serves two goals simultaneously:
1. **Internship / Engineering Proof & Open-Source Virality:** Demonstrate production-grade AI systems engineering (FFmpeg media pipelines, Faster-Whisper transcription, PySceneDetect, Hybrid Vector + FTS5 RAG, Recall@K evaluation benchmarks, and an official MCP Server) that any developer or hiring manager can run locally in 2 minutes.
2. **Core Engine for Arova Solutions (Zero Commercial IP Leak):** Act as the open-source multimodal indexing engine underneath Arova Solutions, while keeping **100% of Arova Creator OS's commercial business logic private**.

### Strict Open-Source Secrecy Rules (Never Implement Here)
To protect the commercial moat of **Arova Creator OS (and Molty AI)** so no developer or competitor can clone your influencer SaaS from this public repo:
- **NO** Content Idea Generators, Hook Generators, or Viral Topic Predictors.
- **NO** Script Generators, B-Roll Script Matchers, or Creator Tone/Style Memory.
- **NO** Brand Deal CRM, Sponsor Brief Checkers, Campaign Deliverables, or Client Approval Links.
- **Positioning:** Frame this project strictly as **"The Local Video RAG & MCP Engine for AI Agents and Developers"** (similar to how Whisper, Chroma, or FFmpeg are developer primitives—not an influencer business app).

---

## 1. PROJECT VISION

Build a local-first, open-source video intelligence engine and Model Context Protocol (MCP) server that turns any local video folder into a timestamp-searchable knowledge base for humans and AI agents (Claude Desktop, Cursor, Gemini Antigravity, custom agents).

### Core Value Proposition
> *"Index local video libraries into timestamped transcripts, visual scenes, and hybrid vector embeddings—accessible via REST API, Web Inspector, and MCP."*

A developer or user can point the engine at a local folder of videos and ask:
- *"Find the exact timestamp where we discussed vector database indexing."*
- *"Find clips between 15 and 60 seconds where a terminal demo or product intro happens."*
- *"Summarise this 45-minute recording into timestamped chapters."*
- *"Search across 50 local videos for every mention of 'rate limiting' with surrounding context."*

---

## 2. PROJECT OBJECTIVES

1. **Zero-Friction Developer Adoption (Viral Loop):** Run locally with SQLite + ChromaDB + Faster-Whisper using a single command—no PostgreSQL, Redis, or paid cloud account required to start.
2. **Standout AI Systems Portfolio (Recruiter Magnet):** Showcase hybrid retrieval (Vector + Keyword FTS), timestamp-preserving chunking, structured LLM outputs, MCP server implementation, and reproducible Recall@K evaluation metrics.
3. **Reusable Core Package:** Expose clean Python services (`backend/app/services`) that can be imported directly by internal Arova Solutions commercial products without duplicating media pipeline code.
4. **Full-Stack Engineering Quality:** FastAPI + SQLAlchemy + Pydantic v2 backend, React + TypeScript + Tailwind + shadcn/ui web inspector, Pytest/Vitest suites, Docker, and GitHub Actions CI.

---

## 3. PRODUCT FEATURES & PRIORITY TIERS

### P0 — Mandatory MVP Features (Ship This First)

#### A. Video Library & Collection Management
- Import individual video files or scan a selected local directory (`MP4`, `MOV`, `MKV`, `WebM`).
- Extract technical metadata via `ffprobe` (duration, resolution, FPS, video/audio codecs, file size, SHA-256 file hash for deduplication).
- Generate contact-sheet/keyframe thumbnails via `ffmpeg`.
- Organise indexed videos into logical **Collections**.
- Track per-video processing state (`pending`, `processing`, `completed`, `failed`).
- **Safe Index Removal:** Deleting a video from the index removes database/vector records and generated thumbnails, **never** the user's original source video file.

#### B. Video Processing Pipeline
- Audio track extraction and normalisation (`16kHz` mono WAV for optimal ASR).
- Visual scene boundary detection using `PySceneDetect` (content-aware detector with configurable threshold).
- Each detected `VideoScene` records `start_time`, `end_time`, duration, and a representative midpoint thumbnail.
- Lightweight background execution using FastAPI background worker threads backed by SQLite `ProcessingJob` state (no Redis/Celery required for local MVP).

#### C. Speech Transcription Abstraction
- Pluggable `TranscriptionProvider` interface:
  - **Default Local:** `faster-whisper` (`base` / `small` / `medium` models, CTranslate2 int8/fp16 quantisation).
  - **Optional Cloud Adapter:** OpenAI Whisper / Gemini Audio API via user-supplied API key.
- Supports English, Hindi, and Hinglish (Hindi-English code-switching).
- Stores full transcripts plus fine-grained `TranscriptSegment` rows (`start_time`, `end_time`, `text`, `confidence`).

#### D. Hybrid Timestamped Video Search (Core Technical Differentiator)
- **Timestamp-Aware Chunking:** Group adjacent transcript segments into overlapping semantic windows (e.g., 20–45 second windows) while preserving exact `start_time` and `end_time` boundaries.
- **Hybrid Retrieval:**
  1. **Dense Semantic Search:** ChromaDB vector similarity using `sentence-transformers` (`all-MiniLM-L6-v2` or `BAAI/bge-small-en-v1.5` locally) or cloud embeddings.
  2. **Lexical Keyword Search:** SQLite FTS5 full-text search for exact technical terms, names, and acronyms.
  3. **Reciprocal Rank Fusion (RRF):** Merge semantic and lexical scores to rank timestamped segments accurately.
- Returns source `video_id`, filename, exact `[start_time, end_time]`, matching transcript snippet, scene thumbnail, and relevance score.

#### E. ML Re-ranking & Cross-Encoder Verification (The ML Engineer Component)
To solve the classic retrieval problem where bi-encoder vector similarity matches broad context but misses exact semantic nuances:
- **Bi-Encoder + Cross-Encoder Two-Stage Pipeline:**
  1. *Stage 1 (Retrieval):* Hybrid Dense Vector + FTS5 retrieves top-$K$ candidates ($K=20$).
  2. *Stage 2 (ML Re-ranking):* A local PyTorch Cross-Encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2` via HuggingFace `sentence-transformers`) scores `(query, transcript_window)` pairs jointly via full cross-attention.
- **ML Evaluation Harness:** Benchmarks Stage 1 vs. Stage 2 retrieval using standard ranking metrics:
  - **Mean Reciprocal Rank (MRR@10)**
  - **Normalized Discounted Cumulative Gain (NDCG@10)**
  - **Recall@K ($K \in \{1, 3, 5, 10\}$)**
  - Latency impact breakdown (Bi-encoder lookup vs. Cross-encoder re-ranking pass in milliseconds).
- *Why this cracks ML Engineer interviews:* Demonstrates understanding of the fundamental bi-encoder vs. cross-encoder trade-off (speed vs. accuracy), PyTorch inference latency optimization, and formal Information Retrieval (IR) ranking metrics.

#### F. AI Clip Finder & Factual Video Summarisation
- **AI Clip Finder:** Given a natural-language description (e.g., *"Find a 30-second segment explaining the database schema"*), retrieve top candidate windows and return exact start/end timestamps, transcript, and relevance rationale without modifying source files.
- **Factual Video Summarisation & Chapters:** Generate structured summaries, key takeaways, and timestamped chapter markers (`[{"start_time": 0.0, "title": "..."}]`) grounded strictly in the transcript with source citations.

#### G. Official MCP Server (`mcp_server`)
Built with the official Python `mcp` SDK over STDIO (compatible with Claude Desktop, Cursor, Windsurf, and Gemini Antigravity).
Exposes **8 read-only / retrieval tools** (zero commercial workflow leakage):
1. `list_videos` — List indexed videos with optional collection/status filters.
2. `get_video_metadata` — Inspect technical metadata, scenes, and processing status for a video.
3. `search_video_content` — Run hybrid semantic + keyword search across all videos with timestamp results.
4. `search_transcripts` — Exact/fuzzy lexical search across transcript segments.
5. `find_video_clips` — Locate specific timestamp ranges matching a natural-language description and optional duration bound.
6. `summarize_video` — Retrieve or generate a grounded summary and key points for a video.
7. `get_video_chapters` — Retrieve timestamped chapter markers and scene boundaries.
8. `get_media_library_stats` — Total videos, indexed duration, scene counts, and index health.

---

### P1 — Post-MVP Enhancements
- Optional vision-model keyframe captioning (`VideoScene.description`) for silent B-roll visual search.
- Search filters by collection, resolution, duration range, and date imported.
- Duplicate/near-duplicate video detection via perceptual frame hashing.
- MCP Streamable HTTP transport for remote agent connections.

### P2 — Future Possibilities (Out of Scope for v1.0)
- Automated FFmpeg clip export (`ffmpeg -ss ... -to ... -c copy`).
- Multimodal native video embeddings.
- Optional Celery + Redis distributed worker profile for large team servers.

---

## 4. TECHNOLOGY STACK (LOCAL-FIRST & LOW-FRICTION)

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend** | React 18 + TypeScript + Vite | Fast developer inspector UI |
| **Styling** | Tailwind CSS + shadcn/ui | Clean, minimal dark/light developer console |
| **Backend API** | Python 3.11+ + FastAPI + Pydantic v2 | Async REST API + automatic OpenAPI docs |
| **Database** | SQLite (with FTS5) + SQLAlchemy 2.0 + Alembic | Zero-install local relational + full-text storage |
| **Vector Store** | ChromaDB (Persistent local client) | Embedded vector storage on disk (`./data/vectors`) |
| **Video / Audio** | FFmpeg (`ffprobe` + `ffmpeg`) + PySceneDetect | Industry-standard metadata, audio, and scene cut detection |
| **Transcription** | `faster-whisper` (local) + Cloud Adapter | Fast local ASR without mandatory API costs |
| **Embeddings & Re-ranking** | `sentence-transformers` (Bi-Encoder + Cross-Encoder) | Local PyTorch models (`all-MiniLM-L6-v2` + `ms-marco-MiniLM-L-6-v2`) |
| **LLM Layer** | Provider-agnostic adapter (Gemini / OpenAI / Ollama) | Used only for grounded summaries & chapter generation |
| **MCP** | Official Python `mcp` SDK | Plugs into Claude Desktop, Cursor, Antigravity |
| **Testing & ML Eval** | Pytest (Backend/AI) + Vitest (Frontend) | Evaluation script measuring MRR@10, NDCG@10, and Recall@K |

---

## 5. SYSTEM ARCHITECTURE

```text
               HUMAN USER                      AI AGENT (Claude / Cursor / Antigravity)
                   |                                              |
                   v                                              v
     REACT WEB INSPECTOR (Vite/TS)                     MCP SERVER (STDIO / Python)
                   |                                              |
                   v                                              |
            FASTAPI REST API                                      |
                   |                                              |
                   +----------------------+-----------------------+
                                          |
                                          v
                           SHARED APPLICATION SERVICE LAYER
             (MediaService, TranscriptionService, SearchService, SummaryService)
                                          |
                +-------------------------+-------------------------+
                |                         |                         |
                v                         v                         v
      SQLite + FTS5 Index         ChromaDB Vectors         Local Media Storage
        (./data/app.db)           (./data/vectors)       (Thumbnails & Audio WAV)
                |
                v
     LOCAL PROCESSING PIPELINE
   (FFmpeg -> PySceneDetect -> Faster-Whisper -> Chunker -> Embedder)
```

---

## 6. REPOSITORY STRUCTURE

```text
arova-creator-intelligence/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── features/
│   │   │   ├── dashboard/          # Library stats, job queue, quick search
│   │   │   ├── media-library/      # Video grid, import modal, collection manager
│   │   │   ├── video-search/       # Hybrid search bar, timestamp jump player
│   │   │   ├── video-inspector/    # Video player, transcript timeline, scenes, chapters
│   │   │   └── settings/           # Model providers, local paths, MCP config snippet
│   │   ├── services/
│   │   └── types/
│   ├── package.json
│   └── tsconfig.json
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/routes/
│   │   ├── core/                   # config.py, logging.py, telemetry.py, security.py
│   │   ├── database/               # session.py, migrations/
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── schemas/                # Pydantic v2 schemas
│   │   ├── services/               # media, video, transcription, embedding, search, summary
│   │   ├── ai/
│   │   │   ├── providers/          # local sentence-transformers, faster-whisper, cloud adapters
│   │   │   ├── retrieval/          # hybrid_search.py (vector + FTS5 RRF)
│   │   │   ├── reranking/          # cross_encoder_reranker.py (PyTorch cross-attention)
│   │   │   └── evaluation/         # eval_harness.py, metrics.py (MRR, NDCG, Recall@K, Latency)
│   │   ├── processing/             # metadata.py, thumbnails.py, scene_detection.py, audio.py
│   │   └── workers/                # Local background task runner & queue telemetry
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── benchmarks/             # Latency profiling & synthetic query load tests
│   └── pyproject.toml
├── mcp_server/
│   ├── server.py
│   ├── tools/
│   └── tests/
├── docs/
│   ├── architecture.md
│   ├── installation.md
│   ├── mcp-guide.md
│   ├── PROJECT_STATUS.md
│   ├── DEVELOPMENT_LOG.md
│   ├── TECHNICAL_DECISIONS.md
│   └── KNOWN_ISSUES.md
├── sample_data/                    # Benchmark queries & sample evaluation manifest
├── .env.example
├── docker-compose.yml
├── LICENSE                         # Apache 2.0
└── README.md
```

---

## 7. DATABASE DESIGN (SQLite + SQLAlchemy)

- **`Video`**: `id` (UUID/str), `filename`, `file_path`, `file_hash`, `file_size`, `duration`, `width`, `height`, `fps`, `codec`, `format`, `thumbnail_path`, `processing_status`, `created_at`
- **`Collection`**: `id`, `name`, `description`, `created_at`
- **`CollectionVideo`**: `collection_id`, `video_id`
- **`Transcript`**: `id`, `video_id`, `language`, `model_name`, `full_text`, `created_at`
- **`TranscriptSegment`**: `id`, `transcript_id`, `video_id`, `start_time`, `end_time`, `text`, `confidence`
- **`VideoScene`**: `id`, `video_id`, `scene_index`, `start_time`, `end_time`, `thumbnail_path`, `description`
- **`EmbeddingRecord`**: `id`, `video_id`, `chunk_text`, `start_time`, `end_time`, `embedding_id`, `model_name`, `created_at`
- **`VideoSummary`**: `id`, `video_id`, `summary_text`, `topics_json`, `chapters_json`, `model_name`, `created_at`
- **`ProcessingJob`**: `id`, `video_id`, `job_type`, `status`, `progress`, `error_message`, `created_at`, `completed_at`

---

## 8. REST API DESIGN (`/api/v1`)

- **Health:** `GET /api/v1/health`
- **Videos:**
  - `POST /api/v1/videos/import` (file path or directory path within allowed roots)
  - `GET /api/v1/videos`
  - `GET /api/v1/videos/{video_id}`
  - `DELETE /api/v1/videos/{video_id}/index` (deletes index only, never source media)
  - `POST /api/v1/videos/{video_id}/process`
  - `GET /api/v1/videos/{video_id}/stream` (HTTP Range request support for local video preview jumping to timestamps)
- **Collections:**
  - `POST /api/v1/collections`
  - `GET /api/v1/collections`
  - `POST /api/v1/collections/{collection_id}/videos`
- **Transcripts & Scenes:**
  - `GET /api/v1/videos/{video_id}/transcript`
  - `GET /api/v1/videos/{video_id}/scenes`
- **Search & AI Retrieval:**
  - `POST /api/v1/search/semantic` (Hybrid semantic + FTS5 search with timestamp results)
  - `POST /api/v1/search/transcripts`
  - `POST /api/v1/search/clips` (AI clip finder with duration/relevance scoring)
  - `POST /api/v1/ai/summarize` (Grounded video summary + chapters)
- **ML Evaluation Harness & Telemetry (System Engine Endpoints):**
  - `POST /api/v1/ml/eval/run` (Triggers benchmark run across golden query-segment dataset)
  - `GET /api/v1/ml/eval/report` (Returns latest benchmark: MRR@10, NDCG@10, Recall@K, and bi-encoder vs. cross-encoder latency delta)
  - `GET /api/v1/system/telemetry` (Returns worker throughput, memory/GPU VRAM utilization, average ASR audio factor)
- **Jobs:**
  - `GET /api/v1/jobs`
  - `GET /api/v1/jobs/{job_id}`

---

## 9. DEVELOPER CONNECTORS, MCP STACK & ANTI-BLUFF WORKFLOW

To build this system rapidly as a solo founder/engineer without AI bloat or hallucinated code, development uses the following **Agent & Connector Stack**:

| Tool / Connector | Role in Development | How It Is Used in Every Milestone |
| :--- | :--- | :--- |
| **Ponytail (`ponytail`, `ponytail-review`, `ponytail-audit`)** | **Anti-Bluff & Code Quality Gate** (Already Installed) | Blocks over-engineering, fake mock data, dead abstractions, and unused wrappers. Run a `ponytail-review` check at the end of every feature before committing. |
| **Obsidian Vault (`docs/` as Main Brain + optional `mcp-obsidian`)** | **Second Brain & Engineering Ledger** | Point Obsidian directly at the repo's `docs/` folder (or connect via `mcp-obsidian`). Every milestone updates `PROJECT_STATUS.md`, `DEVELOPMENT_LOG.md`, `TECHNICAL_DECISIONS.md`, and `KNOWN_ISSUES.md` using clean Markdown + `[[wikilinks]]`. |
| **Gemini API Docs MCP (`gemini-api-docs`)** | **Up-to-Date SDK Reference** (Already Installed) | Queries official upstream `google-genai` SDK docs when building the grounded LLM summariser & chapter generator in Milestone 4 (never uses deprecated SDK syntax). |
| **TinyFish / Web Agent Connector (Optional)** | **External Web Metadata / Benchmark Fetcher** | *Optional helper:* Use only if fetching public benchmark video metadata or external web references. Core video indexing stays 100% local-first. |
| **`uv` + `pytest` + `vitest`** | **Fast Package & Verification Harness** | `uv` manages Python environments in milliseconds; `pytest` and `vitest` verify every feature before marking it complete. |

---

## 10. FEATURE-BY-FEATURE EXECUTION ROADMAP (5 MILESTONES)

Execute strictly **one milestone and one logical feature at a time**. Every feature follows the loop: **Plan -> Minimal Implementation (Ponytail) -> Automated Test -> Update Obsidian `docs/` Brain**.

### Milestone 1 — Foundation, Obsidian Brain & Connectivity (Days 1–2)
- **Feature 1.1 (Obsidian Brain Init):** Create `docs/PROJECT_STATUS.md`, `docs/DEVELOPMENT_LOG.md`, `docs/TECHNICAL_DECISIONS.md`, `docs/KNOWN_ISSUES.md`, `docs/architecture.md`, and `README.md`.
- **Feature 1.2 (Backend Core):** Scaffold `backend/` with `uv` / `pyproject.toml`, FastAPI (`app/main.py`), Pydantic Settings (`app/core/config.py`), structured logging (`app/core/logging.py`), and `GET /api/v1/health`.
- **Feature 1.3 (Frontend Shell):** Scaffold `frontend/` (React + Vite + TypeScript + Tailwind CSS) with layout navigation and live backend health status indicator.
- **Feature 1.4 (Verification & Ponytail Audit):** Run `pytest` on `/api/v1/health` and verify frontend build (`npm run build` / `vitest`).
- **Acceptance Gate:** Backend and frontend run locally, communicate over `/api/v1/health`, and pass tests with zero dead files.

### Milestone 2 — Media Ingestion, FFmpeg Pipeline & Video Inspector UI (Days 3–5)
- **Feature 2.1 (SQLite + SQLAlchemy Schema):** Implement `Video`, `Collection`, `CollectionVideo`, and `ProcessingJob` models + Alembic migration.
- **Feature 2.2 (Safe File & FFmpeg Probing):** Build path-traversal-safe local file validator, SHA-256 deduplication hash, `ffprobe` metadata extractor (`duration`, `width`, `height`, `fps`, `codec`), and `ffmpeg` keyframe thumbnail generator.
- **Feature 2.3 (Import, Index Delete & HTTP Range Streaming API):** Implement `POST /api/v1/videos/import`, `GET /api/v1/videos`, `DELETE /api/v1/videos/{id}/index` (never deletes source file), `GET /api/v1/videos/{id}/stream` (HTTP 206 Range support), and Collection endpoints.
- **Feature 2.4 (Media Library & Video Player UI):** Build the Media Library grid, Import modal, Collection filter, and HTML5 Video Player with timestamp jump support.
- **Acceptance Gate:** Import a real local MP4, view extracted metadata and thumbnail, stream/seek video in browser, and pass API + DB integration tests.

### Milestone 3 — Whisper ASR, PySceneDetect & Background Job Runner (Days 6–9)
- **Feature 3.1 (Audio & Scene Extraction):** Build `ffmpeg` 16kHz mono WAV extractor and `PySceneDetect` content-aware scene cut detector (`VideoScene` records with midpoint thumbnails).
- **Feature 3.2 (Transcription Abstraction & Faster-Whisper):** Implement `TranscriptionProvider` interface with `faster-whisper` local adapter (supporting English, Hindi, Hinglish) storing `Transcript` and timestamped `TranscriptSegment` rows.
- **Feature 3.3 (SQLite Background Task Runner):** Build non-blocking background worker executing Metadata -> Scenes -> Audio -> Whisper while updating `ProcessingJob` progress and Measure Real-Time Factor (RTF).
- **Feature 3.4 (Interactive Transcript & Scene Timeline UI):** Add clickable transcript segments and visual scene cards in the Video Inspector page that seek the video player to exact `start_time`.
- **Acceptance Gate:** Process a video end-to-end; inspect timestamped transcript and scenes in UI; verify retry/error handling with Pytest.

### Milestone 4 — Two-Stage Hybrid RAG, Cross-Encoder ML Re-Ranker & Eval Harness (Days 10–14)
- **Feature 4.1 (Timestamp-Preserving Chunker & Dual Index):** Group transcript segments into overlapping 30s semantic windows; index dense embeddings in ChromaDB (`sentence-transformers/all-MiniLM-L6-v2`) and lexical text in SQLite `FTS5`.
- **Feature 4.2 (Stage-1 Hybrid RRF + Stage-2 Cross-Encoder Re-Ranking):** Merge ChromaDB + FTS5 results via Reciprocal Rank Fusion (RRF), then re-score top-20 candidates using PyTorch `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- **Feature 4.3 (ML Evaluation Harness & Telemetry API):** Build `backend/app/ai/evaluation/eval_harness.py` + `sample_data/evaluation_golden_set.json` computing **MRR@10**, **NDCG@10**, **Recall@1/3/5/10**, and **p50/p95 latency delta** via `/api/v1/ml/eval/run` and `/api/v1/system/telemetry`.
- **Feature 4.4 (AI Clip Finder & Grounded Summariser):** Implement `POST /api/v1/search/clips` and `POST /api/v1/ai/summarize` (Pydantic-validated summary + timestamped chapters).
- **Feature 4.5 (AI Search & Benchmark UI):** Build natural-language video search page with instant clip preview, relevance score breakdown, and evaluation report view.
- **Acceptance Gate:** Search queries jump to exact video timestamps; ML evaluation harness outputs real MRR/NDCG/Recall/Latency benchmarks.

### Milestone 5 — Official MCP Server, Docker & Public v1.0 Release (Days 15–18)
- **Feature 5.1 (Official Python MCP Server):** Build `mcp_server/server.py` (STDIO transport) exposing the 8 retrieval/inspection tools directly backed by `backend/app/services`.
- **Feature 5.2 (MCP Inspector & Settings UI):** Add one-click "Copy Claude Desktop / Cursor / Antigravity MCP Config" in Frontend Settings + MCP tool unit tests.
- **Feature 5.3 (Docker, CI & Ponytail Full Repo Audit):** Add `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, and run a full `ponytail-audit` to strip any dead code before tagging `v1.0.0`.
- **Acceptance Gate:** Connect an MCP client to query local videos; all backend, frontend, MCP, and ML benchmark tests pass in CI.
