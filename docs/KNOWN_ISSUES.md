# Known Limitations & Issues

## Active Issues & Reality Disclosures

- **ISS-001 (Vitest / JSDOM Video Warning):** JSDOM emits an unhandled `Not implemented: HTMLMediaElement.prototype.play` console error during `MediaLibrary.test.tsx` when testing timestamp jump buttons. All frontend tests pass cleanly.
- **ISS-002 (MCP Tool Count Reconciled):** `export_video_clip` tool was added for lossless subclip slicing. AI agent interfaces are strictly read-only by default. FastMCP defaults strictly to 8 read-only retrieval tools. Subclip export requires explicit developer opt-in (`--enable-exports` or `AROVA_ENABLE_MCP_EXPORTS=1`).
- **ISS-003 (Speech ASR Multilingual Performance & Language Tiers):**
  - **English (`en_us`):** High accuracy (~6.7% WER, ~3.3% CER, 0.42x RTF on CPU with faster-whisper-small). Eligible for default real-time processing.
  - **Hindi (`hi_in`) & Tamil (`ta_in`):** Quality-tier processing (~64.9% - 78.6% WER on small model). Useful for retrieval indexing but requires secondary verification for mission-critical transcripts.
  - **Kannada (`kn_in`) & Telugu (`te_in`):** Script mismatch on generic Whisper base/small checkpoints (> 100% WER). Requires specialized fine-tuned checkpoints or external providers.
- **ISS-004 (500-Video Stress Test Scope):** The 500-video automated test verifies directory discovery, SHA-256 deduplication, and pipeline state recovery after worker interruption. It does not perform full end-to-end Whisper ASR transcription across 500 full-length video files.
- **ISS-005 (100-Query Benchmark Scope):** The 100-query multimodal benchmark uses a curated synthetic golden set (`sample_data/visual_retrieval_golden_100.json`) to verify RRF fusion and Cross-Encoder re-ranking mechanics. Real-world validation against independently labelled video footage is staged on the Beta roadmap.
- **ISS-006 (Desktop GUI MCP Client Testing):** Claude Desktop and Cursor IDE configurations are verified at the FastMCP STDIO schema level (`test_mcp_tools.py`), but live GUI click-through testing in desktop applications is verified by the end user on their workstation.
- **ISS-007 (Privacy & Network Egress Scope):** Localhost-only binding (`127.0.0.1`) and lack of remote analytics have been verified via static code audit and socket inspection. In-memory operational metrics are held strictly locally.
- **ISS-008 (Prompt Injection Sanitization Boundary):** Untrusted transcript and OCR text is sanitized via regex pattern neutralization and XML boundary isolation, passing 215 red-team test cases. This is a heuristic defense, not a formal mathematical guarantee against novel adversarial jailbreaks.

## Tracked Shortcuts (`shortcut:`)

- `shortcut: Single-node local SQLite + local JSON vector storage is scoped for local workstation usage; upgrade to client-server Postgres/Qdrant only if multi-tenant concurrent write load is required.`
- `shortcut: ALLOWED_MEDIA_ROOTS allows relative parents for demo imports; in hardened multi-tenant environments, restrict to absolute directory path.`
- `shortcut: ASR-unavailable error or lexical FTS5 fallback used when Whisper/MiniLM weights are absent; full neural accuracy requires installing optional [ai,asr] extras and local model weights.`
- `shortcut: Visual OCR extracts text using lightweight template heuristics on sampled keyframes; full OCR requires Tesseract/EasyOCR dependencies planned for Beta.`
