# M3.4 Real Browser Acceptance Report

- **Date:** 2026-11-19
- **Branch / Tested Tree:** `feat/m3-baseline-execution` (based on `9b17ef8` + Q1 OCR caching/no-heavy-import fix)
- **Browser:** `Chrome/157.0.8103.79` (`HeadlessChrome/157.0.0.0`, launched with isolated temporary `--user-data-dir` and loopback-only `--remote-debugging-address=127.0.0.1`; user's personal Chrome profile untouched)
- **Local Services:** FastAPI (`http://127.0.0.1:8000`) and Vite (`http://127.0.0.1:5173`), started and stopped cleanly by the test harness
- **Target Processed Video:** `tears_of_steel_720p.mov` (`99989b1a-5119-45b8-a39d-9abeaf34c6cb`, `734.17s`, `86` transcript segments, `139` scenes)
- **Source Media Immutability:** `VERIFIED` — SHA-256 before & after identical (`efa9062d9cdb7a338e40ad530dfdf234806743f29ae6a1a136b97ece4e588e8f`)
- **Console / Runtime Exceptions:** `0` (`[]`)

---

## 1. Live Chrome Browser Verification Matrix: `VERIFIED`

| Check | Viewport | Expected Behavior | Actual Observed Result | Status |
|---|---|---|---|---|
| **Workstation Load** | `1440x900` | Opens `tears_of_steel_720p.mov` with timeline & scenes | Loaded `86 / 86 segments` and `139 cuts` cleanly | `VERIFIED` |
| **Segment vs Word Timing Honesty** | `1440x900` | Shows segment-level badge; hides ASS Karaoke without word timings | Badge: `Timing: Segment-level only (word timings unavailable)`; `ASS Karaoke` hidden | `VERIFIED` |
| **Real SRT Download + FFmpeg Parse** | `1440x900` | Real browser download completes despite `URL.revokeObjectURL`; valid SRT | Downloaded `tears_of_steel_720p.srt` (`4,773` bytes); `ffmpeg -i ... -f ass -` `rc=0`, `stderr=''` | `VERIFIED` |
| **Real VTT Download + FFmpeg Parse** | `1440x900` | Real browser download completes; valid WebVTT | Downloaded `tears_of_steel_720p.vtt` (`4,532` bytes); `ffmpeg -i ... -f srt -` `rc=0`, `stderr=''` | `VERIFIED` |
| **Real ASS Download + FFmpeg Parse** | `1440x900` | Real browser download completes; valid ASS v4+ | Downloaded `tears_of_steel_720p.ass` (`6,742` bytes); `ffmpeg -i ... -f srt -` `rc=0`, `stderr=''` | `VERIFIED` |
| **Transcript Click Seeking** | `1440x900` | Clicking dialogue segment updates HTML5 `video.currentTime` | Clicked segment `30.4s - 34.3s` &rarr; `video.currentTime == 30.38` | `VERIFIED` |
| **Keyboard Focus & Labels** | `1440x900` | Focus ring visible, accessible `aria-label` present | `document.activeElement` focused `Export SRT subtitles` with visible `focus-visible:ring` | `VERIFIED` |
| **Live OCR Panel** | `1440x900` | Displays actual backend OCR state + version provenance | `Completed — No Text Detected`, `rapidocr_onnxruntime@1.4.4`, `ver:56939a4b` | `VERIFIED` |
| **Narrow Viewport Responsiveness** | `390x844` | Usable layout, 0 horizontal overflow, controls accessible | `innerWidth: 390`, `scrollWidth: 390`, `overflowPx: 0`, export & OCR visible | `VERIFIED` |
| **Controlled `engine_unavailable` OCR** | `1440x900` | Explicit unavailable badge + remediation hint (CDP Fetch intercept) | Badge `OCR Engine Unavailable` + remediation hint rendered | `VERIFIED` |
| **Controlled Export Error Alert** | `1440x900` | HTTP 500 export failure renders accessible `role="alert"` | Alert rendered: `Simulated export error for browser alert test` | `VERIFIED` |
| **Controlled Word Timings + OCR Frame Seek** | `1440x900` | Word timings unlock `ASS Karaoke` + OCR frame click seeks player | Badge `Timing: ASR-estimated word timing (not forced-aligned)`, karaoke shown, OCR click seeked `video.currentTime == 45` | `VERIFIED` |
| **Controlled `failed` OCR State** | `1440x900` | Failed OCR renders `OCR Failed` badge + `role="alert"` error detail | Alert rendered: `OCR stage failed: Simulated corrupt frame failure` | `VERIFIED` |

## 2. Visual Evidence (Real Chrome Screenshots)
- Desktop (`1440x900`): `reports/product-acceptance/screenshots/m3_workstation_desktop_1440.png`
- Narrow Mobile (`390x844`): `reports/product-acceptance/screenshots/m3_workstation_mobile_390.png`
