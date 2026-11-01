# Known Issues & Shortcuts Ledger

Related notes: [[PROJECT_STATUS]] | [[architecture]] | [[DEVELOPMENT_LOG]] | [[TECHNICAL_DECISIONS]] | [[FEATURE_STATUS]] | [[MCP_TOOLS]]

## Active Issues & Reality Disclosures

- **ISS-001 (Vitest / JSDOM Video Warning):** JSDOM emits an unhandled `Not implemented: HTMLMediaElement.prototype.play` console error during `MediaLibrary.test.tsx` when testing timestamp jump buttons. All 6 frontend tests pass cleanly.
- **ISS-002 (MCP Tool Count Reconciled):** `export_video_clip` tool was added in Milestone 5 for lossless subclip slicing. Per Launch 01 Spec §3.2, AI agent interfaces must be strictly read-only by default. FastMCP defaults strictly to 8 read-only retrieval tools. Subclip export requires explicit developer opt-in (`AROVA_ENABLE_MCP_EXPORTS=1`).
- **ISS-003 (Transcription RTF on Low-Spec CPUs):** Offline transcription of long media files (> 2 hours) on low-spec CPUs can take significant wall-clock time; progress is streamed via `/api/v1/jobs`.
- **ISS-004 (500-Video Stress Test Scope):** The 500-video automated test verifies directory discovery, SHA-256 deduplication, and pipeline state recovery after mid-run worker abort. It does NOT perform full end-to-end Whisper ASR transcription, optical character recognition, or scene cut detection across 500 full-length video files (which would require hours of CPU compute). Full media indexing scale testing is staged on the Beta roadmap.
- **ISS-005 (100-Query Benchmark Scope):** The 100-query multimodal benchmark uses a curated synthetic golden set (`sample_data/visual_retrieval_golden_100.json`) to verify RRF fusion and Cross-Encoder re-ranking mechanics. Real-world validation against independently labelled video footage is deferred to Beta.
- **ISS-006 (Desktop GUI MCP Client Testing):** Claude Desktop and Cursor IDE configurations are verified at the FastMCP STDIO schema level (`test_mcp_tools.py`), but live GUI click-through testing in desktop applications requires manual user verification.
- **ISS-007 (Privacy & Network Egress Scope):** Localhost-only binding (`127.0.0.1`) and lack of telemetry have been verified via static code audit and socket inspection. Independent dynamic network packet capture under an isolated OS harness has not been conducted (deferred to Beta).
- **ISS-008 (Prompt Injection Sanitization Boundary):** Untrusted transcript and OCR text is sanitized via regex pattern neutralization and XML boundary isolation, passing 215 red-team tests. This is a heuristic pattern defense, not a formal mathematical guarantee against novel adversarial jailbreaks.

## Tracked Shortcuts (`shortcut:`)

- `shortcut: Single-node local SQLite + embedded ChromaDB storage is scoped for local workstation usage; upgrade to client-server Postgres/Qdrant only if multi-tenant concurrent write load is required in future P2 profiles.`
- `shortcut: ALLOWED_MEDIA_ROOTS allows relative parents for demo imports; in hardened multi-tenant environments, restrict to absolute directory path.`
- `shortcut: Deterministic acoustic fallback used when Whisper/MiniLM weights are absent; full neural accuracy requires downloading pinned local model weights.`
- `shortcut: Visual OCR extracts text using lightweight template heuristics on sampled keyframes; full OCR requires Tesseract/EasyOCR dependencies planned for Beta.`
