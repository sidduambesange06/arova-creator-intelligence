# Advanced Multi-Agent System Architecture

Related notes: [[PROJECT_STATUS]] | [[FLASH_EXECUTION_PLAYBOOK]] | [[architecture]] | [[DEVELOPMENT_LOG]]

## Task Division Across Specialized Subagents

To execute development with precision, zero bloat, and rigorous verification, tasks in `arova-creator-intelligence` are divided across 5 specialized autonomous subagents:

```text
                           LEAD ORCHESTRATOR
                (Antigravity / Gemini Lead AI Engineer)
                                   |
         +-------------+-----------+-----------+-------------+
         |             |                       |             |
         v             v                       v             v
   [media-pipeline]  [ml-rag-engineer]  [frontend-inspector] [mcp-protocol]
   - FFmpeg / WAV    - Hybrid RRF       - React / TS         - 8 MCP Tools
   - PySceneDetect   - Cross-Encoder    - Video Player Seek  - STDIO Server
   - Faster-Whisper  - Chroma + FTS5    - Timeline UI        - Agent Configs
   - Background RTF  - IR Eval Metrics  - Vitest             - MCP Tests
         |             |                       |             |
         +-------------+-----------+-----------+-------------+
                                   |
                                   v
                         [qa-audit-sentinel]
                         - system_health_audit.py
                         - Pytest + Vitest
                         - IP Boundary & Security Checks
                         - Obsidian docs/ Sync
```

---

## 1. `media-pipeline-engineer`
- **Scope:** Milestone 2 & Milestone 3 media processing.
- **Responsibilities:**
  - FFmpeg metadata probing and keyframe thumbnails.
  - 16kHz mono WAV extraction with silent video fallback (`backend/app/processing/audio.py`).
  - PySceneDetect visual scene boundary detection (`backend/app/processing/scene_detection.py`).
  - Faster-Whisper speech-to-text transcription with offline acoustic fallback.
  - SQLite background task runner with progress tracking and RTF telemetry (`backend/app/workers/pipeline_runner.py`).

---

## 2. `ml-rag-engineer`
- **Scope:** Milestone 4 Two-Stage Hybrid Video RAG & Evaluation.
- **Responsibilities:**
  - Timestamp-preserving chunking (30s windows with 5s overlap).
  - Dual Indexing: SQLite `FTS5` lexical index + ChromaDB dense vector store (`all-MiniLM-L6-v2`).
  - Stage-1 Hybrid Retrieval via Reciprocal Rank Fusion ($RRF(d) = \sum \frac{1}{60 + \text{rank}(d)}$).
  - Stage-2 ML Re-ranking via local PyTorch Cross-Encoder (`ms-marco-MiniLM-L-6-v2`).
  - ML Evaluation Harness calculating MRR@10, NDCG@10, Recall@K ($K \in \{1, 3, 5, 10\}$), and latency delta.
  - AI Clip Finder and Grounded Summariser with timestamped chapters.

---

## 3. `frontend-inspector-engineer`
- **Scope:** React Web Inspector Shell & Feature Views.
- **Responsibilities:**
  - React 18 + TypeScript + Vite + Tailwind CSS UI components.
  - HTML5 video player with HTTP 206 byte-range seeking to exact timestamps.
  - Interactive transcript timeline and scene cut visual strip.
  - Hybrid RAG search bar, clip results preview, and ML benchmark evaluation report dashboard.
  - MCP configuration copying and connection guides.
  - Zero mock data; all views backed by real APIs and tested via Vitest.

---

## 4. `mcp-protocol-engineer`
- **Scope:** Milestone 5 Model Context Protocol Server.
- **Responsibilities:**
  - Official Python MCP server implementation (`mcp_server/server.py`) over STDIO transport.
  - Exposing the 8 read-only inspection and retrieval tools backed directly by `backend/app/services`.
  - STDIO client integration testing for Claude Desktop, Cursor, and Gemini Antigravity.

---

## 5. `qa-audit-sentinel`
- **Scope:** Continuous Quality Assurance, Security & Compliance.
- **Responsibilities:**
  - Master health audit runner (`scripts/system_health_audit.py`).
  - Strict Apache 2.0 commercial IP boundary audits (zero proprietary Arova Creator OS / Molty AI terms).
  - Security validation: path-traversal blocking and safe index deletion.
  - Database schema and PRAGMA integrity verification.
  - Obsidian Main Brain ledger updates (`PROJECT_STATUS.md`, `DEVELOPMENT_LOG.md`, `TECHNICAL_DECISIONS.md`, `KNOWN_ISSUES.md`).
