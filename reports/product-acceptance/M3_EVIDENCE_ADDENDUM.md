# M3 Evidence & Optional-Dependency Reconciliation Addendum

- **Date:** 2026-11-19
- **Branch:** `feat/m3-baseline-execution`
- **Purpose:** Correct provenance, memory reporting, license/weight identity, and optional-dependency details for M3 without rewriting original execution reports (`M3_BASELINE_EXECUTION_REPORT.{md,json}` and `M3_OCR_EXECUTION_REPORT.{md,json}` are preserved unchanged).

---

## A. OCR Memory Reporting Correction
- `M3_OCR_EXECUTION_REPORT.md` line 10 previously rendered `RSS Max Observed: None MB` because `psutil` is not declared in `backend/pyproject.toml` and was absent from `backend/.venv` after `uv sync`.
- **Corrected Value:** **`NOT_MEASURED` (`psutil` not installed in locked `backend/.venv`)**. No historical memory value is invented. `scripts/run_m3_ocr_eval.py` has been updated to emit `NOT_MEASURED` explicitly when `psutil` is unavailable.

## B. OCR Frame Annotation Provenance Correction
- `M3_OCR_EXECUTION_REPORT.md` and `M3_FINAL_CLOSURE_AUDIT.md` previously referred to the 6 *Tears of Steel* (CC-BY 3.0) evaluation frames as "human-annotated".
- **Corrected Provenance:** All 6 frame references (`f01_opening_006s.png`, `f03_scene_045s.png`, `f04_scene_120s.png`, `f05_scene_240s.png`, `f06_credits_608s.png`, `f07_credits_625s.png`) were **`agent-annotated`** by the coding agent via direct visual inspection of the extracted PNG images (independent of OCR output and transcripts, but **not independently human-verified**). CER figures (`4.29%` clear-text, `5.98%` all-text) should be interpreted accordingly until independently human-checked.

## C. Model, License & Dependency Identity + Cache Fingerprint Hardening
- **`backend/pyproject.toml` Constraint:** `[project.optional-dependencies] ocr = ["rapidocr-onnxruntime>=1.3.0"]`
- **`backend/uv.lock` Pinned Resolution:** `rapidocr-onnxruntime==1.4.4` (plus `opencv-python==5.1.0.95`, `pillow==13.0.0`, `pyclipper==1.4.0`, `shapely==2.2.0`, `six==1.17.0`).
- **Separate Runtime vs Model Licenses:**
  - Runtime package `rapidocr-onnxruntime==1.4.4`: **Apache-2.0**.
  - Bundled PaddleOCR PP-OCRv4 mobile ONNX weights: **Apache-2.0** (PaddleOCR).
- **Zero Runtime Downloads Verified:** `rapidocr_onnxruntime` loads its 3 bundled ONNX files directly from its installed package `models/` directory:
  - `models/ch_PP-OCRv4_det_infer.onnx` (`4,745,517` bytes) — `d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9`
  - `models/ch_PP-OCRv4_rec_infer.onnx` (`10,857,958` bytes) — `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b`
  - `models/ch_ppocr_mobile_v2.0_cls_infer.onnx` (`585,532` bytes) — `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`
- **Cache Fingerprint Hardening:** Added `get_ocr_fingerprint_config()` in `backend/app/processing/visual_text.py` and wired it into `PipelineOrchestrator` (`STAGE_OCR_DETECTION`), hashing `ocr_engine`, `ocr_engine_version`, `ocr_model_weights_hash` (SHA-256 over bundled ONNX files), `max_frames`, `min_interval_sec`, and `max_image_pixels`.

## D. Optional Dependency & Test Isolation Verification
- **Default Install (OCR Absent):** Default CI (`uv sync --project backend --group dev --locked`) installs zero OCR dependencies; `detect_ocr_engine()` returns `(None, None)`, `/ocr/status` reports `engine_unavailable`, and `test_optional_ocr_real_pixel_inference_on_synthetic_fixture` cleanly skips without failing default CI.
- **Optional OCR Install:** With `--extra ocr`, `test_optional_ocr_real_pixel_inference_on_synthetic_fixture` executes genuine pixel-level OCR on a synthetic rendered PNG fixture (distinct from the real-frame *Tears of Steel* benchmark).
- **Schema Isolation Subprocess Test (`test_schema_offline_isolation_no_ai_imports`):** Confirmed via negative check that importing `onnxruntime` alongside `app.models.entities` in the subprocess exits non-zero (`AssertionError`), proving the test actively detects unwanted AI imports during schema loading rather than suppressing failure.

## E. Factual M3 PR Summary (`feat/m3-baseline-execution`, `8ca9fc2..HEAD`)
- **M3.0:** Reconciled `origin/main` (`8ca9fc2`), stale Nov 15 state, root spec path, and 12-tool read-only MCP contract (`CONF-005` resolved, `CONF-006` logged for M15).
- **M3.1 (`3816d04`):** Faster-Whisper baseline runner (`asr_baseline.py`, `run_m3_asr_baseline.py`) and 10-clip FLEURS execution report (`en_us` 9.43% WER, `hi_in` 54.41%, `ta_in` 61.11%, `kn_in` 100.0% incl. empty `fleurs_kn_in_1970`, `te_in` 100.0%; smoke-only).
- **M3.2 (`fcb11fd`):** Backward-compatible `words_json` + `timing_source` on `TranscriptSegment`, migration `0004_transcript_word_timings`, dynamic Alembic head fix in `migrator.py`, rollover-safe SRT/VTT/ASS export with ASS escaping, and `GET /api/v1/videos/{id}/subtitles/export` (verified by FFmpeg subtitle decoder).
- **M3.3 (`cbe5998`, `fcaf08b`):** Optional local pixel OCR (`rapidocr-onnxruntime==1.4.4`), explicit `engine_unavailable` state, bounded sampling, weight+config stage fingerprinting, and 6-frame agent-annotated *Tears of Steel* evaluation (Latin/English only).
- **M3.4 (`f4f9b75`):** Read-only `GET /api/v1/videos/{id}/ocr/status` (6 explicit states), workstation SRT/VTT/ASS export with object-URL cleanup & word-timing-gated karaoke, and 6-state OCR panel (`20/20` Vitest + Vite build; live Chrome browser check `BLOCKED` due to missing `DevToolsActivePort`).
