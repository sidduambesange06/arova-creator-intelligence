# M3.4 Workstation Integration Acceptance Report

- **Date:** 2026-11-19
- **Branch / Commit:** `feat/m3-baseline-execution` (`f4f9b75` — M3.4 implementation; `fcaf08b` — M3.3 OCR validation)
- **Design System:** The Cinematic Instrument (`#080B12`, `#0B1019`, `#111827`, `#172235`, `#243149`, `#9B8CFF`, `#51DCC8`, `#6BCBFF`, `#F4BF69`, `#FF7386`) preserved intact.

## 1. Delivered Workstation Workflows

### A. Subtitle Export (`SRT`, `VTT`, `ASS`)
- Wired `VideoWorkstationView.tsx` to `GET /api/v1/videos/{video_id}/subtitles/export` via `exportVideoSubtitles()` in `frontend/src/services/api.ts`.
- Downloads real backend output using `<video-stem>.{srt,vtt,ass}`, guards against duplicate clicks (`exportingSubFormat`), cleans up temporary object URLs via `URL.revokeObjectURL()` in `finally`, and displays accessible `role="status"` / `role="alert"` feedback.
- Explicitly distinguishes timing granularity via `data-testid="timing-mode-badge"`:
  - `Timing: ASR-estimated word timing (not forced-aligned)` when real `words` exist on transcript segments.
  - `Timing: Segment-level only (word timings unavailable)` when segments lack word timings.
- Gates the `ASS Karaoke (\k)` checkbox strictly on real backend `words` presence — never fabricates word timings or implies forced alignment.

### B. Optical OCR Visibility
- Added strictly read-only `GET /api/v1/videos/{video_id}/ocr/status` (`VideoOcrStatusOut`) and `fetchVideoOcrStatus()` so the workstation never infers OCR engine availability from an empty array.
- Displays all 6 backend OCR states honestly (`engine_unavailable`, `not_processed`, `running`, `completed_no_text`, `completed_with_text`, `failed`), remediation guidance when unavailable, `version_id` provenance, engine name/version, and clickable timestamped frame buttons that seek the HTML5 video player directly.

## 2. Verification Evidence

| Check | Status | Evidence |
|---|---|---|
| Backend OCR Status Contract (all 6 states + fingerprint invalidation) | `VERIFIED` | `backend/tests/unit/test_m3_optical_ocr.py` (5/5 passed) |
| Frontend Vitest Suite (`WorkstationViews.test.tsx` + 6 existing suites) | `VERIFIED` | `npm --prefix frontend test -- --run` — 7 test files, 20/20 tests passed |
| Frontend TypeScript & Vite Production Build | `VERIFIED` | `npm --prefix frontend run build` (`tsc -b && vite build`, 0 errors) |
| Keyboard Focus, Accessible Labels & Error Alerts | `VERIFIED` | Verified `aria-label`, `focus-visible:ring-2`, `role="status"`, `role="alert"` in component & Vitest |
| Live Browser Visual Capture (CDP screenshots) | `NOT_RUN` | Live headless browser session not executed in this turn; JSDOM component + contract verification passed |
