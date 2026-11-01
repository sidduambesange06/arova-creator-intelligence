# Known Issues & Shortcuts Ledger

Related notes: [[PROJECT_STATUS]] | [[architecture]] | [[DEVELOPMENT_LOG]] | [[TECHNICAL_DECISIONS]] | [[FEATURE_STATUS]] | [[MCP_TOOLS]]

## Active Issues
- **ISS-001 (Vitest / JSDOM Video Warning):** JSDOM emits an unhandled `Not implemented: HTMLMediaElement.prototype.play` console error during `MediaLibrary.test.tsx` when testing timestamp jump buttons. All 6 tests pass cleanly.
- **ISS-002 (MCP Tool Count Reconciled):** `export_video_clip` tool was added in Milestone 5 for lossless subclip slicing. Per Launch 01 Spec §3.2, AI agent interfaces must be strictly read-only; documented in `SOURCE_CONFLICTS.md` (CONF-005) and `docs/MCP_TOOLS.md`. Core agent contract retains 8 read-only tools.
- **ISS-003 (Transcription RTF on Low-Spec CPUs):** Offline transcription of long media files (> 2 hours) on low-spec CPUs can take significant wall-clock time; progress is streamed via `/api/v1/jobs`.

## Tracked Shortcuts (`shortcut:`)
- `shortcut: Single-node local SQLite + embedded ChromaDB storage is scoped for local workstation usage; upgrade to client-server Postgres/Qdrant only if multi-tenant concurrent write load is required in future P2 profiles.`
- `shortcut: ALLOWED_MEDIA_ROOTS allows relative parents for demo imports; in hardened multi-tenant environments, restrict to absolute directory path.`
- `shortcut: Deterministic fallback used when Whisper/MiniLM weights are absent; full neural accuracy requires downloading pinned local model weights.`
