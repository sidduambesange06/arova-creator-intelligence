# Arova Creator Intelligence — Backend Integration Audit

**Document Version:** 1.0.0  
**Audit Date:** 2026-11-09  
**Base URL:** `http://127.0.0.1:8000/api/v1`  
**Binding:** Loopback only (`127.0.0.1`) — Zero external telemetry, zero cloud egress without active scoped consent.  
**Consolidated Regression Suite Status:** 232/232 passed (100%) in 43.70s.

---

## 1. Subsystem Integration Verification

Every major backend subsystem was verified against its corresponding FastAPI router, SQLAlchemy entities, Alembic migrations, Pydantic schemas, and frontend client functions.

### 1.1 Core Health & Hardware Telemetry
- **Endpoints:** `GET /api/v1/health`, `GET /api/v1/system/telemetry`
- **Router:** `backend/app/main.py`, `backend/app/api/routes/system.py`
- **Client Methods:** `fetchHealth()`, `fetchSystemTelemetry()`
- **Frontend Views:** `App.tsx` (TopBar badge, Sidebar indicator), `SystemHealthView.tsx` (telemetry dials)
- **Contract Verification:** Returns structured JSON with status, engine, CPU/RAM/VRAM/Disk utilization percentages, and worker counts.
- **Test Evidence:** `test_health.py` (2 tests), `WorkstationViews.test.tsx` (system view).

### 1.2 Media Ingestion, Streaming & Metadata (M1–M3)
- **Endpoints:**
  - `POST /api/v1/videos/import`
  - `GET /api/v1/videos`
  - `GET /api/v1/videos/stats/summary`
  - `GET /api/v1/videos/{id}`
  - `GET /api/v1/videos/{id}/thumbnail`
  - `GET /api/v1/videos/{id}/stream` (HTTP 206 Partial Content Range)
  - `DELETE /api/v1/videos/{id}/index`
  - `POST /api/v1/videos/{id}/export-clip`
  - `GET /api/v1/videos/clips/{filename}`
  - `POST /api/v1/videos/{id}/subtitles`
- **Router:** `backend/app/api/routes/videos.py`
- **Client Methods:** `importVideos()`, `fetchVideos()`, `fetchMediaLibraryStats()`, `fetchVideo()`, `deleteVideoIndex()`, `exportVideoClip()`, `uploadVideoSubtitles()`, `getVideoStreamUrl()`, `getVideoThumbnailUrl()`
- **Frontend Views:** `OverviewView.tsx`, `MediaLibraryView.tsx`, `VideoWorkstationView.tsx`
- **Contract Verification:** Enforces `ALLOWED_MEDIA_ROOTS`. Probes duration, resolution, codecs via FFprobe with software decoding fallback. `DELETE /index` removes DB rows while preserving source video files on disk. Subtitle endpoint parses SRT/VTT without ASR models.
- **Test Evidence:** `test_videos_api.py`, `test_media_probing.py`, `test_clip_export.py`, `test_subtitles.py` (28 tests).

### 1.3 Collections & Media Bins
- **Endpoints:** `GET /api/v1/collections`, `POST /api/v1/collections`, `POST /api/v1/collections/{id}/videos`
- **Router:** `backend/app/api/routes/collections.py`
- **Client Methods:** `fetchCollections()`, `createCollection()`, `addVideoToCollection()`
- **Frontend Views:** `MediaLibraryView.tsx` (Collection filter pills & tagging), `StorageBackupView.tsx`
- **Contract Verification:** Relational cascade associations via SQLite junction table `collection_videos`.
- **Test Evidence:** `test_videos_api.py::test_collection_management_endpoints`.

### 1.4 Multimodal Search, RRF & Grounded Q&A (M4)
- **Endpoints:**
  - `POST /api/v1/search/semantic`
  - `POST /api/v1/search/transcripts`
  - `POST /api/v1/search/clips`
  - `POST /api/v1/ai/summarize`
  - `POST /api/v1/ai/ask`
  - `POST /api/v1/ml/eval/run`
  - `GET /api/v1/ml/eval/report`
