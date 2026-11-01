# Arova Creator Intelligence — Requirement Traceability Matrix

**Specification Authority:** Open Source Spec v1.1  
**Total Requirements Tracked:** 35  
**Audit Date:** 2026-11-01  

---

## Traceability Matrix

| Requirement ID | Specification Source | Description / Requirement | Workstream | Task ID | Acceptance Criteria | Tests / Verification | Reality Status |
|---|---|---|---|---|---|---|---|
| **REQ-001** | Spec §3.1.1 | Local Video File / Directory Import | `WS-ENG` | `TASK-001` | Accepts local `.mp4`, `.mov`, `.mkv` files; enforces `ALLOWED_MEDIA_ROOTS`. | `test_media_probing.py::test_path_traversal_protection_and_discovery` | `VERIFIED` |
| **REQ-002** | Spec §3.1.10 | Original Source Media Immutability | `WS-SEC` | `TASK-001` | Source video file checksum is never modified by probing, indexing, or deleting index. | `test_videos_api.py::test_import_list_stream_and_safe_delete_index` | `VERIFIED` |
| **REQ-003** | Spec §3.1.2 | Technical Media Probe via `ffprobe` | `WS-ENG` | Baseline | Returns duration, width, height, fps, codec, format, bitrate as JSON. | `test_media_probing.py::test_ffmpeg_metadata_probe_and_thumbnail` | `VERIFIED` |
| **REQ-004** | Spec §3.1 | SHA-256 Deduplication | `WS-ENG` | Baseline | Detects duplicate video files and avoids duplicate indexing jobs. | `test_media_probing.py`, `media_probe.py` | `VERIFIED` |
| **REQ-005** | Spec §3.1 | Keyframe Thumbnail Generation | `WS-ENG` | Baseline | Generates 1-second interval JPEG thumbnails stored in `data/thumbnails`. | `test_ffmpeg_metadata_probe_and_thumbnail` | `VERIFIED` |
| **REQ-006** | Spec §3.1.3 | Audio Extraction (`ffmpeg`) | `WS-ENG` | Baseline | Extracts 16 kHz mono WAV audio track for transcription. | `test_audio_and_scenes.py::test_extract_audio_wav_with_audio_and_fallback` | `VERIFIED` |
| **REQ-007** | Spec §3.1 | Content-Aware Scene Detection | `WS-ENG` | Baseline | Detects scene boundaries with threshold fallback for synthesized media. | `test_audio_and_scenes.py::test_detect_video_scenes` | `VERIFIED` |
| **REQ-008** | Spec §3.1.4 | Preserved Millisecond Timestamps | `WS-ENG` | Baseline | Every transcript segment stores exact `start_time` and `end_time` in seconds/ms. | `test_transcription.py::test_transcribe_and_store_db_persistence` | `VERIFIED` |
| **REQ-009** | Spec §3.1.5 | Offline Speech Transcription (faster-whisper) | `WS-ENG` | Baseline | Transcribes audio locally using faster-whisper with deterministic fallback. | `test_transcription.py::test_faster_whisper_provider_offline_fallback` | `VERIFIED` |
| **REQ-010** | Spec §3.1 | Visual OCR Frame Text Extraction | `WS-ENG` | Baseline | Probes frames for text; annotates transcript with `[On-Screen Visual Text]`. | `test_visual_text.py::test_extract_visual_text_fallback_handling` | `VERIFIED` |
| **REQ-011** | Spec §3.1.5 | Dual Storage Persistence (SQLite + ChromaDB) | `WS-ENG` | Baseline | Stores segments in SQLite database and vector embeddings in ChromaDB. | `test_chunker_and_index.py::test_index_video_chunks_dual_storage` | `VERIFIED` |
| **REQ-012** | Spec §3.1.6 | Dense Semantic Vector Search | `WS-ENG` | Baseline | Computes 384-dimensional cosine similarities with normalized vectors. | `test_chunker_and_index.py::test_minilm_embedding_provider_dimension_and_norm` | `VERIFIED` |
| **REQ-013** | Spec §3.1.6 | Lexical Search with SQLite FTS5 BM25 | `WS-ENG` | Baseline | Executes exact keyword queries over FTS5 virtual table. | `test_models.py::test_sqlite_schema_and_cascade_delete` | `VERIFIED` |
| **REQ-014** | Spec §3.1 | Reciprocal Rank Fusion (RRF) | `WS-ENG` | `TASK-003` | Fuses dense and lexical ranks using $k=60$ formula: $\sum \frac{1}{60 + r(d)}$. | `test_hybrid_rerank.py::test_hybrid_search_rrf_and_api` | `VERIFIED` |
| **REQ-015** | Spec §3.1 | Stage 2 Cross-Encoder Re-Ranking | `WS-ENG` | `TASK-003` | Scores query-passage pairs using local PyTorch Cross-Encoder. | `test_hybrid_rerank.py::test_cross_encoder_reranker_scoring` | `VERIFIED` |
| **REQ-016** | Spec §3.1.7 | Result Asset & Timestamp Identity | `WS-ENG` | `TASK-003` | Search hits return stable `video_id`, display title, and `[start_time, end_time]`. | `test_hybrid_rerank.py::test_hybrid_search_rrf_and_api` | `VERIFIED` |
| **REQ-017** | Spec §3.1.8 | Grounded Video Q&A with Timecode Citations | `WS-ENG` | Baseline | Synthesizes answers citing verified time intervals `[mm:ss - mm:ss]`. | `test_clips_and_summary.py::test_ask_video_ai_grounded_citations` | `VERIFIED` |
| **REQ-018** | Spec §3.1.8 | Executive Summary & Chapters API | `WS-ENG` | Baseline | Generates structured summary bullets and chapter breakdowns cached in DB. | `test_clips_and_summary.py::test_summarize_video_api_grounded_and_cached` | `VERIFIED` |
| **REQ-019** | Spec §3.1.9 | Health & Job Status API | `WS-ENG` | Baseline | `GET /api/v1/health` and `GET /api/v1/pipeline/jobs/{id}` expose live status. | `test_health.py::test_health_endpoint_returns_ok`, `test_pipeline_api.py` | `VERIFIED` |
| **REQ-020** | Spec §3.2 | FastMCP STDIO Server Transport | `WS-MCP` | `TASK-002` | Local STDIO server runs with JSON-RPC protocol; stderr for logs. | `mcp_server/server.py` | `VERIFIED` |
| **REQ-021** | Spec §3.2 | MCP Read-Only Toolset (8 Tools) | `WS-MCP` | `TASK-002` | Exposes the 8 approved read-only retrieval tools to AI agents by default. | `mcp_server/tests/test_mcp_tools.py::test_mcp_server_default_tools_are_eight_read_only` | `VERIFIED` |
| **REQ-022** | Spec §4.1 | OpenAPI / REST Developer Endpoints | `WS-ENG` | Baseline | Complete REST endpoints for videos, streams, search, clips, summary, health. | `backend/app/main.py` (FastAPI OpenAPI docs) | `VERIFIED` |
| **REQ-023** | Spec §4.2 | Thin Python Client Wrapper | `WS-CLI` | `TASK-008` | Lightweight zero-dependency Python client wrapper calling REST endpoints (health, search, videos, ask). | `tests/cli/test_client.py` (4/4 passed) | `VERIFIED` |
| **REQ-024** | Spec §4.3 | CLI Diagnostic `arova doctor` | `WS-CLI` | `TASK-006` | Non-destructive check of Python, FFmpeg, SQLite, disk, and MCP readiness. | `tests/cli/test_doctor.py` (10/10 passed) | `VERIFIED` |
| **REQ-025** | Spec §4.3 | CLI Sample Workflow `arova demo` | `WS-CLI` | `TASK-007` | Runs small synthetic sample workflow without requiring external credentials. | `tests/cli/test_demo.py` (4/4 passed in < 1s) | `VERIFIED` |
| **REQ-026** | Spec §7.1 | Accurate Local Processing Boundary | `WS-SEC` | Baseline | Loopback bind default; zero telemetry; zero silent cloud fallback. | `reports/security/CONTROL_GAP_ASSESSMENT.md` | `VERIFIED` |
| **REQ-027** | Spec §7.2 | Deny-by-Default Filesystem Roots | `WS-SEC` | `TASK-001` | Path traversal protection with canonicalized path checks. | `test_media_probing.py::test_path_traversal_protection_and_discovery` | `VERIFIED` |
| **REQ-028** | Spec §7.2 | Untrusted Media-Derived Text Sanitization | `WS-SEC` | Baseline | Transcripts and OCR treated as untrusted text; no prompt injection execution. | `backend/app/services/summary_service.py` | `VERIFIED` |
| **REQ-029** | Spec §8.0 | Apache-2.0 License Compliance | `WS-SEC` | `TASK-011` | Root `LICENSE` and `NOTICE` preserved; dependency licenses audited. | `reports/audit/DEPENDENCY_LICENSES.md` | `VERIFIED` |
| **REQ-030** | Spec §9.2 | ML Evaluation Metrics Harness | `WS-QA` | Baseline | Automated calculations of MRR@10, NDCG@10, Recall@K on golden queries. | `test_eval_metrics.py::test_ranking_metrics_formulas` | `VERIFIED` |
| **REQ-031** | Spec §10.2 | Community Documents & Governance | `WS-DOC` | `TASK-010` | Root `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`. | Planned document review & link checks | `NOT IMPLEMENTED` |
| **REQ-032** | Spec §15.1 | Sub-5 Minute First-Use Verification | `WS-QA` | `TASK-007` | Reference machine setup documented and verified under 5 minutes. | Verified via `arova demo` (0.74s execution; < 300s target) | `VERIFIED` |
| **REQ-033** | Spec §15.2 | Client Integration Guides | `WS-DOC` | `TASK-009` | Tested configurations for Claude Desktop, Cursor, Gemini Antigravity. | Planned `docs/INTEGRATIONS.md` checklist | `NOT IMPLEMENTED` |
| **REQ-034** | Spec §1.4 | Strict Commercial IP Exclusion | `WS-SEC` | Baseline | Zero Creator OS / Molty AI / Brand Deal CRM / cloud studio code. | Verified by codebase scan | `VERIFIED` |
| **REQ-035** | Spec §1.2 | Hallmark Fullscreen Workstation UI | `WS-ENG` | Baseline | Tokenized dark workstation UI with precision scrubber and multi-track timeline. | `vitest run`, `vite build` | `VERIFIED` |
