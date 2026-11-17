# Stitch Integration Map: The Cinematic Instrument Workstation

**Document Version:** 1.0.0  
**Status:** Approved Engineering Blueprint  
**Design System Identity:** The Cinematic Instrument (`cinematic_instrument/DESIGN.md`)  
**Theme Philosophy:** Instrument-Grade Restraint, Local-First Enclave, Tabular Precision, High Information Density

---

## 1. Design Asset Inventory

Two batches of Stitch design assets were analyzed and integrated:
- **Batch 01 (15 Screens + Design Specification):** Complete end-to-end workstation layout and full navigation topology.
- **Batch 02 (6 Refinement Screens + Design Specification):** Deepened component specifications, precision subtitles, right-hand inspector, index maintenance, feedback states, and responsive breakpoints.

### Batch 01 — Baseline Screen Inventory

| Screen Folder | Purpose & Visual Topology | Key Interactive Elements |
|---|---|---|
| `overview` | Mission Control cockpit, library telemetry matrix, quick actions | Index Media button, Ask Archive console, 6 KPI tiles, Live DAG pipeline bar |
| `media_library` | Asset browser, media grid, filter rail, processing badges | Search bar, collection selector, sort toggle, video cards with status tags |
| `video_workstation` | Frame-accurate inspection, video player, timeline view | Precision player, SMPTE timecode scrubber, transcript track, scene cut pins |
| `search_ask` | Multimodal semantic search, hybrid RRF, Grounded Q&A | Search input, Cross-Encoder toggle, Ask Archive with citations, Clip Export |
| `mcp_server` | Agent integration gateway, tool catalog, client configurations | 12 read-only tools + 1 write tool, Claude/Cursor/VSCode/Antigravity JSON snippets |
| `database_explorer` | Read-only SQLite introspection, table inspector | Table list, column schema, paginated rows, migrations, ER diagram |
| `system_health` | Engine connectivity, process telemetry, resource dials | FastAPI status, CPU/RAM/VRAM/Disk metrics, model registry health |
| `library_sources` | Task 4B Discovery roots, scan policies, scan history | Root path registration, policy toggles (`local_only`/`allow_remote`), Scan Now |
| `processing` | Task 4C Resumable DAG jobs, stage inspector, artifacts | 7-stage DAG progress, stage fingerprints, Cancel Job, Resume/Retry, Artifact table |
| `models_languages` | Indic speech & text model readiness matrix | Model status (Whisper, IndicConformer), 12 Indic languages, VRAM footprints |
| `privacy_ai` | Step 6 BYO-AI Gateway, consent manager, audit log | Provider cards (Local, Gemini, OpenAI, Anthropic), verify credentials, consent CRUD |
| `storage_backup` | Task 4D Portable Media Memory, `.arova` bundles | Export `.arova`, dry-run import preview, import, relink missing files, duplicates |
| `appearance_shortcuts` | UI density, accessibility, keyboard cheatsheet | Compact/Comfortable density, reduced motion toggle, global shortcut reference |
| `about_licenses` | Apache 2.0 open-source attribution, SBOM | Open-source license, core dependency inventory, zero-telemetry guarantee |
| `command_palette_ctrl_k` | Quick launcher modal summoned via `Ctrl+K` / `Cmd+K` | Fuzzy command filter, view switcher, direct action triggers, keyboard nav |

### Batch 02 — Precision Refinements & Integration Matrix

| Screen Folder | Refinement over Batch 01 | Implemented Integration |
|---|---|---|
| `overview_index_media_subtitle_import` | Adds dedicated Subtitle Import (`.srt`/`.vtt`) to Overview and Media Ingest drawer | Wired to `POST /api/v1/videos/{video_id}/subtitles` with language selector |
| `media_library_inspector_index_maintenance` | Adds right-hand structural inspector pane: physical media availability, index maintenance | Wired to `GET /api/v1/versions/{v}/availability`, `POST .../relink`, `DELETE .../index` |
| `video_workstation_precision_intelligence_subtitles` | Adds precision subtitle track and word-level confidence timeline | Synchronized player with `.srt`/`.vtt` segments and speech transcript |
| `design_system_sheet_the_cinematic_instrument` | Master color palette, typography scales, elevation layers, corner radii | Implemented in `frontend/src/index.css` & `tailwind.config.js` |
| `application_states_system_feedback` | System feedback states: loading skeletons, empty states, error alerts, badges | Standardized UI state components across all workstation views |
| `responsive_variants_1024px_768px_390px` | Responsive adaptations for Desktop (1440px), Laptop (1024px), Mobile (390px) | Collapsible sidebar, horizontal scrolling tables, responsive grid columns |

