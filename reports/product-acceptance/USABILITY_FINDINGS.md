# Arova Creator Intelligence — Usability & Human-Factors Walkthrough

**Document ID:** `REP-ACCEPT-003`  
**Date:** `2026-11-09`  
**Auditor:** Autonomous Product & Human-Factors Sentinel  
**Persona:** Solo Video Creator / YouTube & TikTok Documentarian (Never seen Arova before)  
**Primary Goal:** Organize 500 GB of documentary B-roll and talking-head footage, find specific quotes instantly, keep intelligence local, and export clean project memory to take on a laptop.

---

## 1. Executive Usability Assessment

Arova Creator Intelligence has made an immense architectural leap from a fragmented "collection of buttons" to a structured, 4-group operational cockpit. The addition of the **"How Arova Creator Intelligence Works — 3-Step Guided Workflow"** banner on the Mission Overview screen provides immediate orientation within 5 seconds.

However, several human-factors rough edges, technical jargon leaks, and mental model ambiguities were discovered during the audit. These do not crash the system, but they create user hesitation.

---

## 2. Detailed Findings & Usability Friction Matrix

| Finding ID | View / Component | Observed Friction | Creator Persona Reaction | Severity | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **UX-001** | **Studio Media Library** (`MediaLibraryView.tsx`) | Empty state when no folder is scanned shows a generic "No media assets indexed yet" message without a direct CTA button to Add Folder. | "I'm in my library, but where do I click to import my files? Do I drag and drop here?" | **MEDIUM** | Add a prominent primary button: `"Add Video Folder Now"`, which automatically switches navigation to `1. Add & Watch Folders`. |
| **UX-002** | **3. Archive & Export** (`StorageBackupView.tsx`) | The distinction between `.arova` memory archives (metadata + transcripts + scenes) and raw video files is stated in the banner text, but users might still expect video files to be inside the download. | "Wait, my export finished in 2 seconds and is only 350 KB. Did it fail to export my 4K video?" | **MEDIUM** | Emphasize: `"Your 4K source videos stay safely on your local disk. This archive carries 100% of the transcripts, visual cuts, and AI memory."` |
| **UX-003** | **Search & Ask Archive** (`HybridSearch.tsx`) | The search input placeholder says `"Search transcripts, visual concepts, or ask questions..."`, but does not explain that hybrid search combines lexical BM25 keyword matching with vector semantic embeddings. | "If I search 'red car', does it find words people said or things seen on screen?" | **LOW** | Add small filter pill chips under the search bar: `All Evidence`, `Spoken Dialogue`, `Visual Scenes / OCR`. |
| **UX-004** | **Engine Telemetry & Health** (`SystemHealthView.tsx`) | Several cards use dense backend terminology: `"DAG Task Queue"`, `"ACID WAL WAL2"`, `"ASR Whisper Medium FP16"`. | "What is a DAG? Did something break with my WAL?" | **LOW** | Provide tooltip hover explanations or subtitle labels: `"DAG Task Queue (Background Processing Jobs)"`, `"WAL Database (Crash-Resistant Storage)"`. |
| **UX-005** | **Privacy & BYO-AI** (`PrivacyAiView.tsx`) | Provider cards display technical context window numbers like `1048576 tokens` without translating to human units. | "What does 1,048,576 tokens mean for my video?" | **LOW** | Display human-readable equivalents alongside: `"~700 hours of spoken dialogue"` or `"~1M tokens"`. |
| **UX-006** | **Mission Overview** (`OverviewView.tsx`) | The 3-Step Workflow Banner is clean, but once a user has already indexed multiple libraries, the banner remains at the very top of Cockpit. | "I've already indexed 50 videos; I don't need the beginner instructions every time." | **LOW** | Add an optional `"Dismiss"` or collapse toggle for the onboarding banner, persisting user preference in `localStorage`. |

---

## 3. Workflow Usability Walkthroughs

### Workflow A: Initial Orientation (Mission Overview Cockpit)
- **Time to Understand Core Value:** ~4.5 seconds.
- **Visual Hierarchy:** Excellent. The 3-Step banner immediately answers:
  1. *What is this?* A local-first media intelligence system for video creators.
  2. *What do I do first?* Add a media folder in step 1.
  3. *What happens next?* The system transcribes, detects scene cuts, and indexes everything locally.
- **Hesitation Points:** None on the overview itself.

### Workflow B: Media Ingestion & Video Playback
- **Clarity:** High. Video cards list duration, resolution (e.g. 1280x720), and pipeline badges (`ASR: done`, `Scenes: done`).
- **Interactive Transcript Jump:** Clicking a transcript timestamp immediately seeks the video player to that second and resumes playback. This is an intuitive, delightful workflow for creators editing clips.

### Workflow C: Privacy & BYO-AI Configuration
- **Reassurance Level:** Very High. The top badge displays `100% LOCAL PRIVACY ENCLAVE` in green.
- **Provider Clarity:** The 4 cards clearly distinguish between the free offline local engine and remote cloud providers.
- **Credential Safety:** The password-type input for API keys and the "Test Connection" button provide immediate reassurance before any job runs.

### Workflow D: Portable Memory Export & Transfer
- **Workflow Experience:** The two distinct panels ("Export Portable Memory" vs. "Import Memory Archive") prevent confusion between exporting and importing.
- **Browser Download Flow:** Clicking "Create .arova Archive" generates the file and automatically triggers browser download, while providing an explicit "Download .arova Archive File" button if popups are blocked.
- **Dry-Run Preview:** Uploading an archive automatically runs a dry-run and displays the exact count of assets, transcripts, and scenes before committing to database import.

### Workflow E: Developer MCP Server
- **Value Delivery:** Instant. Ready-to-copy JSON configuration blocks for both `claude_desktop_config.json` and Cursor `.cursor/mcp.json`.
- **Safety Framing:** The `Read-Only Agent Enforcement` banner clearly reassures creators that external AI agents cannot delete or modify their video files.

---

## 4. Prioritized Usability Recommendations

1. **Immediate (P1):**
   - Add `"Add Video Folder Now"` button directly inside the empty-state view of Studio Media Library.
   - Refine the export completion modal in Storage & Backup with explicit text explaining why the archive file is compact.
2. **Next Milestone (P2):**
   - Add search mode filter pills (`Dialogue`, `Visuals`, `All`) to Hybrid Search.
   - Add token-to-video-hour translation in Privacy & BYO-AI model descriptions.
   - Add collapsible/dismissible state for the 3-step Cockpit banner.