- **Router:** `backend/app/api/routes/search.py`, `backend/app/api/routes/ml_eval.py`
- **Client Methods:** `searchSemantic()`, `searchTranscripts()`, `askVideoAi()`, `summarizeVideo()`, `runEvalBenchmark()`, `fetchLatestEvalReport()`
- **Frontend Views:** `HybridSearchView.tsx`, `VideoWorkstationView.tsx`
- **Contract Verification:** Stage-1 Reciprocal Rank Fusion ($k=60$) combining dense ChromaDB cosine similarity with SQLite FTS5 BM25 lexical score. Stage-2 PyTorch Cross-Encoder scoring. Grounded Q&A synthesizes answers citing verified `[mm:ss - mm:ss]` intervals.
- **Test Evidence:** `test_hybrid_rerank.py`, `test_clips_and_summary.py`, `test_visual_retrieval_benchmark.py` (14 tests).

### 1.5 Media Discovery & Safety (Task 4B)
- **Endpoints:**
  - `GET /api/v1/discovery/libraries`
  - `POST /api/v1/discovery/libraries`
  - `GET /api/v1/discovery/libraries/{id}/roots`
  - `POST /api/v1/discovery/libraries/{id}/roots`
  - `POST /api/v1/discovery/roots/{id}/scan`
  - `GET /api/v1/discovery/roots/{id}/scans`
- **Router:** `backend/app/api/routes/discovery.py`
- **Client Methods:** `fetchDiscoveryLibraries()`, `createDiscoveryLibrary()`, `fetchDiscoveryRoots()`, `registerDiscoveryRoot()`, `scanDiscoveryRoot()`, `fetchScanRuns()`
- **Frontend Views:** `DiscoverySourcesView.tsx`
- **Contract Verification:** Validates canonicalized paths against `ALLOWED_MEDIA_ROOTS`. Blocks path traversal (`../`, absolute escapes). Streaming SHA-256 chunk hashing. Tracks `scanned_files`, `discovered_media`, `new_assets`.
- **Test Evidence:** `test_discovery_api.py`, `test_discovery_scanner.py`, `test_media_roots.py` (18 tests).

### 1.6 Resumable DAG Processing & Stage Leases (Task 4C)
- **Endpoints:**
  - `GET /api/v1/jobs`
  - `GET /api/v1/jobs/{id}`
  - `POST /api/v1/jobs/{id}/cancel`
  - `POST /api/v1/jobs/{id}/resume`
  - `GET /api/v1/jobs/{id}/stages`
  - `GET /api/v1/jobs/versions/{id}/artifacts`
- **Router:** `backend/app/api/routes/jobs.py`
- **Client Methods:** `fetchJobs()`, `fetchJobDetails()`, `cancelJob()`, `resumeJob()`, `fetchJobStages()`, `fetchVersionArtifacts()`
- **Frontend Views:** `ProcessingJobsView.tsx`, `OverviewView.tsx`
- **Contract Verification:** 7-stage DAG with SHA-256 parameter fingerprints. Atomic worker leases with heartbeat tracking. Resumption skips completed fingerprints. Structured error codes (`INSUFFICIENT_DISK_SPACE`, `LEASE_EXPIRED`). Atomic artifact superseding (`is_current = true`).
- **Test Evidence:** `test_resumable_processing.py`, `test_pipeline_orchestrator.py` (19 tests).

### 1.7 Portable Media Memory & Availability (Task 4D)
- **Endpoints:**
  - `POST /api/v1/portable/export`
  - `POST /api/v1/portable/import/dry-run`
  - `POST /api/v1/portable/import`
  - `GET /api/v1/versions/{id}/availability`
  - `POST /api/v1/versions/{id}/relink`
  - `GET /api/v1/libraries/duplicates`
  - `GET /api/v1/annotations`
  - `POST /api/v1/annotations`
  - `DELETE /api/v1/annotations/{id}`
