# Arova Creator Intelligence — Complete Frontend Workflow Audit & Backlog Ranking
**Sprint:** Frontend Workflow Improvement Sprint (V10.1)  
**Date:** November 10, 2026  
**Auditor:** Principal Frontend Architect & Senior UX Systems Engineer  
**Baseline Git HEAD:** `4e67e87`  
**Test Host:** `127.0.0.1:5173` (Frontend) & `127.0.0.1:8000` (FastAPI Engine)  

---

## 1. Executive Audit Summary

A comprehensive, live-browser audit of all 11 workstation views was conducted against the running FastAPI backend.

### Key Audit Findings:
1. **Critical Defect (Broken Discovery API):** Navigation to `1. Add & Watch Folders` (`discovery-roots` / `DiscoverySourcesView.tsx`) immediately fails with `Failed to load discovery libraries (HTTP 404)`. The root cause is `frontend/src/services/api.ts` prefixing library endpoints with `/api/v1/discovery/libraries` instead of the canonical backend route `/api/v1/libraries`. As a result, creators cannot view registered folders, add media roots, or trigger folder scans from the UI.
2. **First-Step Usability Disconnect:** The 3-Step Guided Banner on Mission Overview points users to Step 1: "Add & Watch Folders". When clicked, the broken API traps the user in an error state. In addition, the Media Library (`MediaLibraryView.tsx`) lacks a direct CTA to navigate to folder management when empty.
3. **Redundant Workstation Duplication:** `MediaLibraryView.tsx` currently labels itself "Studio Video Workstation" and duplicates a 16:9 video player, timeline scrubber, and transcript pane, creating cognitive overlap with the dedicated `Precision Workstation` (`VideoWorkstationView.tsx`).
4. **Search Evidence Usability:** `HybridSearchView.tsx` connects cleanly to `/api/v1/search/semantic`, but creators cannot filter results between dialogue speech and visual OCR scenes.
5. **Technical Jargon in Telemetry:** `SystemHealthView.tsx` exposes raw internal terms (`ACID WAL WAL2`, `DAG Task Queue`) that confuse non-technical creators.

---

## 2. Comprehensive 11-View Audit Matrix

| View ID & Name | Route / Nav | Real Backend Endpoints | Audit Observations & Defects | Status |
| :--- | :--- | :--- | :--- | :--- |
| **01. Mission Overview** | `overview` | `/api/v1/health`, `/api/v1/videos`, `/api/v1/system/telemetry` | Clean 3-step banner (`Add Directory` $\to$ `Run Ingestion` $\to$ `Search Moments`). Correctly routes to workstation on video click. | **FUNCTIONAL** |
| **02. Studio Media Library** | `media-library` | `/api/v1/videos`, `/api/v1/collections` | Heading confusingly reads "Studio Video Workstation". Duplicates player from `workstation`. Empty state lacks CTA button to `1. Add & Watch Folders`. | **USABILITY FRICTION** |
| **03. Precision Workstation** | `workstation` | `/api/v1/videos`, `/api/v1/videos/{id}/stream`, `/api/v1/transcripts/{id}`, `/api/v1/scenes/{id}`, `/api/v1/annotations` | Full SMPTE timecode HUD, custom scrubber, in/out lossless clip export, sidecar subtitles, timestamped notes. Excellent execution. | **VERIFIED** |
| **04. 1. Add & Watch Folders** | `discovery-roots` | `/api/v1/libraries` (Mismatched in `api.ts` as `/discovery/libraries`) | **CRITICAL DEFECT: HTTP 404** on mount. Prevents viewing 40 registered roots, adding new folders, or triggering scans. | **BROKEN (HTTP 404)** |
| **05. 2. Processing Pipelines** | `processing-jobs` | `/api/v1/jobs`, `/api/v1/jobs/{id}/stages`, `/api/v1/artifacts` | Renders canonical DAG stages (probe, audio, whisper, scenes, embeddings, search, provenance). 5s polling. | **FUNCTIONAL** |
| **06. 3. Archive & Export** | `storage-backup` | `/api/v1/portable/exports`, `/api/v1/portable/import/dry-run` | Roundtrip export/import verified in `33faffd`. Needs copy notice that 4K binaries remain on disk. | **VERIFIED** |
| **07. Search & Ask Archive** | `hybrid-search` | `/api/v1/search/semantic`, `/api/v1/ai/ask`, `/api/v1/tools` | Dense + BM25 RRF search operates offline. Grounded Q&A with timecode receipts. Lacks speech vs visual filter chips. | **FUNCTIONAL** |
| **08. Privacy & BYO-AI** | `privacy-ai` | `/api/v1/ai/providers`, `/api/v1/ai/consents`, `/api/v1/ai/runs` | Fixed black screen in `33faffd`. 4 provider cards (Local, OpenAI, Anthropic, Gemini). Ephemeral key input. | **VERIFIED** |
| **09. MCP Agent Server** | `mcp-config` | `/api/v1/tools` | 12 tools status (11 read-only, 1 gated). Claude Desktop and Cursor JSON copy blocks. | **VERIFIED** |
| **10. Database Explorer** | `database-explorer`| `/api/v1/database/*` | Protected SQLite table and migration viewer for developers. | **VERIFIED** |
| **11. Telemetry & Health** | `system` | `/api/v1/health`, `/api/v1/system/telemetry` | Real system metrics. Could use friendlier subtitles for technical terminology. | **FUNCTIONAL** |

---

## 3. Workflow Ranking & Prioritization Matrix

