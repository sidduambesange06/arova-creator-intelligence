# Arova Creator Intelligence — Post-Acceptance Engineering Repair Backlog

**Document ID:** `REP-ACCEPT-004`  
**Date:** `2026-11-09`  
**Subsystem:** Overall Product, Frontend, Backend, Database, MCP & UX  
**Status:** Approved for Prioritized Implementation  

---

## 1. Backlog Summary & Prioritization Matrix

| Priority | Definition | Target Window | Total Items |
| :--- | :--- | :--- | :--- |
| **P0 — Critical** | System crash, data loss risk, privacy breach, or broken core workflow. | Immediate fix (All 3 verified resolved in commit `33faffd`) | 0 Active (3 Resolved) |
| **P1 — High** | Core feature rough edges, empty-state navigation dead ends, high user friction. | Next Sprint / Milestone | 2 Active |
| **P2 — Medium** | Usability polish, technical terminology minimization, search filtering enhancements. | Next Milestone | 3 Active |
| **P3 — Low** | Cosmetic enhancements, collapsible onboarding widgets, advanced telemetry visualizers. | Future Roadmap | 2 Active |

---

## 2. P0: Critical Defects (Previously Identified & Verified Resolved)

### [RESOLVED] ISS-016: Portable Memory Archive Export Download Failure
- **Priority:** P0 (Critical)
- **Subsystem:** Backend (`portable.py`, `portable_service.py`) & Frontend (`StorageBackupView.tsx`)
- **Problem:** Users clicked "Export Portable Archive", but the browser received a server path rather than downloading the `.arova` file.
- **Root Cause:** Missing `GET /api/v1/portable/exports/{filename}` download route with path traversal sanitization, and missing client-side download anchor trigger.
- **Resolution:** Implemented secure download endpoint with path-traversal denial (`..`, `/`, `\`), added automatic client-side blob download trigger, and verified full round-trip export in commit `33faffd`.
- **Status:** **VERIFIED RESOLVED (100% Round-trip pass in `scratch/verify_archive_roundtrip.py`).**

### [RESOLVED] ISS-017: Privacy & BYO-AI View Blank/Black Screen Exception
- **Priority:** P0 (Critical)
- **Subsystem:** Frontend (`PrivacyAiView.tsx`, `api.ts`, `ErrorBoundary.tsx`)
- **Problem:** Clicking "Privacy & BYO-AI" resulted in a completely blank/black screen.
- **Root Cause:** API response payload shape mismatch (array vs `{ providers, models }` object) and unhandled `null` latency values triggering uncaught JavaScript TypeErrors.
- **Resolution:** Built React `ErrorBoundary`, normalized `fetchAiProviders` / `fetchAiConsents`, added defensive array guards (`safeProviders`, `safeConsents`, `safeRuns`), and safe latency formatting.
- **Status:** **VERIFIED RESOLVED (DOM audit verified provider cards render cleanly with zero black screens).**

### [RESOLVED] ISS-018: Production ErrorBoundary Diagnostic Disclosure
- **Priority:** P0 (Security Hardening)
- **Subsystem:** Frontend (`ErrorBoundary.tsx`)
- **Problem:** Component stack traces containing local workspace paths were potentially visible in production fallback UI.
- **Root Cause:** `<pre>{this.state.errorInfo.componentStack}</pre>` rendered unconditionally.
- **Resolution:** Gated stack trace rendering to `import.meta.env.DEV` only. In production builds, only user-friendly diagnostic guidance is shown with "Reload View" and "Reset to Cockpit" CTAs.
- **Status:** **VERIFIED RESOLVED (`tsc -b && vite build` and `ErrorBoundary.test.tsx` pass).**

---

## 3. P1: High-Priority Usability & Workflow Polish

### BL-001: Media Library Empty-State Direct Folder Navigation CTA
- **Priority:** P1 (High)
- **Subsystem:** Frontend (`MediaLibraryView.tsx`)
- **Problem:** When zero media folders have been added, the Studio Media Library displays `"No media assets indexed yet"` without a clickable action to guide the creator.
- **Recommended Solution:** Add a primary CTA button: `"Add Video Folder Now"`, which calls `onNavigate("discovery-roots")` to immediately transition to folder onboarding.
- **Verification Criteria:** Empty state renders primary button; clicking button transitions sidebar to `1. Add & Watch Folders`.
- **Estimated Effort:** 0.5 hours.

### BL-002: Storage & Backup Export Clarification Notice
- **Priority:** P1 (High)
- **Subsystem:** Frontend (`StorageBackupView.tsx`)
- **Problem:** Creators unfamiliar with `.arova` memory containers may mistakenly believe a 350 KB export failed to include their 4K source video footage.
- **Recommended Solution:** In the export success banner, add explicit copy: `"Your 4K source video binaries remain untouched on your local disk. This archive carries 100% of the transcribed dialogue, detected scene cuts, visual tokens, and AI memory for instant cross-machine transfer."`
- **Verification Criteria:** Export completion card renders the clarification notice.
- **Estimated Effort:** 0.5 hours.

---

## 4. P2: Medium-Priority Usability & Search Enhancements

### BL-003: Hybrid Search Scope & Evidence Filtering Chips
- **Priority:** P2 (Medium)
- **Subsystem:** Frontend (`HybridSearch.tsx`) & Backend (`search_service.py`)
- **Problem:** Creators cannot easily restrict search queries to dialogue transcripts only or visual scene OCR only.
- **Recommended Solution:** Add three clickable pill chips under the search input: `All Evidence`, `Spoken Dialogue Only`, and `Visual Scene OCR Only`. Pass `evidence_type` query param to `/api/v1/search/hybrid`.
- **Verification Criteria:** Selecting `Spoken Dialogue Only` filters out non-transcript OCR results in the search results list.
- **Estimated Effort:** 1.5 hours.

### BL-004: Telemetry Technical Jargon Simplification
- **Priority:** P2 (Medium)
- **Subsystem:** Frontend (`SystemHealthView.tsx`)
- **Problem:** Cards display dense backend terms such as `"DAG Task Queue"`, `"ACID WAL WAL2"`, `"ASR Whisper Medium FP16"`.
- **Recommended Solution:** Add user-friendly subtitles to each telemetry card:
  - `"Task Processing Pipeline (DAG Queue)"`
  - `"Storage Health (SQLite WAL2 Mode)"`
  - `"Speech Recognition Engine (Local Whisper Medium)"`
- **Verification Criteria:** Telemetry view displays clear, human-understandable subtitles under each technical card.
- **Estimated Effort:** 1.0 hour.

### BL-005: AI Context Window Human Units Display
- **Priority:** P2 (Medium)
- **Subsystem:** Frontend (`PrivacyAiView.tsx`)
- **Problem:** Model cards list raw token numbers (e.g. `1048576 tokens`, `128000 tokens`) which mean little to a video creator.
- **Recommended Solution:** Calculate and display human-readable video equivalents: `context_window >= 1000000 ? "~700 hrs of dialogue" : "~85 hrs of dialogue"`.
- **Verification Criteria:** Model cards display video hour capacity next to token counts.
- **Estimated Effort:** 0.5 hours.

---

## 5. P3: Low-Priority Polish & Roadmap Enhancements

### BL-006: Dismissible Onboarding Banner with LocalStorage Persistence
- **Priority:** P3 (Low)
- **Subsystem:** Frontend (`OverviewView.tsx`)
- **Problem:** Once an experienced creator has indexed dozens of video folders, the 3-step beginner banner occupies top screen real estate.
- **Recommended Solution:** Add a small `Dismiss` or `Minimize` button on the banner that stores `arova_onboarding_dismissed: true` in `localStorage`.
- **Verification Criteria:** Dismissing the banner hides it across page reloads until user clicks "Show Guide".
- **Estimated Effort:** 1.0 hour.

### BL-007: Visual Video Relink Dropzone in Media Library
- **Priority:** P3 (Low)
- **Subsystem:** Frontend (`MediaLibraryView.tsx`)
- **Problem:** If a video file is moved, the backend supports `POST /api/v1/versions/{id}/relink`, but the frontend only shows "Missing offline" without a direct file dropzone on the player.
- **Recommended Solution:** When a video has `can_play === false`, display a "Locate Missing Video File" button directly on the video player container, allowing the user to pick the relocated file on disk and auto-trigger relinking.
- **Verification Criteria:** Dropping or selecting moved video file triggers relink API call and resumes playback.
- **Estimated Effort:** 2.0 hours.

