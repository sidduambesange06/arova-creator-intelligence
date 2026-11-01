# Arova Creator Intelligence — Feature Reality Status

**Document Authority:** Open Source Spec v1.1 (§2, §12)  
**Verification Date:** 2026-11-01  
**Verification Environment:** Windows 11, Python 3.11.9, Node v22.14.0, PyTorch 2.6.0+cpu, FastAPI 0.115.8, React 18.3.1  

Every claim in the project documentation and `README.md` is mapped below to its exact source file, automated test command, and certified reality status (`WORKING`, `PARTIAL`, `EXPERIMENTAL`, `PLANNED`, `BROKEN`, `UNVERIFIED`).

---

## 1. Feature Verification Matrix

| Claim / Capability | Source Code Location | Verification Test / Command | Verified Status | Evidence Notes |
|---|---|---|---|---|
| **Local Video Ingestion & Probe** | `backend/app/processing/media_probe.py` | `pytest backend/tests/unit/test_media_probing.py` | `WORKING` | Probes duration, resolution, fps, codec via `ffprobe` JSON parsing. |
| **Path Traversal Protection** | `backend/app/processing/media_probe.py`, `backend/app/core/config.py` | `pytest backend/tests/unit/test_media_probing.py::test_path_traversal_protection_and_discovery` | `WORKING` | Strictly rejects paths outside configured `ALLOWED_MEDIA_ROOTS`. |
| **Thumbnail Extraction** | `backend/app/processing/media_probe.py` | `pytest backend/tests/unit/test_media_probing.py::test_ffmpeg_metadata_probe_and_thumbnail` | `WORKING` | Generates 1-second interval JPEG thumbnails via `ffmpeg`. |
| **HTTP 206 Partial Streaming** | `backend/app/api/routes/videos.py` | `pytest backend/tests/integration/test_videos_api.py` | `WORKING` | Supports byte-range requests for video scrubber seeking. |
| **Content-Aware Scene Detection** | `backend/app/processing/scene_detector.py` | `pytest backend/tests/unit/test_audio_and_scenes.py::test_detect_video_scenes` | `WORKING` | Detects scene boundaries with threshold fallback for synthetic media. |
| **Offline Speech ASR** | `backend/app/processing/transcription.py` | `pytest backend/tests/unit/test_transcription.py` | `WORKING` | `faster-whisper` integration with deterministic fallback when weights absent. |
| **Visual OCR Dual Memory** | `backend/app/processing/visual_text.py`, `backend/app/ai/retrieval/chunker.py` | `pytest backend/tests/unit/test_visual_text.py` | `WORKING` | Extracts frame text, fuses into transcript chunks with `[On-Screen Visual Text]` tags. |
| **Stage 1 Dense Semantic Retrieval** | `backend/app/ai/retrieval/embedding_provider.py`, `backend/app/ai/retrieval/chunker.py` | `pytest backend/tests/unit/test_chunker_and_index.py` | `WORKING` | 384-dimensional dense vectors stored in ChromaDB collection. |
| **Stage 1 Lexical Retrieval (FTS5)** | `backend/app/models/entities.py`, `backend/app/ai/retrieval/hybrid_search.py` | `pytest backend/tests/unit/test_models.py`, `pytest backend/tests/unit/test_hybrid_rerank.py` | `WORKING` | SQLite FTS5 full-text search with BM25 rank ordering. |
| **Reciprocal Rank Fusion (RRF)** | `backend/app/ai/retrieval/hybrid_search.py` | `pytest backend/tests/unit/test_hybrid_rerank.py::test_hybrid_search_rrf_and_api` | `WORKING` | Combines dense and lexical ranks with $k=60$ formula: $\text{RRF}(d) = \sum \frac{1}{60 + r(d)}$. |
| **Stage 2 Cross-Encoder Re-Ranking** | `backend/app/ai/retrieval/reranker.py` | `pytest backend/tests/unit/test_hybrid_rerank.py::test_cross_encoder_reranker_scoring` | `WORKING` | Local PyTorch cross-encoder scoring pair `(query, passage)` with MinMax scaling. |
| **ML Evaluation Harness** | `backend/app/ai/retrieval/eval_metrics.py`, `backend/app/api/routes/eval.py` | `pytest backend/tests/unit/test_eval_metrics.py` | `WORKING` | Computes MRR@10, NDCG@10, and Recall@K formulas against golden test sets. |
| **Grounded Timestamped Video Q&A** | `backend/app/services/summary_service.py`, `backend/app/api/routes/search.py` | `pytest backend/tests/integration/test_clips_and_summary.py::test_ask_video_ai_grounded_citations` | `WORKING` | Synthesizes grounded answers citing verified timecode intervals `[mm:ss - mm:ss]`. |
| **Executive Summary & Chapters** | `backend/app/services/summary_service.py` | `pytest backend/tests/integration/test_clips_and_summary.py::test_summarize_video_api_grounded_and_cached` | `WORKING` | Generates structured summary bullets and chapter breakdowns cached in DB. |
| **FastMCP STDIO Server (8 Read-Only Tools)** | `mcp_server/server.py`, `mcp_server/tools/video_tools.py` | `mcp_server/server.py` | `WORKING` | Exposes 8 read-only retrieval tools over STDIO with JSON-RPC. |
| **Lossless Subclip Export** | `backend/app/processing/clip_export.py` | `pytest backend/tests/integration/test_clip_export.py` | `WORKING` | FFmpeg stream-copy subclip export bounded to `ALLOWED_MEDIA_ROOTS`. |
| **Hallmark Studio Workstation UI** | `frontend/src/features/media-library/MediaLibraryView.tsx`, `frontend/src/features/video-search/HybridSearchView.tsx` | `npm test --prefix frontend`, `npm run build --prefix frontend` | `WORKING` | 12-column responsive layout, precision scrubber, variable speeds, multi-track timeline. |
| **CLI `arova doctor` & `arova demo`** | Proposed in Spec §4.3 | Not yet implemented in root CLI package | `PLANNED` | Required for Launch 01 first-use experience. |
| **Thin Python SDK Wrapper** | Proposed in Spec §4.2 | Not yet extracted into standalone `arova-client` | `PLANNED` | REST API exists; thin client wrapper to be packaged. |
| **Night Shift Background Ingestion** | Older Master Plan | Excluded from Launch 01 by Spec v1.1 | `DEFERRED` | Gated research track after Release 3. |
| **Commercial Studio / Creator OS** | Private Roadmap | Excluded by Open Source Spec & AGENTS rules | `EXCLUDED` | Zero commercial IP permitted in this repository. |

---

## 2. Test Execution Summary

- **Backend & MCP Pytest:** 31 passed, 0 failed, 0 skipped in 5.09s (`pytest backend/tests mcp_server/tests -v`).
- **Frontend Vitest:** 4 test suites passed (6 tests), 0 failed in 6.81s.
- **Frontend Production Build:** `tsc -b && vite build` succeeded in 1.50s (bundle size 202 KB, 0 errors).
- **System Health Audit:** `scripts/system_health_audit.py` -> 7/7 PASSED (HEALTHY).

