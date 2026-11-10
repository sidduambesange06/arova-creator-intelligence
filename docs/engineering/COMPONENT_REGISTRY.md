# Arova Creator Intelligence — Canonical Component Registry
**Document ID:** `REG-COMP-001`  
**Date:** November 10, 2026  
**Operating System:** V11.0  
**Subsystem:** Frontend & Integration Architecture  

---

## 1. Registry Architecture & Standards

Every frontend view and workstation capability in Arova Creator Intelligence is cataloged with its implementing paths, API contracts, security boundaries, and test coverage.

---

## 2. Component Directory

| Component Name | Purpose & Workflow | Source File Path | API Contracts | Security & Enclave Boundary | Associated Tests | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`App`** | Master workstation shell, 4 navigation groups, responsive mobile drawer, cross-view `selectedVideoId` + `selectedVideoStartTime` handoff, global Command Palette (`Ctrl+K`), ErrorBoundary encapsulation. | `frontend/src/App.tsx` | `GET /api/v1/health` | Loopback only (`127.0.0.1`), dev/prod stack-trace masking. | `App.test.tsx`, `ErrorBoundary.test.tsx` | **VERIFIED** |
| **`OverviewView`** | Studio cockpit, 3-step creator onboarding banner, quick stats, recent media, health pulse. | `frontend/src/features/overview/OverviewView.tsx` | `/api/v1/videos`, `/api/v1/system/telemetry` | Read-only inspection; zero cloud telemetry. | `WorkstationViews.test.tsx` | **VERIFIED** |
| **`DiscoverySourcesView`** | Step 1 of workflow: discovery libraries, media roots, allowed paths, scan execution history. | `frontend/src/features/discovery/DiscoverySourcesView.tsx` | `GET /api/v1/libraries`, `POST /api/v1/libraries`, `GET /api/v1/libraries/{id}/roots`, `POST /api/v1/libraries/roots/{id}/scan` | Strict `ALLOWED_MEDIA_ROOTS` deny-by-default boundary. | `WorkstationViews.test.tsx` | **VERIFIED** |
| **`MediaLibraryView`** | Media vault, collection categorization, video asset cards, direct timecode handoff to Precision Workstation. | `frontend/src/features/media-library/MediaLibraryView.tsx` | `/api/v1/videos`, `/api/v1/collections`, `/api/v1/videos/import` | Source media read-only immutability. | `MediaLibrary.test.tsx` | **VERIFIED** |
| **`VideoWorkstationView`** | Dedicated precision video workstation: SMPTE HUD, frame-step (`-1f`/`+1f`), step-seek (`-5s`/`+5s`), scene navigation (`Prev`/`Next Scene`), speed (`0.5x..2x`), visual `[In, Out]` range scrubber with scene ticks, `Preview Selection`, honest stream-copy/re-encode MP4 clip export, transcript filter, scene keyframe thumbnails, clickable AI chapters, sidecar subtitles, notes. | `frontend/src/features/workstation/VideoWorkstationView.tsx` | `/api/v1/videos/{id}/stream`, `/api/v1/videos/{id}/transcript`, `/api/v1/videos/{id}/scenes`, `/api/v1/videos/{id}/scenes/{idx}/thumbnail`, `/api/v1/videos/{id}/export-clip` | HTTP 206 partial streaming; read-only source media; honest keyframe stream copy vs H.264 fallback. | `WorkstationViews.test.tsx` | **VERIFIED** |
| **`ProcessingJobsView`** | Step 2 of workflow: 7-stage DAG visualization, stage run status, cancel, resume, artifact browser. | `frontend/src/features/processing/ProcessingJobsView.tsx` | `GET /api/v1/jobs`, `POST /api/v1/jobs/{id}/cancel`, `POST /api/v1/jobs/{id}/resume`, `/api/v1/artifacts` | Lease-based concurrency locking; idempotent skip. | `WorkstationViews.test.tsx` | **VERIFIED** |
| **`HybridSearchView`** | Step 3 of workflow: Retrieval-layer channel filtering (`all`, `speech`, `visual`, `multimodal`), Dense + BM25 RRF hybrid retrieval, cross-encoder reranker, grounded Q&A with active channel enforcement, Smart Loop Agent, Shared Tool Explorer. | `frontend/src/features/video-search/HybridSearchView.tsx` | `POST /api/v1/search/semantic`, `POST /api/v1/ai/ask`, `POST /api/v1/agent/smart-loop`, `GET /api/v1/tools`, `POST /api/v1/tools/execute` | Zero remote telemetry; local extractive fallback; read-only tool gating. | `HybridSearch.test.tsx` | **VERIFIED** |
| **`PrivacyAiView`** | BYO-AI Provider Gateway: Local, OpenAI, Anthropic, Gemini; consent granting, revocation, token budgets. | `frontend/src/features/privacy-ai/PrivacyAiView.tsx` | `/api/v1/ai/providers`, `/api/v1/ai/consents`, `/api/v1/ai/runs` | 5-gate non-bypassable consent; ephemeral RAM keys. | `WorkstationViews.test.tsx` | **VERIFIED** |
| **`StorageBackupView`** | Step 3 of media ops: `.arova` archive export, dry-run schema preview, safe restoration, media relinking. | `frontend/src/features/storage/StorageBackupView.tsx` | `/api/v1/portable/exports`, `POST /api/v1/portable/import/dry-run`, `/api/v1/portable/relink` | Path traversal, zip bomb, and tamper defenses. | `WorkstationViews.test.tsx` | **VERIFIED** |
| **`McpConfigView`** | FastMCP server status, 12 tools contract (11 read-only, 1 gated), Claude Desktop and Cursor JSON configs. | `frontend/src/features/settings/McpConfigView.tsx` | `GET /api/v1/tools` | Read-only enforcement; mutating ops gated. | `McpConfig.test.tsx` | **VERIFIED** |
| **`DatabaseExplorerView`** | Developer SQLite table schema browser, row viewer, migration revisions, table relations. | `frontend/src/features/database-explorer/DatabaseExplorerView.tsx` | `/api/v1/database/tables`, `/api/v1/database/rows`, `/api/v1/database/migrations` | Gated by secret dev token. | `DatabaseExplorer.test.tsx` | **VERIFIED** |
| **`SystemHealthView`** | Core engine health diagnostics, memory, CPU, DB WAL status, ASR model load state. | `frontend/src/features/system/SystemHealthView.tsx` | `GET /api/v1/health`, `GET /api/v1/system/telemetry` | Zero remote telemetry. | `WorkstationViews.test.tsx` | **VERIFIED** |

