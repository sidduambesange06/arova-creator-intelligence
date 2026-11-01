# Arova Creator Intelligence — Requirement Traceability Matrix

**Specification Authority:** Open Source Spec v1.1  
**Total Requirements Tracked:** 35  
**Audit Date:** 2026-11-01  

---

## Traceability Matrix

| Requirement ID | Specification Source | Description / Requirement | Workstream | Acceptance Criteria | Tests / Evidence | Status |
|---|---|---|---|---|---|---|
| **REQ-001** | Spec §3.1.1 | Local Video File / Directory Import | `WS-ENG` | Accepts local `.mp4`, `.mov`, `.mkv` files; enforces `ALLOWED_MEDIA_ROOTS`. | `test_media_probing.py::test_path_traversal_protection_and_discovery` | `VERIFIED` |
| **REQ-002** | Spec §3.1.10 | Original Source Media Immutability | `WS-SEC` | Source video file checksum is never modified by probing, indexing, or deleting index. | `test_videos_api.py::test_import_list_stream_and_safe_delete_index` | `VERIFIED` |
| **REQ-003** | Spec §3.1.2 | Technical Media Probe via `ffprobe` | `WS-ENG` | Returns duration, width, height, fps, codec, format, bitrate as JSON. | `test_media_probing.py::test_ffmpeg_metadata_probe_and_thumbnail` | `VERIFIED` |
| **REQ-004** | Spec §3.1 | SHA-256 Deduplication | `WS-ENG` | Detects duplicate video files and avoids duplicate indexing jobs. | `test_media_probing.py`, `media_probe.py` | `VERIFIED` |
| **REQ-005** | Spec §3.1 | Keyframe Thumbnail Generation | `WS-ENG` | Generates 1-second interval JPEG thumbnails stored in `data/thumbnails`. | `test_ffmpeg_metadata_probe_and_thumbnail` | `VERIFIED` |
| **REQ-006** | Spec §3.1.3 | Audio Extraction (`ffmpeg`) | `WS-ENG` | Extracts 16 kHz mono WAV audio track for transcription. | `test_audio_and_scenes.py::test_extract_audio_wav_with_audio_and_fallback` | `VERIFIED` |
| **REQ-007** | Spec §3.1 | Content-Aware Scene Detection | `WS-ENG` | Detects scene boundaries with threshold fallback for synthesized media. | `test_audio_and_scenes.py::test_detect_video_scenes` | `VERIFIED` |
| **REQ-008** | Spec §3.1.4 | Preserved Millisecond Timestamps | `WS-ENG` | Every transcript segment stores exact `start_time` and `end_time` in seconds/ms. | `test_transcription.py::test_transcribe_and_store_db_persistence` | `VERIFIED` |
| **REQ-009** | Spec §3.1.5 | Offline Speech Transcription (faster-whisper) | `WS-ENG` | Transcribes audio locally using faster-whisper with deterministic fallback. | `test_transcription.py::test_faster_whisper_provider_offline_fallback` | `VERIFIED` |
| **REQ-010** | Spec §3.1 | Visual OCR Frame Text Extraction | `WS-ENG` | Probes frames for text; annotates transcript with `[On-Screen Visual Text]`. | `test_visual_text.py::test_extract_visual_text_fallback_handling` | `VERIFIED` |
| **REQ-011** | Spec §3.1.5 | Dual Storage Persistence (SQLite + ChromaDB) | `WS-ENG` | Stores segments in SQLite database and vector embeddings in ChromaDB. | `test_chunker_and_index.py::test_index_video_chunks_dual_storage` | `VERIFIED` |
| **REQ-012** | Spec §3.1.6 | Dense Semantic Vector Search | `WS-ENG` | Computes 384-dimensional cosine similarities with normalized vectors. | `test_chunker_and_index.py::test_minilm_embedding_provider_dimension_and_norm` | `VERIFIED` |
| **REQ-013** | Spec §3.1.6 | Lexical Search with SQLite FTS5 BM25 | `WS-ENG` | Executes exact keyword queries over FTS5 virtual table. | `test_models.py::test_sqlite_schema_and_cascade_delete` | `VERIFIED` |
| **REQ-014** | Spec §3.1 | Reciprocal Rank Fusion (RRF) | `WS-ENG` | Fuses dense and lexical ranks using $k=60$ formula: $\sum \frac{1}{60 + r(d)}$. | `test_hybrid_rerank.py::test_hybrid_search_rrf_and_api` | `VERIFIED` |
| **REQ-015** | Spec §3.1 | Stage 2 Cross-Encoder Re-Ranking | `WS-ENG` | Scores query-passage pairs using local PyTorch Cross-Encoder. | `test_hybrid_rerank.py::test_cross_encoder_reranker_scoring` | `VERIFIED` |
| **REQ-016** | Spec §3.1.7 | Result Asset & Timestamp Identity | `WS-ENG` | Search hits return stable `video_id`, display title, and `[start_time, end_time]`. | `test_hybrid_rerank.py::test_hybrid_search_rrf_and_api` | `VERIFIED` |
| **REQ-017** | Spec §3.1.8 | Grounded Video Q&A with Timecode Citations | `WS-ENG` | Synthesizes answers citing verified time intervals `[mm:ss - mm:ss]`. | `test_clips_and_summary.py::test_ask_video_ai_grounded_citations` | `VERIFIED` |
| **REQ-018** | Spec §3.1.8 | Executive Summary & Chapters API | `WS-ENG` | Generates structured summary bullets and chapter breakdowns cached in DB. | `test_clips_and_summary.py::test_summarize_video_api_grounded_and_cached` | `VERIFIED` |
| **REQ-019** | Spec §3.1.9 | Health & Job Status API | `WS-ENG` | `GET /api/v1/health` and `GET /api/v1/pipeline/jobs/{id}` expose live status. | `test_health.py::test_health_endpoint_returns_ok`, `test_pipeline_api.py` | `VERIFIED` |
| **REQ-020** | Spec §3.2 | FastMCP STDIO Server Transport | `WS-MCP` | Local STDIO server runs with JSON-RPC protocol; stderr for logs. | `mcp_server/server.py` | `VERIFIED` |
| **REQ-021** | Spec §3.2 | MCP Read-Only Toolset (8 Tools) | `WS-MCP` | Exposes the 8 approved read-only retrieval tools to AI agents. | `docs/MCP_TOOLS.md`, `mcp_server/tools/video_tools.py` | `VERIFIED` |
| **REQ-022** | Spec §4.1 | OpenAPI / REST Developer Endpoints | `WS-ENG` | Complete REST endpoints for videos, streams, search, clips, summary, health. | `backend/app/main.py` (FastAPI OpenAPI docs) | `VERIFIED` |
| **REQ-023** | Spec §4.2 | Thin Python Client Wrapper | `WS-CLI` | Lightweight Python client wrapper calling REST endpoints. | Planned for Phase 1 delivery | `PLANNED` |
| **REQ-024** | Spec §4.3 | CLI Diagnostic `arova doctor` | `WS-CLI` | Diagnostic command checking Python, FFmpeg, SQLite, disk, and MCP readiness. | Planned for Phase 1 delivery | `PLANNED` |
| **REQ-025** | Spec §4.3 | CLI Sample Workflow `arova demo` | `WS-CLI` | Runs small synthetic sample workflow without requiring external credentials. | Planned for Phase 1 delivery | `PLANNED` |
| **REQ-026** | Spec §7.1 | Accurate Local Processing Boundary | `WS-SEC` | Loopback bind default; zero telemetry; zero silent cloud fallback. | `reports/security/CONTROL_GAP_ASSESSMENT.md` | `VERIFIED` |
| **REQ-027** | Spec §7.2 | Deny-by-Default Filesystem Roots | `WS-SEC` | Path traversal protection with canonicalized path checks. | `test_media_probing.py::test_path_traversal_protection_and_discovery` | `VERIFIED` |
| **REQ-028** | Spec §7.2 | Untrusted Media-Derived Text Sanitization | `WS-SEC` | Transcripts and OCR treated as untrusted text; no prompt injection execution. | `backend/app/services/summary_service.py` | `VERIFIED` |
| **REQ-029** | Spec §8.0 | Apache-2.0 License Compliance | `WS-SEC` | Root `LICENSE` and `NOTICE` preserved; dependency licenses audited. | `reports/audit/DEPENDENCY_LICENSES.md` | `VERIFIED` |
| **REQ-030** | Spec §9.2 | ML Evaluation Metrics Harness | `WS-QA` | Automated calculations of MRR@10, NDCG@10, Recall@K on golden queries. | `test_eval_metrics.py::test_ranking_metrics_formulas` | `VERIFIED` |
| **REQ-031** | Spec §10.2 | Community Documents & Governance | `WS-DOC` | `README.md`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `AGENTS.md`. | Root documentation audit | `VERIFIED` |
| **REQ-032** | Spec §15.1 | Sub-5 Minute First-Use Verification | `WS-QA` | Reference machine setup documented and verified under 5 minutes. | Documented in `docs/installation.md` | `VERIFIED` |
| **REQ-033** | Spec §15.2 | Client Integration Guides | `WS-DOC` | Tested configurations for Claude Desktop, Cursor, Gemini Antigravity. | `docs/mcp-guide.md`, `docs/MCP_TOOLS.md` | `VERIFIED` |
| **REQ-034** | Spec §1.4 | Strict Commercial IP Exclusion | `WS-SEC` | Zero Creator OS / Molty AI / Brand Deal CRM / cloud studio code. | Verified by codebase scan | `VERIFIED` |
| **REQ-035** | Spec §1.2 | Hallmark Fullscreen Workstation UI | `WS-ENG` | Tokenized dark workstation UI with precision scrubber and multi-track timeline. | `vitest run`, `vite build` | `VERIFIED` |

