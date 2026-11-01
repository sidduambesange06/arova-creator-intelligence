# Arova Creator Intelligence — Issues & Known Limitations

**Document Authority:** Open Source Spec v1.1 (§7, §11)  
**Status:** Managed Operational State  

---

## 1. Active Issues & Tracking

| Issue ID | Severity | Component | Summary | Workaround / Status |
|---|---|---|---|---|
| **ISS-001** | Low | `MediaLibraryView.tsx` | JSDOM does not implement `HTMLMediaElement.prototype.play()` during Vitest execution, emitting a console warning. | Test suite mocks playback or swallows unhandled promise; all 6 tests pass cleanly. |
| **ISS-002** | Medium | `mcp_server/server.py` | `export_video_clip` tool writes subclips to disk; per Launch 01 Spec §3.2, AI agent interface must be strictly read-only. | Gated/documented in `docs/MCP_TOOLS.md` and `SOURCE_CONFLICTS.md` (CONF-005). Core agent contract retains 8 read-only tools. |
| **ISS-003** | Low | Ingestion Pipeline | Long videos (> 2 hours) on low-spec CPUs may take 15–30 minutes during faster-whisper transcription. | User informed via live job status updates on `GET /api/v1/pipeline/jobs/{id}`. |

---

## 2. Technical Shortcuts & Debt Ledger

- `shortcut: ALLOWED_MEDIA_ROOTS allows relative parents for demo imports; in hardened multi-tenant environments, restrict to absolute directory path.`
- `shortcut: Deterministic fallback used when Whisper/MiniLM weights are absent; full neural accuracy requires downloading pinned local model weights.`
