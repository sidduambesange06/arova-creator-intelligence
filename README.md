# Arova Creator Intelligence

**The local-first video intelligence and Model Context Protocol (MCP) engine for AI agents and developers.**

[![CI Suite](https://github.com/sidduambesange06/arova-creator-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/sidduambesange06/arova-creator-intelligence/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2024.11-green.svg)](https://github.com/jlowin/fastmcp)

> Index local video libraries into timestamped transcripts, visual scene boundaries, and hybrid vector embeddings—accessible via local REST API, web interface, and Model Context Protocol (MCP).

Licensed under the [Apache License 2.0](./LICENSE).

---

## Project Status: Developer Preview / Alpha

Arova Creator Intelligence is an open-source project in active developer preview (Alpha). It is designed for developers, researchers, and AI engineers evaluating local multimodal video indexing and retrieval on their own workstations.

- **Verified Local Mechanics:** Automated tests verify local ingestion, native FFmpeg scene detection, SQLite FTS5 lexical search, dense semantic search, Cross-Encoder re-ranking, and FastMCP STDIO transport.
- **Experimental & Roadmap Items:** Optical character recognition (OCR) currently uses template heuristics. Formal multi-host package distribution and live desktop GUI client testing are staged for upcoming milestones.

---

## Core Capabilities

- **Local Video Ingestion & Metadata (`ffprobe` + `ffmpeg`):** Non-destructive media probing (duration, resolution, framerate, codecs), SHA-256 deduplication, keyframe thumbnails, and HTTP 206 Partial Content video streaming. Original source video files are opened strictly read-only.
- **Visual Scene Detection (`ffmpeg`):** Native FFmpeg scene-selection filter (`select='gt(scene,...)'`) identifying visual cut boundaries and calculating representative midpoint keyframes.
- **Speech Transcription (`faster-whisper`):** Offline speech-to-text with millisecond timestamps and word-level alignment (optional `[asr]` extra; returns clear ASR-unavailable error when uninstalled without fabricating text).
- **Visual-Text Dual Memory:** Keyframe on-screen visual text extraction fused into sliding-window transcript chunks tagged with `[On-Screen Visual Text]`.
- **Two-Stage Hybrid Search:**
  - *Stage 1:* Dense semantic vectors (optional `sentence-transformers/all-MiniLM-L6-v2`) stored in local JSON vector storage, merged with lexical `SQLite FTS5` (BM25) via Reciprocal Rank Fusion (RRF, $k=60$).
  - *Stage 2:* PyTorch Cross-Encoder re-ranking (optional `cross-encoder/ms-marco-MiniLM-L-6-v2`) computing joint query-passage relevance scores, with term-proximity lexical fallback.
- **Grounded Video Q&A:** Synthesizes factual answers strictly citing verified timecode intervals `[mm:ss - mm:ss]` linked directly to video player positions.
- **FastMCP Server (8 Read-Only Tools):** STDIO server exposing 8 read-only retrieval tools to MCP-compatible AI agents (Claude Desktop, Cursor, VS Code). Lossless subclip export requires explicit developer opt-in.
- **CLI Diagnostics & Demo:** Built-in `arova doctor` environment diagnostic, `arova demo` instant synthetic first-use flow, and zero-dependency `ArovaClient` Python SDK.
- **Web Workspace:** Dark-theme responsive web interface for browsing indexed media, interactive scrubbing, and inspectable hybrid search queries.

---

## Platform Requirements

- **Python:** 3.11+
- **Node.js:** 20+ (Node.js 24 LTS recommended)
- **FFmpeg & ffprobe:** System installation recommended. If not present on `PATH`, the engine automatically falls back to bundled `imageio-ffmpeg` binaries.
- **Supported Operating Systems:** Linux (Ubuntu 22.04+), macOS (13+), Windows 10/11 (x86_64).
- **Hardware:** Standard multi-core CPU. CPU inference with INT8 quantization is supported out of the box; GPU acceleration (CUDA) is optional.

---

## Quick Start

### 1. Installation

Clone the repository and install backend dependencies:

```bash
git clone https://github.com/sidduambesange06/arova-creator-intelligence.git
cd arova-creator-intelligence

# Using Astral uv (recommended):
uv sync --project backend --group dev --locked

# Or with standard Python venv:
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e backend/
```

### 2. Verify Your Environment (`arova doctor`)

Run the non-destructive diagnostic check:

```bash
python -m arova doctor
```

This verifies Python runtime version, FFmpeg/ffprobe binary resolution, SQLite FTS5 capability, data directory write permissions, and FastMCP tool availability.

### 3. Run the Synthetic First-Use Demo (`arova demo`)

Validate the end-to-end ingestion, transcription, indexing, hybrid search, and grounded Q&A pipeline on a lightweight synthetic fixture in under one second:

```bash
python -m arova demo
```

### 4. Start the Backend REST API Server

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`

### 5. Start the Web Workspace UI

In a separate terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173` to access the media library, video player, and search inspector.

### 6. Connect AI Agents via Model Context Protocol (FastMCP)

Configure **Claude Desktop** (`claude_desktop_config.json`), **Cursor** (`.cursor/mcp.json`), or **VS Code** (`.vscode/mcp.json`):

```json
{
  "mcpServers": {
    "arova-creator-intelligence": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "<absolute-path-to-the-cloned-arova-repository>"
    }
  }
}
```

> **Note:** Replace `<absolute-path-to-the-cloned-arova-repository>` with the actual local path where you cloned this repository.

By default, AI agents are restricted to 8 read-only retrieval tools (`list_videos`, `get_video_metadata`, `search_video_content`, `search_transcripts`, `find_video_clips`, `summarize_video`, `get_video_chapters`, `get_media_library_stats`). Lossless subclip export can be enabled with `--enable-exports` or `AROVA_ENABLE_MCP_EXPORTS=1`.

### 7. Python Client SDK

```python
from arova import ArovaClient

client = ArovaClient(base_url="http://127.0.0.1:8000")
health = client.health()
print("Engine Status:", health["status"])

# Query video library
results = client.search("scene cut detection", top_k=5)
for hit in results.get("results", []):
    print(f"[{hit['start_time']}s - {hit['end_time']}s] {hit['text']}")
```

---

## Configuration & Local Models

Configuration is managed via environment variables or a local `.env` file (see [`.env.example`](./.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `API_HOST` | `127.0.0.1` | Loopback binding address |
| `API_PORT` | `8000` | REST API service port |
| `SQLITE_DB_PATH` | `./data/app.db` | SQLite relational database path |
| `VECTOR_STORAGE_DIR` | `./data/vectors` | Local JSON vector storage path (`CHROMA_PERSIST_DIR` supported as legacy alias) |
| `MEDIA_STORAGE_DIR` | `./data/media` | Extracted WAV audio and keyframe thumbnails |
| `ALLOWED_MEDIA_ROOTS` | `./data/media` | Approved root directories for media import |
| `WHISPER_MODEL_SIZE` | `base` | faster-whisper model size (`tiny`, `base`, `small`, `medium`) |
| `WHISPER_COMPUTE_TYPE` | `int8` | Inference quantization (`int8`, `float16`, `float32`) |
| `AI_REMOTE_CONSENT` | `false` | Explicit opt-in consent required for remote AI provider egress |

### Model Downloads & Optional Extras
- Default installation provides lightweight lexical FTS5 BM25 search, native FFmpeg scene detection, and zero-telemetry REST/MCP execution.
- Neural speech recognition uses optional `[asr]` extra (`faster-whisper`):
  ```bash
  uv sync --project backend --extra asr --locked
  ```
  If uninstalled or offline, the engine returns a clear ASR-unavailable error rather than fabricating text.
- Dense embeddings (`sentence-transformers/all-MiniLM-L6-v2`) and Cross-Encoder reranking run locally via optional `[ai]` extra:
  ```bash
  uv sync --project backend --extra ai --locked
  ```
- Optional cloud providers (Google Gemini) require explicit user consent (`AI_REMOTE_CONSENT=true`), user-supplied API keys (BYOK), and the `[cloud]` extra:
  ```bash
  uv sync --project backend --extra cloud --locked
  ```
- To install all optional extras together:
  ```bash
  uv sync --project backend --all-extras --locked
  ```
> **Note on Weights & Runtime:** Installing an optional extra package provides the required runtime libraries, but does not automatically download model weights or guarantee model availability. Models must be downloaded or cached locally before offline inference.

---

## Privacy & Security Baseline

- **Strict Source Media Immutability:** Original source video files are opened strictly read-only. Indexing, probing, and index deletion operations never alter, overwrite, or delete source video files.
- **Deny-by-Default Filesystem:** File probing and video imports are restricted to configured directories (`ALLOWED_MEDIA_ROOTS`). Path traversal patterns (`../`, symlinks, unauthorized absolute paths) are rejected with HTTP 400.
- **Loopback Binding & Zero Remote Telemetry:** Backend services bind to loopback (`127.0.0.1`) by default. There is zero remote analytics tracking, zero usage telemetry, and zero silent cloud fallback. In-memory operational metrics are queryable only via loopback API.
- **Untrusted Source Defanging:** All media-derived text (transcripts, OCR, metadata) is treated as untrusted data and sanitized prior to LLM context inclusion or query processing.
- **Read-Only MCP Agent Contract:** AI agent connections default to read-only retrieval tools to prevent unauthorized filesystem modification.

---

## Known Limitations

- **Speech ASR Language Performance:**
  - *English (`en_us`):* ~6.7% WER, 0.42x RTF on CPU with faster-whisper-small.
  - *Hindi (`hi_in`) & Tamil (`ta_in`):* ~64.9% - 78.6% WER with smaller models. Useful for keyword retrieval; requires secondary review for high-accuracy transcripts.
  - *Kannada (`kn_in`) & Telugu (`te_in`):* High error rates on generic Whisper checkpoints due to script mismatch. Requires fine-tuned regional checkpoints or external providers.
- **Keyframe OCR:** Current visual text extraction uses lightweight template heuristics. Full scene text recognition is planned for subsequent milestones.
- **Single-Node Execution:** Designed for local developer workstations and single machines; does not operate as a distributed cluster.

See [`docs/KNOWN_ISSUES.md`](./docs/KNOWN_ISSUES.md) for detailed disclosures.

---

## Documentation

- [System Architecture](./docs/architecture.md)
- [Client Integration Guides (Claude Desktop, Cursor, VS Code)](./docs/INTEGRATIONS.md)
- [Model Context Protocol (MCP) Guide](./docs/mcp-guide.md)
- [MCP Toolset Reference](./docs/MCP_TOOLS.md)
- [Installation & Deployment](./docs/installation.md)
- [Feature Status Matrix](./docs/FEATURE_STATUS.md)
- [Known Limitations & Issues](./docs/KNOWN_ISSUES.md)
- [Technical Decisions (ADRs)](./docs/TECHNICAL_DECISIONS.md)
- [Contributing Guidelines](./CONTRIBUTING.md)
- [License](./LICENSE)

---

## Contributing

We welcome community contributions, bug reports, and suggestions. Please read our [Contributing Guidelines](./CONTRIBUTING.md) and [Code of Conduct](./CODE_OF_CONDUCT.md) before opening a pull request.

---

## License

Arova Creator Intelligence is open-source software licensed under the [Apache License, Version 2.0](./LICENSE).