Each workflow was evaluated across 7 weighted criteria (Scale 1–10):
1. **User Impact:** Severity of obstruction to the user's primary goal.
2. **Frequency:** Likelihood of everyday creator usage.
3. **Severity:** Confusion, failure, or loss of trust caused by the issue.
4. **Product Importance:** Centrality to Arova's core value proposition.
5. **Improvement Leverage:** Ratio of user benefit to implementation complexity.
6. **Implementation Risk:** Probability of breaking existing stable contracts (Inverse: 10 = Lowest Risk).
7. **Verification Feasibility:** Ease of objective, reproducible verification.

### Ranking Table

| Rank | Workflow Name | Focus Area & Files | User Impact | Freq | Sev | Prod Imp | Lev | Low Risk | Verif | Total Score | Priority Tier |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | **Media Ingestion & Folder Discovery** | `api.ts`, `DiscoverySourcesView.tsx`, `MediaLibraryView.tsx` | 10 | 10 | 10 | 10 | 9 | 9 | 10 | **68 / 70** | **P0 (Critical Blocker)** |
| **2** | **Hybrid Search & Evidence Filtering** | `HybridSearchView.tsx`, `search.py` | 8 | 9 | 6 | 9 | 8 | 9 | 9 | **58 / 70** | **P1 (High)** |
| **3** | **Precision Workstation vs Library Demarcation** | `MediaLibraryView.tsx`, `VideoWorkstationView.tsx` | 7 | 8 | 6 | 8 | 8 | 8 | 9 | **54 / 70** | **P1 (High)** |
| **4** | **Storage & Archive User Reassurance** | `StorageBackupView.tsx` | 6 | 6 | 5 | 7 | 8 | 9 | 10 | **51 / 70** | **P2 (Medium)** |
| **5** | **System Telemetry Jargon Simplification** | `SystemHealthView.tsx` | 5 | 5 | 4 | 6 | 9 | 9 | 10 | **48 / 70** | **P2 (Medium)** |
| **6** | **Privacy AI Human Video Units** | `PrivacyAiView.tsx` | 5 | 4 | 3 | 6 | 8 | 9 | 10 | **45 / 70** | **P2 (Medium)** |

---

## 4. Phase 3: Selection of Coherent Workflow

### Selected Workflow: **Media Ingestion, Folder Discovery & Library Onboarding (Rank #1)**

#### 1. Current User Journey & Friction:
- A video creator launches Arova for the first time.
- On the Overview Cockpit, they read: *"Step 1: Add Media Folder"*.
- They click *"Add Video Folder Now"* and navigate to `1. Add & Watch Folders`.
- **Failure:** The view flashes `Failed to load discovery libraries (HTTP 404)`. The library dropdown is empty. The list of active media roots shows `(0)` despite 40 roots existing in the database.
- The creator attempts to register a folder, but the form is disabled because `selectedLibraryId` is empty.
- The creator tries navigating to `Studio Media Library`, but the page says *"Studio Video Workstation"* and displays a video player with no guidance on how to link their local footage.
- **Outcome:** The creator cannot ingest their media and abandons the application.

#### 2. Intended New Experience (Cinematic Instrument):
- **Contract Correction:** `api.ts` correctly points to `/api/v1/libraries`, `/api/v1/libraries/{id}/roots`, and `/api/v1/libraries/roots/{id}/scan`.
- **Immediate Orientation:** When opening `1. Add & Watch Folders`, the creator sees their primary library (e.g. *"Primary Studio MediaVault"*) selected automatically with live counts of registered directories and scan history.
- **Clear Enclave Policy Badging:** Each folder clearly displays its policy badge (`Strict Zero-Cloud Egress` vs `Eligible for BYO-AI`).
- **One-Click Live Scan Trigger:** Clicking *"Scan Folder Now"* triggers an immediate folder scan, showing a progress spinner and immediate, informative results (`Discovered X video files, Y new assets indexed`).
- **Seamless Transition to Media Library:** After scanning, a clear CTA appears: *"View Discovered Videos in Media Library $\to$"*.
- **Media Library Empty State:** When empty, `MediaLibraryView.tsx` displays a focused empty state with a primary button: *"Add Video Folder Now"*, which transitions the creator directly to `1. Add & Watch Folders`.

#### 3. Affected Components & Contracts:
- `frontend/src/services/api.ts`: Fix endpoints to `/api/v1/libraries` (replacing `/api/v1/discovery/libraries`).
- `frontend/src/features/discovery/DiscoverySourcesView.tsx`: Refine to Cinematic Instrument styling, add scan progress indicators, clear folder status badges, and bridge CTA to Media Library.
- `frontend/src/features/media-library/MediaLibraryView.tsx`: Add `onNavigate` prop so empty state can route to `discovery-roots`; fix header from "Studio Video Workstation" to "Studio Media Library & Vault".
- `frontend/src/App.tsx`: Pass `onNavigate` to `MediaLibraryView`.

#### 4. Acceptance Criteria:
1. `GET /api/v1/libraries` returns HTTP 200 and loads libraries into `DiscoverySourcesView`.
2. Existing media roots load and render with zero 404 errors.
3. Adding a new media root registers the path and immediately updates the active roots list.
4. Clicking "Scan Folder Now" executes `/api/v1/libraries/roots/{id}/scan` and updates the scan run history with discovered file counts.
5. In `MediaLibraryView`, empty state displays a primary button that transitions the user to `1. Add & Watch Folders`.
6. Header in `MediaLibraryView` is distinct from `VideoWorkstationView`.
7. All automated tests pass (`vitest` and `pytest`).
8. Before-and-after screenshots across 5 viewports prove responsive visual clarity.
