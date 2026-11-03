# Arova Creator Intelligence — Feature Reality Status

**Document Class:** Capability Verification Matrix
**Status:** Active Developer Preview / Alpha
**Verification Environment:** Python 3.11, Node.js 20, PyTorch 2.6.0+cpu, FastAPI 0.115, React 18

Every capability claim in the project documentation and README is mapped below to its source implementation, automated test suite, and certified status (`WORKING`, `WORKING (SYNTHETIC)`, `WORKING (DISCOVERY)`, `WORKING (OPT-IN)`, `EXPERIMENTAL`, `PARTIAL`, `DEFERRED`, `EXCLUDED`).

---

## 1. Feature Verification Matrix

| Claim / Capability | Source Code Location | Verification Test / Command | Verified Status | Evidence Notes |
|---|---|---|---|---|
| **Local Video Ingestion & Probe** | `backend/app/processing/metadata.py` | `pytest backend/tests/unit/test_media_probing.py` | `WORKING` | Probes duration, resolution, fps, codec via `ffprobe` (with ffmpeg stderr parsing fallback). |
| **Path Traversal Protection** | `backend/app/core/security.py` | `pytest backend/tests/unit/test_media_probing.py::test_path_traversal_protection_and_discovery` | `WORKING` | Strictly rejects paths outside configured `ALLOWED_MEDIA_ROOTS`. |
| **Thumbnail Extraction** | `backend/app/processing/thumbnails.py` | `pytest backend/tests/unit/test_media_probing.py::test_ffmpeg_metadata_probe_and_thumbnail` | `WORKING` | Generates 1-second interval JPEG thumbnails via `ffmpeg`. |
| **HTTP 206 Partial Streaming** | `backend/app/api/routes/videos.py` | `pytest backend/tests/integration/test_videos_api.py` | `WORKING` | Supports byte-range requests for video scrubber seeking. |
| **Content-Aware Scene Detection** | `backend/app/processing/scene_detection.py` | `pytest backend/tests/unit/test_audio_and_scenes.py::test_detect_video_scenes` | `WORKING` | Detects scene boundaries with threshold fallback for synthetic media. |
| **Offline Speech ASR** | `backend/app/ai/providers/transcription.py` | `pytest backend/tests/unit/test_transcription.py` | `WORKING` | `faster-whisper` integration with deterministic acoustic fallback when weights absent. |
| **Visual OCR Dual Memory** | `backend/app/processing/visual_text.py`, `backend/app/ai/retrieval/chunker.py` | `pytest backend/tests/unit/test_visual_text.py` | `EXPERIMENTAL` | Basic heuristic OCR extraction; fuses into transcript chunks with `[On-Screen Visual Text]` tags. |
| **Stage 1 Dense Semantic Retrieval** | `backend/app/ai/providers/embeddings.py`, `backend/app/ai/retrieval/chunker.py` | `pytest backend/tests/unit/test_chunker_and_index.py` | `WORKING` | 384-dimensional dense vectors stored in local ChromaDB collection. |
| **Stage 1 Lexical Retrieval (FTS5)** | `backend/app/models/entities.py`, `backend/app/ai/retrieval/hybrid_search.py` | `pytest backend/tests/unit/test_models.py`, `pytest backend/tests/unit/test_hybrid_rerank.py` | `WORKING` | SQLite FTS5 full-text search with BM25 rank ordering and token sanitization. |
| **Reciprocal Rank Fusion (RRF)** | `backend/app/ai/retrieval/hybrid_search.py` | `pytest backend/tests/unit/test_hybrid_rerank.py::test_hybrid_search_rrf_and_api` | `WORKING` | Combines dense and lexical ranks with $k=60$ formula: $\text{RRF}(d) = \sum \frac{1}{60 + r(d)}$. |
| **Stage 2 Cross-Encoder Re-Ranking** | `backend/app/ai/retrieval/cross_encoder_reranker.py` | `pytest backend/tests/unit/test_hybrid_rerank.py::test_cross_encoder_reranker_scoring` | `WORKING` | Local PyTorch cross-encoder scoring pair `(query, passage)` with MinMax scaling. |
| **100-Query Multimodal Benchmark** | `sample_data/visual_retrieval_golden_100.json`, `reports/audit/BENCHMARK_100_QUERIES.md` | `pytest backend/tests/benchmarks/test_visual_retrieval_benchmark.py` | `WORKING (SYNTHETIC)` | Evaluated on curated 100-query synthetic multimodal set; validation on real footage deferred to Beta. |
| **500-Video Scale & Recovery** | `backend/tests/stress/test_large_library_stress.py` | `pytest backend/tests/stress/test_large_library_stress.py` | `WORKING (DISCOVERY)` | Evaluates 500-video filesystem scanning, SHA-256 deduplication, and crash recovery (not full ASR indexing). |
| **Prompt-Injection Defense** | `backend/app/services/summary_service.py` | `pytest backend/tests/security/test_prompt_injection_redteam.py` | `WORKING (HEURISTIC)` | Regex pattern neutralization and XML boundary isolation; verified against 215 red-team test cases. |
| **Grounded Timestamped Video Q&A** | `backend/app/services/summary_service.py`, `backend/app/api/routes/search.py` | `pytest backend/tests/integration/test_clips_and_summary.py::test_ask_video_ai_grounded_citations` | `WORKING` | Synthesizes grounded answers citing verified timecode intervals `[mm:ss - mm:ss]`. |
| **Executive Summary & Chapters** | `backend/app/services/summary_service.py` | `pytest backend/tests/integration/test_clips_and_summary.py::test_summarize_video_api_grounded_and_cached` | `WORKING` | Generates structured summary bullets and chapter breakdowns cached in DB. |
| **FastMCP STDIO Server (8 Read-Only Tools)** | `mcp_server/server.py`, `mcp_server/tools/video_tools.py` | `pytest mcp_server/tests/test_mcp_tools.py` | `WORKING` | Exposes 8 read-only retrieval tools over STDIO; `export_video_clip` absent by default. |
| **Lossless Subclip Export** | `backend/app/processing/clip_export.py` | `pytest backend/tests/integration/test_clip_export.py` | `WORKING (OPT-IN)` | FFmpeg stream-copy subclip export; gated behind developer opt-in on MCP (`--enable-exports`). |
| **Arova Web Workstation UI** | `frontend/src/features/media-library/MediaLibraryView.tsx`, `frontend/src/features/video-search/HybridSearchView.tsx` | `npm test --prefix frontend`, `npm run build --prefix frontend` | `WORKING` | Responsive layout, precision scrubber, variable speeds, multi-track timeline. |
| **CLI `arova doctor`** | `backend/app/cli/doctor.py`, `backend/app/cli/main.py` | `pytest backend/tests/cli/test_doctor.py` | `WORKING` | Non-destructive diagnostic checking Python, FFmpeg, SQLite FTS5, disk, and MCP readiness. |
| **CLI `arova demo`** | `backend/app/cli/demo.py`, `backend/app/cli/main.py` | `pytest backend/tests/cli/test_demo.py` | `WORKING` | Instant synthetic first-use flow without external credentials (verified in < 1s). |
| **Thin Python SDK Wrapper** | `arova/client.py` | `pytest backend/tests/cli/test_client.py` | `WORKING` | Zero-dependency REST client wrapper (`ArovaClient`) for health, videos, search, and Q&A. |
| **Desktop GUI MCP Clients** | `docs/INTEGRATIONS.md` | FastMCP STDIO schema verified | `DOCUMENTED` | Claude Desktop and Cursor configurations verified at schema layer; live GUI click-through verified by user. |
| **Privacy & Loopback Audit** | `backend/app/core/security.py`, `backend/app/main.py` | Static code & socket audit | `WORKING` | Loopback binding (`127.0.0.1`) and zero telemetry verified via code audit. |
| **Commercial Studio / Creator OS** | N/A | Excluded by Open Source Spec | `EXCLUDED` | Zero commercial IP permitted in this open-source repository. |
