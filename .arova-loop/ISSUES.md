# Arova Creator Intelligence — Issues & Known Limitations

**Document Authority:** Open Source Spec v1.1 (§7, §11)  
**Status:** Managed Operational State  

---

## 1. Active Issues & Tracking

| Issue ID | Severity | Component | Summary | Workaround / Status |
|---|---|---|---|---|
| **ISS-001** | Low | `MediaLibraryView.tsx` | JSDOM does not implement `HTMLMediaElement.prototype.play()` during Vitest execution, emitting a console warning. | Test suite mocks playback or swallows unhandled promise; all 6 tests pass cleanly. |
| **ISS-002** | Medium | `mcp_server/server.py` | `export_video_clip` tool writes subclips to disk; per Launch 01 Spec §3.2, AI agent interface must be strictly read-only. | Gated/documented in `docs/MCP_TOOLS.md` and `SOURCE_CONFLICTS.md` (CONF-005). FastMCP server defaults strictly to 8 read-only tools. |
| **ISS-003** | Low | Ingestion Pipeline | Long videos (> 2 hours) on low-spec CPUs may take 15–30 minutes during faster-whisper transcription. | User informed via live job status updates on `GET /api/v1/pipeline/jobs/{id}`. |
| **ISS-004** | Info | Stress Testing | 500-video stress test validates directory discovery, deduplication, and crash recovery; not full ASR indexing. | Clarified in test documentation and release gate; full ASR scale test staged on Beta roadmap. |
| **ISS-005** | Info | Benchmarks | 100-query benchmark is evaluated against a curated synthetic multimodal dataset. | Documented as synthetic evaluation golden set; real-world video footage validation staged on Beta roadmap. |
| **ISS-006** | Low | Client Integrations | Claude Desktop and Cursor IDE verified at FastMCP STDIO schema level; live GUI manual click-through pending. | Configs documented in `docs/INTEGRATIONS.md`; physical desktop click-through deferred to Beta manual QA. |
| **ISS-007** | Info | Privacy Boundary | Loopback binding (`127.0.0.1`) and zero telemetry verified via static source code & socket inspection. | Documented; dynamic network packet egress monitoring under isolated OS harness staged on Beta roadmap. |
| **ISS-008** | Info | Security Defenses | Untrusted transcript and OCR text is sanitized via regex pattern defanging and XML boundary tags. | Heuristic defense; passes 215 red-team tests, but not formal mathematical proof against novel jailbreaks. |

---

## 2. Technical Shortcuts & Debt Ledger

- `shortcut: ALLOWED_MEDIA_ROOTS allows relative parents for demo imports; in hardened multi-tenant environments, restrict to absolute directory path.`
- `shortcut: Deterministic fallback used when Whisper/MiniLM weights are absent; full neural accuracy requires downloading pinned local model weights.`
- `shortcut: Visual OCR extracts text using lightweight template heuristics on sampled keyframes; full OCR requires Tesseract/EasyOCR dependencies planned for Beta.`
