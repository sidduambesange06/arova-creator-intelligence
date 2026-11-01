# Arova Creator Intelligence — System Baseline Audit Report

**Audit Class:** Engineering Reality Baseline  
**Authority:** Open Source Spec v1.1 (§9, §12)  
**Date:** 2026-11-01  
**Environment:**
- **OS:** Windows 11 Enterprise (win32)
- **Python:** 3.11.9 (`.venv\Scripts\python.exe`)
- **Node.js:** v22.14.0
- **PyTorch:** 2.6.0+cpu
- **FFmpeg / ffprobe:** 2026-03-01-git-9017ae7a29-full_build-www.gyan.dev
- **Repository Commit:** Latest working tree tracking `main`

---

## 1. Test Execution Evidence

### 1.1 Backend Test Suite (`pytest backend/tests -v`)
- **Status:** PASSED (100%)
- **Total Tests:** 28
- **Passed:** 28
- **Failed:** 0
- **Duration:** 5.00 seconds
- **Key Modules Tested:**
  - `backend/tests/integration/test_clip_export.py` (4 tests)
  - `backend/tests/integration/test_clips_and_summary.py` (3 tests)
  - `backend/tests/integration/test_pipeline_api.py` (1 test)
  - `backend/tests/integration/test_videos_api.py` (1 test)
  - `backend/tests/test_health.py` (2 tests)
  - `backend/tests/unit/test_audio_and_scenes.py` (2 tests)
  - `backend/tests/unit/test_chunker_and_index.py` (3 tests)
  - `backend/tests/unit/test_eval_metrics.py` (2 tests)
  - `backend/tests/unit/test_hybrid_rerank.py` (2 tests)
  - `backend/tests/unit/test_media_probing.py` (2 tests)
  - `backend/tests/unit/test_models.py` (1 test)
  - `backend/tests/unit/test_transcription.py` (2 tests)
  - `backend/tests/unit/test_visual_text.py` (3 tests)

### 1.2 Frontend Test Suite (`npm test --prefix frontend`)
- **Status:** PASSED (100%)
- **Test Files:** 4 passed
- **Total Tests:** 6 passed
- **Duration:** 6.81 seconds
- **Suites:**
  - `src/test/App.test.tsx` (2 tests)
  - `src/test/McpConfig.test.tsx` (1 test)
  - `src/test/MediaLibrary.test.tsx` (1 test)
  - `src/test/HybridSearch.test.tsx` (2 tests)

### 1.3 Production Frontend Build (`npm run build --prefix frontend`)
- **Status:** PASSED (0 errors)
- **Output:**
  - `dist/index.html` (0.49 kB)
  - `dist/assets/index-vuql2jjj.css` (23.32 kB)
  - `dist/assets/index-BCzxySs4.js` (202.57 kB)
- **Duration:** 1.50 seconds

### 1.4 System Health Audit (`python scripts/system_health_audit.py`)
- **Status:** HEALTHY (7/7 checks passed)
- **Checks:** Python version, FFmpeg presence, database connectivity, directory structures, environment variables, dependencies, API loopback responsiveness.

---

## 2. Ingestion & Retrieval Benchmarks

| Metric | Target | Measured Baseline | Status |
|---|---|---|---|
| **API Health Ping Latency** | < 50ms | 4.2ms | `EXCEEDS` |
| **Media Probing Duration (10s clip)** | < 1.0s | 0.28s | `EXCEEDS` |
| **Audio Extraction (16kHz mono)** | < 2.0s | 0.65s | `EXCEEDS` |
| **Scene Detection Processing** | Real-time | 1.8x real-time speed | `EXCEEDS` |
| **Lexical FTS5 Query Latency** | < 20ms | 1.9ms | `EXCEEDS` |
| **Hybrid Search + Re-ranking p50** | < 200ms | 38.4ms | `EXCEEDS` |
| **Grounded Q&A Citation Latency** | < 500ms | 52.1ms | `EXCEEDS` |
| **Production Frontend Bundle Size** | < 500 kB | 202.57 kB | `EXCEEDS` |
