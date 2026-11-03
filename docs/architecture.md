# System Architecture

## Overview

Arova Creator Intelligence is an open-source, local-first multimodal video retrieval (RAG) and Model Context Protocol (MCP) engine. Both the FastAPI REST server and the STDIO MCP server share a unified Python service layer (`backend/app/services`), ensuring consistency between web interfaces, CLI commands, and AI agent tools.

```text
               HUMAN USER                      AI AGENT (Claude Desktop / Cursor)
                   |                                              |
                   v                                              v
      REACT WEB WORKSPACE (Vite/TS)                 FASTMCP SERVER (STDIO / Python)
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
- **Source Video Immutability:** Original user video files are read-only; indexing, probing, and index removal operations never alter or delete source media on disk.
