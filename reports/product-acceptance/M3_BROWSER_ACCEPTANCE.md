# M3.4 Real Browser Acceptance Report

- **Date:** 2026-11-19
- **Branch / Tested Commit:** `feat/m3-baseline-execution` (`6de0e80`)
- **Local Services Started:** FastAPI backend on `http://127.0.0.1:8000`, Vite frontend on `http://127.0.0.1:5173`
- **Target Processed Video:** `tears_of_steel_720p.mov` (`99989b1a-5119-45b8-a39d-9abeaf34c6cb`, `734.17s`, `86` transcript segments, `139` scenes)

## 1. Live Chrome Browser Verification Status: `BLOCKED`

The `browser` subagent attempted to connect to Google Chrome via `chrome_devtools` MCP (`list_pages`) and returned:

- **Exact Error:** `Could not connect to Chrome. Check if Chrome is running and remote debugging is enabled by going to chrome://inspect/#remote-debugging.`
- **Cause:** `Could not find DevToolsActivePort for chrome at C:\Users\Siddhu Ambesanage\AppData\Local\Google\Chrome\User Data\DevToolsActivePort (ENOENT)`.
- **Browser Steps Executed:** `0/7` (no live Chrome clicks, visual layout inspection, or browser screenshots captured).
- **Honesty Disclosure:** JSDOM tests (`WorkstationViews.test.tsx`, `20/20` Vitest) verify React component logic and API contracts only; they are **NOT** presented as live browser acceptance evidence. The live browser acceptance gap remains open until Chrome remote debugging is enabled on the workstation.

## 2. Independent Non-Browser Live Backend & Subtitle Consumer Verification: `VERIFIED`

While the local FastAPI backend was running on `http://127.0.0.1:8000`, the real exported subtitle endpoints and OCR status endpoint for `tears_of_steel_720p.mov` were verified directly against an independent consumer (`ffmpeg` subtitle decoder):

| Endpoint / Check | HTTP | Exported Bytes | Independent FFmpeg Consumer Check | Status |
|---|---:|---:|---|---|
| `GET /api/v1/videos/99989b1a-.../subtitles/export?format=srt` | `200` | `4,773` | `ffmpeg -v error -i out.srt -f ass -` (`rc=0`, `6,740` bytes, `stderr=''`) | `VERIFIED` |
| `GET /api/v1/videos/99989b1a-.../subtitles/export?format=vtt` | `200` | `4,532` | `ffmpeg -v error -i out.vtt -f srt -` (`rc=0`, `4,774` bytes, `stderr=''`) | `VERIFIED` |
| `GET /api/v1/videos/99989b1a-.../subtitles/export?format=ass` | `200` | `6,742` | `ffmpeg -v error -i out.ass -f srt -` (`rc=0`, `6,752` bytes, `stderr=''`) | `VERIFIED` |
| `GET /api/v1/videos/99989b1a-.../ocr/status` | `200` | — | Returned `status="completed_no_text"`, `engine_available=true`, `engine_name="rapidocr_onnxruntime"`, `engine_version="1.4.4"`, `version_id="56939a4b-..."` | `VERIFIED` |

## 3. Action Required to Unblock Live Chrome Verification

1. Launch Google Chrome and enable remote debugging at `chrome://inspect/#remote-debugging` (creating `DevToolsActivePort`).
2. Re-run the M3.4 browser acceptance checklist (desktop + `390x844` narrow viewport, real download check, transcript & OCR seek, keyboard focus, error states).
