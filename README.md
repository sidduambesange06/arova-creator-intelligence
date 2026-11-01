# Arova Creator Intelligence

**The Local Video RAG & MCP Engine for AI Agents and Developers.**

> Index local video libraries into timestamped transcripts, visual scenes, and hybrid vector embeddings—accessible via REST API, Hallmark Web Workstation, and Model Context Protocol (MCP).

Licensed under the [Apache License 2.0](./LICENSE).

---

## Release Status: Open-Source Alpha (`v0.1.0-alpha`)

Arova Creator Intelligence is currently in **Open-Source Developer Alpha**. It is designed for developers, researchers, and AI engineers evaluating local multimodal video retrieval on their own workstations.
- **Automated Verification:** 12/12 automated release gates passing (backend, frontend, FastMCP, doctor, demo, 500-video discovery/recovery, 215 red-team injections, 100-query synthetic benchmark, fault injection, and qualified SBOM).
- **Roadmap Staging:** Real-world video benchmarking, multi-machine non-developer installers, and live desktop GUI client QA are staged on the upcoming Beta roadmap (`ADR-007`).

---

## Core Capabilities

- **Local Video Ingestion & Metadata (`ffprobe` + `ffmpeg`):** SHA-256 deduplication, technical media probing, keyframe thumbnails, and HTTP 206 Range streaming. Source video files are strictly read-only.
- **Visual Scene Detection & ASR (`PySceneDetect` + `faster-whisper`):** Content-aware scene boundary detection and timestamp-accurate speech transcription with millisecond precision.
- **Visual-Text Dual Memory Engine:** Keyframe optical character recognition (OCR) fused into transcript passages with `[On-Screen Visual Text]` tags.
- **Two-Stage Hybrid Video RAG:**
  - *Stage 1:* Dense semantic vectors (`ChromaDB` + `all-MiniLM-L6-v2`) merged with lexical `SQLite FTS5` via Reciprocal Rank Fusion (RRF, $k=60$).
  - *Stage 2:* Local PyTorch Cross-Encoder re-ranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`).
- **Grounded Video Q&A:** Synthesizes factual answers with clickable timecode intervals `[mm:ss - mm:ss]` linked directly to video player timestamps.
- **Official FastMCP Server:** STDIO server exposing 8 read-only retrieval tools to Claude Desktop, Cursor, and Gemini Antigravity. (Subclip export requires explicit opt-in).
- **Diagnostic CLI & SDK:** Built-in `arova doctor` diagnostics, `arova demo` instant first-run flow, and zero-dependency `ArovaClient` Python SDK.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ (for Web Workstation UI)
- [uv](https://github.com/astral-sh/uv) (recommended) or standard Python `venv`
- System FFmpeg is optional (bundled `imageio-ffmpeg` is automatically used as a self-contained fallback)

### 1. Installation & Environment Setup

Clone the repository and sync backend dependencies:

```bash
git clone https://github.com/sidduambesange06/arova-creator-intelligence.git
cd arova-creator-intelligence

# Install backend dependencies with uv (or standard python -m venv)
uv sync --project backend
```

### 2. Verify Your Environment (`arova doctor`)

Run the non-destructive system diagnostic:

```bash
# Using uv:
uv run --project backend arova doctor

# Or with virtualenv activated (.venv/bin/activate or .venv\Scripts\activate):
arova doctor

# Or directly via Python:
python -m arova doctor
```
This checks Python runtime, FFmpeg/ffprobe resolution, SQLite FTS5 capability, data directory write permissions, and FastMCP tool availability.

### 3. Run the Sub-Minute First-Use Demo (`arova demo`)

Test the complete ingestion, transcription, indexing, hybrid search, and grounded Q&A pipeline on a lightweight synthetic fixture:

```bash
# Using uv:
uv run --project backend arova demo

# Or with virtualenv activated:
arova demo

# Or directly via Python:
python -m arova demo
```
*Executes in under 1 second on standard developer hardware with zero external cloud dependencies or credentials required.*

### 4. Start the Backend REST API Server

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`

### 5. Connect AI Agents via FastMCP (STDIO)

Run the official Model Context Protocol server over STDIO:

```bash
python -m mcp_server.server
```

To configure in **Claude Desktop** (`claude_desktop_config.json`) or **Cursor**:

```json
{
  "mcpServers": {
    "arova-creator-intelligence": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/arova-creator-intelligence"
    }
  }
}
```
*By default, AI agents have access strictly to 8 read-only retrieval tools. To enable lossless subclip exports, pass `--enable-exports` or set `AROVA_ENABLE_MCP_EXPORTS=1`.*

### 6. Start the Hallmark Web Workstation UI

```bash
cd frontend
npm install
npm run dev
```
Open `http://127.0.0.1:5173` to explore the dark workstation layout, interactive video scrubber, synchronized transcript timeline, and hybrid search inspector.

### 7. Use the Python Client SDK

```python
from arova import ArovaClient

client = ArovaClient(base_url="http://127.0.0.1:8000")
health = client.health()
print("Engine Status:", health["status"])

# Query video library
results = client.search("retrieval augmented generation", top_k=5)
for hit in results.get("results", []):
    print(f"[{hit['start_time']}s - {hit['end_time']}s] {hit['text']}")
```

---

## Security & Privacy Baseline

- **Strict Source Media Immutability:** Original source video files are opened read-only. Indexing, probing, and index deletion never overwrite or delete source videos.
- **Deny-by-Default Filesystem:** Video ingestion and subclip exports are strictly restricted to configured directories (`ALLOWED_MEDIA_ROOTS`). Path traversal attempts (`../`) are rejected with HTTP 400.
- **Loopback-Only Network Binding:** Backend services bind to loopback (`127.0.0.1`) by default. Static code inspection confirms zero analytics tracking, zero telemetry pings, and zero silent cloud fallbacks. *(Notice: Independent dynamic packet-egress capture under OS isolation is staged on the Beta roadmap).*
- **Adversarial Content Isolation:** Untrusted transcripts and on-screen OCR text are defanged and enclosed in `<untrusted_video_evidence>` XML boundaries, verified against a 215-case red-team prompt-injection corpus.
- **Read-Only MCP Agent Contract:** AI agents are restricted to read-only retrieval tools by default to prevent unauthorized filesystem modification.

---

## Documentation & Engineering Brain (`docs/`)

- [System Architecture](./docs/architecture.md)
- [Client Integration Guides (Claude, Cursor, Antigravity)](./docs/INTEGRATIONS.md)
- [MCP Toolset Documentation](./docs/MCP_TOOLS.md)
- [Feature Reality Status](./docs/FEATURE_STATUS.md)
- [Known Limitations & Issues](./docs/KNOWN_ISSUES.md)
- [Technical Decisions (ADRs)](./docs/TECHNICAL_DECISIONS.md)
- [Project Status & Checklist](./docs/PROJECT_STATUS.md)
- [Development Log](./docs/DEVELOPMENT_LOG.md)
