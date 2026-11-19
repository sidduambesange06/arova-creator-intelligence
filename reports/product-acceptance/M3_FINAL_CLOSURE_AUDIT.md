# M3 Final Closure Audit & M3.1 Provenance Addendum

- **Date:** 2026-11-19
- **Branch:** `feat/m3-baseline-execution` (branched from `origin/main` `8ca9fc2`, PR #21)
- **Commit Range:** `8ca9fc2..HEAD` (`3816d04` M3.1, `fcb11fd` M3.2, `cbe5998` M3.3 contract, `f4f9b75` M3.4 workstation, `fcaf08b` M3.3 real OCR)
- **Overall Milestone Status:** `VERIFIED (WITH EXPLICIT SCOPE LIMITATIONS)` — all core M3.0–M3.4 code, real ASR baseline, word-level subtitles, real-pixel OCR evaluation, and workstation integration are verified; live browser visual capture is `NOT_RUN`, and Indic OCR / specialist Indic ASR are explicitly deferred to M4+.

---

## 1. M3 Gate Matrix

| Gate | Status | Evidence & Scope Notes |
|---|---|---|
| **M3.0 — Context & Contract Reconciliation** | `VERIFIED` | Reconciled `origin/main` (`8ca9fc2`), stale Nov 15 state, stale spec filename (`AROVA_CREATOR_INTELLIGENCE_OPEN_SOURCE_SPEC.md`), 12 read-only MCP tools (+1 gated export), and logged `CONF-006` (M15 IP boundary). |
| **M3.1 — Faster-Whisper Baseline Execution** | `VERIFIED` | Genuine `faster-whisper-small` (`cpu`, `int8`, `language_mode=forced`, `word_timestamps=True`) executed on 10/10 validated FLEURS clips (`M3_BASELINE_EXECUTION_REPORT.{md,json}`). Smoke-only; does not claim population-level quality. |
| **M3.2 — Word-Level Timings & SRT/VTT/ASS Export** | `VERIFIED` | Nullable `words_json` + `timing_source` on `TranscriptSegment`, reversible migration `0004_transcript_word_timings`, dynamic Alembic head detection in `migrator.py`, rollover-safe SRT/VTT/ASS export with ASS override escaping & `GET /api/v1/videos/{id}/subtitles/export`. |
| **M3.3 — Optional Optical OCR & Real-Pixel Validation** | `VERIFIED (LATIN/ENGLISH ONLY)` | Optional `rapidocr-onnxruntime==1.4.4` (`Apache-2.0`, zero runtime downloads) locked in `backend/pyproject.toml` `[project.optional-dependencies] ocr`. Real-pixel evaluation on 6 human-annotated *Tears of Steel* (CC-BY 3.0) frames: Clear-Text CER `4.29%`, All-Text CER `5.98%`, `0` misses, `0` no-text false positives, corrupt-frame safe, source SHA-256 immutable (`M3_OCR_EXECUTION_REPORT.{md,json}`). **Indic OCR NOT supported by default weights.** |
| **M3.4 — Workstation Integration** | `VERIFIED (AUTOMATED)` / Visual Capture `NOT_RUN` | Subtitle export (`SRT`/`VTT`/`ASS` + conditional karaoke gated on real words) and 6-state honest OCR visibility (`GET /api/v1/videos/{id}/ocr/status`) integrated into `VideoWorkstationView.tsx`. 20/20 Vitest + Vite production build passing; live browser visual capture `NOT_RUN`. |

---

## 2. M3.1 Evidence & Provenance Addendum (Original Report Preserved Untouched)

The original [M3_BASELINE_EXECUTION_REPORT.md](./M3_BASELINE_EXECUTION_REPORT.md) and [M3_BASELINE_EXECUTION_REPORT.json](./M3_BASELINE_EXECUTION_REPORT.json) are preserved unchanged. This addendum records audited provenance details:

1. **Immutable Model Identity (`Systran/faster-whisper-small`):**
   - Upstream HuggingFace tree revision recorded in local cache: `536b0662742c02347bc0e980a01041f333bce120`
   - `model.bin` (`483,546,902` bytes): `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671`
   - `config.json` (`2,370` bytes): `b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828`
   - `tokenizer.json` (`2,203,239` bytes): `fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab`
   - `vocabulary.txt` (`459,861` bytes): `34ce3fe1c5041027b3f8d642912270993f986dbc4bb34cf27f951e34a1e453913`
2. **Tested Tree vs Commit Identity:**
   - The M3.1 run executed on working tree based on `8ca9fc25e502abad1a81785a9b94abfbd19dc062` with the uncommitted M3.1 runner files (`asr_baseline.py`, `run_m3_asr_baseline.py`), which were subsequently committed as `3816d04`.
3. **Exact Runtime Interpreter & Dependency Versions:**
   - Interpreter: `backend/.venv/Scripts/python.exe` (Python `3.11.9` on `Windows-10-10.0.26300-SP0`)
   - Dependencies: `faster-whisper==1.2.1`, `ctranslate2==4.8.5`, `psutil==7.2.2`
4. **Inference Timing Scope:**
   - Confirmed `FasterWhisperProvider.transcribe()` exhaustively consumes the `segments_raw` generator (`for s in segments_raw:`) inside the `time.perf_counter()` block in `asr_baseline.py`, so `inference_sec` measures full decode + word-timestamp extraction.
5. **Memory Measurement Method:**
   - `rss_peak_mb` (`377.18 MB`) is the **maximum of discrete `psutil.Process().memory_info().rss` observations** (before init, after init, and after each utterance), not continuous background sampling or OS high-water mark.
6. **Raw Edit-Count Verification (Unclamped WER):**
   - Recomputed directly from raw utterance edit counts: Micro WER = `139 / 232 = 0.599138` (`59.91%`), Micro CER = `680 / 1586 = 0.428752` (`42.88%`). WER is never clamped to `1.0`.
7. **Empty-Hypothesis Outcome (`fleurs_kn_in_1970`):**
   - `fleurs_kn_in_1970` (`kn_in`, `13.92s`) completed execution cleanly (`71.53s` decode, no exception) but produced an **empty hypothesis (`""`, `0` segments, `0` words)**, resulting in `100%` deletion WER (`1.0`). Poor Kannada/Telugu performance on generic Whisper-small (`100%` WER, `6.2x–8.5x` RTF) is preserved honestly and directly motivates M4 specialist Indic ASR evaluation.

---

## 3. Known Limitations & M4 Follow-Up

- **Indic ASR Quality:** Generic `faster-whisper-small` is unsuitable for Kannada/Telugu (`100%` WER) and exhibits high WER on Hindi (`54.4%`) and Tamil (`61.1%`). Specialist Indic ASR comparison on held-out inputs is deferred to **M4–M6**.
- **Indic OCR Coverage:** Default bundled `rapidocr-onnxruntime` weights cover Latin (English) and Chinese only; Indic script OCR requires dedicated Indic OCR models in a future milestone.
- **Live Browser Visual Capture:** Component, contract, and build verification passed (`20/20` Vitest, `tsc -b && vite build`), while live headless browser screenshot capture for M3.4 is marked `NOT_RUN`.
