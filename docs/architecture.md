# System Architecture

Related notes: [[PROJECT_STATUS]] | [[DEVELOPMENT_LOG]] | [[TECHNICAL_DECISIONS]] | [[KNOWN_ISSUES]]

## Overview

`arova-creator-intelligence` is a local-first video indexing, two-stage hybrid retrieval (RAG), and Model Context Protocol (MCP) engine. Both the FastAPI REST server and the STDIO MCP server invoke a shared Python service layer (`backend/app/services`), eliminating duplicate business logic.

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

## Storage & Data Boundaries

- **SQLite + FTS5 (`./data/app.db`):** Stores relational metadata (`Video`, `Collection`, `Transcript`, `TranscriptSegment`, `VideoScene`, `ProcessingJob`, `VideoSummary`) and full-text lexical index (`FTS5`).
- **ChromaDB (`./data/vectors`):** Persistent local vector store for timestamped transcript window embeddings (`all-MiniLM-L6-v2`).
- **Media Artifacts (`./data/media`):** Extracted `16kHz` mono WAV audio files and JPEG scene/keyframe thumbnails.
- **Source Video Safety:** Original user video files are read-only; index removal never deletes source media files on disk.