---

## 2. Design System Tokens ("The Cinematic Instrument")

### 2.1 Palette Architecture
- **Base Canvas:** `#080B12` (Window frame and background)
- **Docked Sidebar & Tool Shelves:** `#0B1019` (Navigation channels and docks)
- **Base Surface:** `#111827` (Panel cards, module frames)
- **Elevated Surfaces:** `#172235` (Overlays, popovers, active headers)
- **Structural Hairstyle Borders:** `#243149` (1px solid containment)
- **High-Emphatic Text:** `#F5F7FB` (Headings, active timecodes, primary metrics)
- **Muted Data Text:** `#A2AEC0` (Secondary metadata, parameters, units)

### 2.2 Precision Accents (1–2% Visual Footprint)
- **Lavender (`#9B8CFF`):** Focal playhead, active in/out regions, primary action buttons, keyframes.
- **Teal (`#51DCC8`):** Verified evidence, phonetic alignment matches, local enclave health.
- **Sky Blue (`#6BCBFF`):** Visual tracking vectors, optical flow streams, detected bounding boxes.
- **Amber (`#F4BF69`):** Scene cuts, perceptual audio warnings, dropped frames.
- **Rose (`#FF7386`):** Errors, missing media files, process halts, offline status.

### 2.3 Typography & Tabular Numerics
- **Interface Grotesque:** `Geist`, `ui-sans-serif`, `system-ui`
- **Tabular Monospace:** `JetBrains Mono`, `ui-monospace`, `monospace` (Used strictly for SMPTE timecodes, hashes, token counts, latency ms, file sizes)

---

## 3. Screen-to-Component Architecture

```
App.tsx (Root Workspace Shell)
├── TopBar (Brand, Local Enclave badge, Remote AI status, Sync Health, Quick Search trigger)
├── SidebarNavigation (Grouped sections: Intelligence, Storage & Pipeline, System & Security)
├── CommandPaletteModal (Ctrl+K launcher)
└── View Router:
    ├── overview -> OverviewView.tsx (Telemetry matrix, quick ask, ingest modal)
    ├── media-library -> MediaLibraryView.tsx (Asset grid, right inspector, availability, maintenance)
    ├── workstation -> VideoWorkstationView.tsx (Player, multi-track timeline, subtitle track, clip export)
    ├── hybrid-search -> HybridSearchView.tsx (RRF search, Cross-Encoder, Grounded Q&A, Smart Loop, Tools, ML Eval)
    ├── discovery-roots -> DiscoverySourcesView.tsx (Task 4B discovery roots, scan triggers, scan runs)
    ├── processing-jobs -> ProcessingJobsView.tsx (Task 4C DAG jobs, stage inspector, cancel/resume, artifacts)
    ├── privacy-ai -> PrivacyAiView.tsx (Step 6 BYO-AI Gateway, credential verification, consents, audit runs, Indic)
    ├── storage-backup -> StorageBackupView.tsx (Task 4D .arova export/import dry-run, relinking, duplicates)
    ├── mcp-config -> McpConfigView.tsx (12 read-only tools + export tool, IDE client snippets, live stats)
    ├── database-explorer -> DatabaseExplorerView.tsx (SQLite read-only schema, tables, paginated rows, migrations)
    └── system-health -> SystemHealthView.tsx (Telemetry dials, appearance/density, shortcuts, licenses)
```

---

## 4. Workstation Interaction Guidelines

1. **Zero Fake Mock Data:** Every component binds directly to real backend API endpoints. If no data exists, render a clean empty state with a direct action button (e.g., "Index Local Media" or "Register Media Root").
2. **Zero Dead Buttons:** Every button, tab, and form control performs an actual HTTP request, state transition, or clipboard copy.
3. **Deny-by-Default Security:** File imports and directory scans enforce `ALLOWED_MEDIA_ROOTS`. Cloud AI requests strictly verify active scoped `AIConsent`.
4. **Resumable & Non-Destructive:** Index deletion and maintenance operations explicitly state that source media files are strictly read-only and preserved.