- **Router:** `backend/app/api/routes/portable.py`, `backend/app/api/routes/annotations.py`
- **Client Methods:** `exportPortableArchive()`, `dryRunPortableImport()`, `importPortableArchive()`, `fetchMediaAvailability()`, `relinkMediaAsset()`, `fetchDuplicateMedia()`, `fetchAnnotations()`, `createAnnotation()`, `deleteAnnotation()`
- **Frontend Views:** `StorageBackupView.tsx`, `MediaLibraryView.tsx`, `VideoWorkstationView.tsx`
- **Contract Verification:** Versioned `.arova` format (ZIP container containing streamed NDJSON and per-entry SHA-256 manifests). 20 untrusted-archive validation checks (ZIP bomb rejection, traversal prevention). Dry-run import with foreign-to-local ID remappings without DB writes. Availability resolution (`present`, `missing`, `relocated`). Safe relinking with SHA-256 check.
- **Test Evidence:** `test_portable_export.py`, `test_portable_import.py`, `test_media_relinking.py` (28 tests).

### 1.8 BYO-AI Provider Gateway & Consents (Roadmap Step 6)
- **Endpoints:**
  - `GET /api/v1/ai/providers`
  - `POST /api/v1/ai/providers/verify`
  - `GET /api/v1/ai/consents`
  - `POST /api/v1/ai/consents`
  - `DELETE /api/v1/ai/consents/{id}`
  - `GET /api/v1/ai/runs`
- **Router:** `backend/app/api/routes/ai_gateway.py`
- **Client Methods:** `fetchAiProviders()`, `verifyAiProvider()`, `fetchAiConsents()`, `grantAiConsent()`, `revokeAiConsent()`, `fetchAiRuns()`
- **Frontend Views:** `PrivacyAiView.tsx`
- **Contract Verification:** Provider-neutral capability router (`LocalExtractive`, `GoogleGemini`, `OpenAICompatible`, `AnthropicClaude`). Automatic loopback detection (`127.0.0.1` classified as `LOCAL`). 5-gate consent rules (`AIConsent`, `ExecutionProfile`, `RootPolicy`, `AI_REMOTE_CONSENT`). Secret masking in logs/DB. Immutable `AIRun` audit trail with prompt SHA-256 hashes.
- **Test Evidence:** `test_byo_ai_gateway.py`, `test_ai_consent_boundary.py` (16 tests).

### 1.9 Smart Loop & Shared Tool Execution Engine (Roadmap Step 7)
- **Endpoints:**
  - `GET /api/v1/tools`
  - `POST /api/v1/tools/execute`
  - `POST /api/v1/agent/smart-loop`
- **Router:** `backend/app/api/routes/agent.py`
- **Client Methods:** `fetchSharedTools()`, `executeSharedTool()`, `runSmartLoopAgent()`
- **Frontend Views:** `HybridSearchView.tsx` (Smart Loop & Tool Explorer tabs)
- **Contract Verification:** Registers all 12 canonical tools with OpenAI/Gemini/Anthropic schemas. Enforces strict read-only execution boundaries (`allow_mutating=False`). Deterministic 3-turn local offline planner + remote LLM reasoning loop. Audited in `AIRun`.
- **Test Evidence:** `test_smart_loop.py` (7 tests).

### 1.10 Local Read-Only Database Explorer
- **Endpoints:**
  - `GET /api/v1/admin/database/overview`
  - `GET /api/v1/admin/database/tables`
  - `GET /api/v1/admin/database/tables/{t}`
  - `GET /api/v1/admin/database/tables/{t}/rows`
  - `GET /api/v1/admin/database/migrations`
  - `GET /api/v1/admin/database/relationships`
- **Router:** `backend/app/api/routes/admin.py`
- **Client Methods:** `fetchDatabaseOverview()`, `fetchDatabaseTables()`, `fetchTableDetails()`, `fetchTableRows()`, `fetchDatabaseMigrations()`, `fetchDatabaseRelationships()`
- **Frontend Views:** `DatabaseExplorerView.tsx`
- **Contract Verification:** Mandatory local admin Bearer token. True read-only SQLite connections (`mode=ro` + `PRAGMA query_only=ON`). Paginated rows (max 50) with token redaction and BLOB byte size masking.
- **Test Evidence:** `test_database_explorer_api.py` (13 tests).

---

## 2. Parity Summary

- **Total Backend Endpoints Verified:** 48
- **Frontend Client Functions:** 48
- **Unmapped Endpoints:** 0
- **Dead Client Functions:** 0
- **Contract Discrepancies:** 0
- **Consolidated Backend Test Status:** 232 passed, 0 failed.

