# Argon-to-Flash Master Engineering Blueprint & Execution Playbook

Related notes: [[PROJECT_STATUS]] | [[architecture]] | [[DEVELOPMENT_LOG]] | [[TECHNICAL_DECISIONS]] | [[KNOWN_ISSUES]]

> [!IMPORTANT]
> **Instructions for Gemini Flash (and any executing model):**
> Milestones 1 and 2 (Features 1.1–2.4) are **100% complete and tested**.
> For every remaining feature (Milestones 3, 4, and 5), follow this exact blueprint in order—**one feature at a time**.
> Do **not** invent extra abstractions, do **not** add mock UI placeholders, and **never** leak commercial Arova Creator OS features.

---

## Global Execution Protocol (Run on Every Feature)

1. **Read Blueprint:** Read the target feature section below before editing any file.
2. **Implement Minimal Code:** Write the exact files and signatures specified.
3. **Sync Both Venvs (Whenever `backend/pyproject.toml` changes):**
   ```powershell
   Set-Location backend; uv sync; Set-Location ..
   $env:UV_PROJECT_ENVIRONMENT = (Resolve-Path ".venv").Path; Set-Location backend; uv sync; Set-Location ..
   ```
4. **Run Automated Tests:**
   - Backend: `& .\.venv\Scripts\Activate.ps1; pytest backend/tests -v`
   - Frontend: `Set-Location frontend; npm test; npm run build; Set-Location ..`
5. **Run `ponytail-review`:** Verify zero bugs, path traversal safety, scale, test coverage, and minimal lines.
6. **Update Obsidian Brain (`docs/`):** Update `docs/PROJECT_STATUS.md` and `docs/DEVELOPMENT_LOG.md`.
7. **Atomic Git Commit:**
   ```powershell
   git add -A
   git commit -m "feat(<scope>): <description> (feature X.Y)"
   ```

---

## MILESTONE 3 — Whisper ASR, PySceneDetect & Background Job Runner

### Feature 3.1: Audio Extraction (`16kHz` Mono WAV) & Scene Detection
- **Goal:** Extract `16kHz` mono PCM WAV audio for ASR and detect visual scene cuts with midpoint JPEG thumbnails.
- **Files to Create:**
  1. `backend/app/processing/audio.py`
     - Function: `extract_audio_wav(video_path: str | Path, video_id: str, output_dir: str | Path | None = None) -> Path`
     - Uses `get_ffmpeg_binary()` from `app.processing.metadata`.
     - Runs:
       ```python
       cmd = [
           ffmpeg_bin, "-y", "-i", str(src),
           "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
           str(target_wav),
       ]
       ```
     - If the input video has no audio stream (`"Output file does not contain any stream"` or `"matches no streams"` in stderr), generate a 1-second silent `16kHz` mono WAV fallback via `wave` stdlib so downstream pipeline stages never crash on silent screen recordings.
  2. `backend/app/processing/scene_detection.py`
     - Dataclass: `DetectedScene(scene_index: int, start_time: float, end_time: float, thumbnail_path: str | None)`
     - Function: `detect_video_scenes(video_path: str | Path, video_id: str, duration: float, threshold: float = 27.0, output_dir: str | Path | None = None) -> list[DetectedScene]`
     - Uses `ffmpeg` `select='gt(scene,0.27)',showinfo` filter (via `get_ffmpeg_binary()`) to parse `pts_time:(\d+(?:\.\d+)?)` scene cut timestamps from stderr without requiring heavy OpenCV C++ wheels.
     - Always produces at least 1 scene covering `[0.0, max(duration, 0.1)]` if no cuts exceed threshold.
     - For each scene, generates a midpoint thumbnail at `(start_time + end_time) / 2.0` using `generate_video_thumbnail(video_path, f"{video_id}_scene_{idx}", midpoint_sec, output_dir)`.
  3. `backend/tests/unit/test_audio_and_scenes.py`
     - Synthesize a 2-second multi-scene test MP4 (or lavfi `testsrc` + `sine` audio), run `extract_audio_wav` and `detect_video_scenes`, and assert WAV header (`16000` Hz, `1` channel) + at least 1 `DetectedScene` with a valid JPEG thumbnail on disk.

---

### Feature 3.2: Transcription Abstraction & Faster-Whisper Local Adapter
- **Goal:** Pluggable `TranscriptionProvider` supporting English, Hindi, and Hinglish (`faster-whisper` when installed, with deterministic local WAV acoustic segmenter fallback when running in lightweight CI).
- **Files to Create:**
  1. `backend/app/ai/providers/transcription.py`
     - Dataclasses:
       ```python
       @dataclass(frozen=True)
       class SegmentResult:
           start_time: float
           end_time: float
           text: str
           confidence: float

       @dataclass(frozen=True)
       class TranscriptionResult:
           language: str
           model_name: str
           full_text: str
           segments: list[SegmentResult]
       ```
     - Protocol: `TranscriptionProvider` with `transcribe(audio_path: Path, language: str | None = None) -> TranscriptionResult`.
     - Class `FasterWhisperProvider`:
       - Attempts `from faster_whisper import WhisperModel` using `settings.WHISPER_MODEL_SIZE` and `settings.WHISPER_COMPUTE_TYPE`.
       - `# shortcut: falls back to deterministic WAV frame windowing when faster-whisper model weights are not cached locally, upgrade by pre-downloading faster-whisper base weights in Docker image.`
       - Ensures every returned `SegmentResult` has `0.0 <= start_time < end_time` and non-empty `text`.
  2. `backend/app/services/transcription_service.py`
     - Function `transcribe_and_store(db: Session, video: Video, audio_path: Path, provider: TranscriptionProvider | None = None) -> Transcript`
     - Deletes any old `Transcript` rows for `video.id`, saves new `Transcript` + `TranscriptSegment` rows, commits, and returns the `Transcript`.
  3. `backend/tests/unit/test_transcription.py`
     - Tests `transcribe_and_store` with a deterministic provider and verifies `Transcript` and `TranscriptSegment` persistence in SQLite.

---

### Feature 3.3: SQLite Background Task Runner & Telemetry (RTF)
- **Goal:** Execute `Metadata -> Scenes -> Audio -> Whisper` pipelines asynchronously or synchronously (for tests), updating `ProcessingJob` progress (`0 -> 25 -> 60 -> 100`) and tracking Real-Time Factor (`RTF = elapsed_sec / max(video.duration, 0.1)`).
- **Files to Create / Update:**
  1. `backend/app/workers/pipeline_runner.py`
     - Stores in-memory runtime telemetry metrics (`jobs_completed`, `jobs_failed`, `last_rtf`, `avg_rtf`) in a thread-safe dataclass `WorkerTelemetry`.
     - Function `run_video_pipeline(video_id: str, session_factory: sessionmaker = SessionLocal, provider: TranscriptionProvider | None = None) -> str`:
       - Creates `ProcessingJob(video_id=video_id, job_type="full_pipeline", status="processing", progress=5.0)`.
       - Sets `video.processing_status = "processing"`.
       - Step 1 (30%): `detect_video_scenes` -> stores `VideoScene` rows in DB.
       - Step 2 (60%): `extract_audio_wav` -> extracts `16kHz` WAV.
       - Step 3 (90%): `transcribe_and_store` -> stores `Transcript` & `TranscriptSegment` rows.
       - Step 4 (100%): Marks `ProcessingJob.status = "completed"`, `progress = 100.0`, `video.processing_status = "completed"`, updates `WorkerTelemetry`.
       - On exception: Marks `ProcessingJob.status = "failed"`, `error_message = str(exc)`, `video.processing_status = "failed"`.
  2. `backend/app/schemas/pipeline.py`
     - `TranscriptSegmentOut`, `TranscriptOut`, `VideoSceneOut`, `ProcessingJobOut`.
  3. Update `backend/app/api/routes/videos.py` and add `backend/app/api/routes/jobs.py`:
     - `POST /api/v1/videos/{video_id}/process` (runs pipeline or schedules via FastAPI `BackgroundTasks`; accepts `?sync=true` query param for deterministic synchronous execution).
     - `GET /api/v1/videos/{video_id}/transcript` -> returns `TranscriptOut` with segments.
     - `GET /api/v1/videos/{video_id}/scenes` -> returns `list[VideoSceneOut]`.
     - `GET /api/v1/jobs` and `GET /api/v1/jobs/{job_id}` -> returns `ProcessingJobOut`.
  4. `backend/tests/integration/test_pipeline_api.py`
     - Imports a test MP4, triggers `POST /api/v1/videos/{video_id}/process?sync=true`, verifies `GET /api/v1/videos/{video_id}/scenes`, `GET /api/v1/videos/{video_id}/transcript`, and `GET /api/v1/jobs`.

---

### Feature 3.4: Interactive Transcript & Scene Timeline UI
- **Goal:** Display clickable `TranscriptSegment` rows and `VideoScene` cards inside the Video Inspector (`MediaLibraryView.tsx`) plus a "Process Video (ASR + Scenes)" button that calls `POST /api/v1/videos/{id}/process?sync=true`. Clicking any segment or scene seeks the HTML5 `<video>` player to `segment.start_time`.
- **Files to Update:**
  1. `frontend/src/services/api.ts`: Add `processVideo(videoId)`, `fetchVideoTranscript(videoId)`, `fetchVideoScenes(videoId)`.
  2. `frontend/src/features/media-library/MediaLibraryView.tsx`: Add "Process Video" button, interactive Transcript Timeline list, and Scene Boundary strip.
  3. `frontend/src/test/MediaLibrary.test.tsx`: Add test verifying clicking a transcript segment updates the player seek time.

---

## MILESTONE 4 — Two-Stage Hybrid RAG, Cross-Encoder ML Re-Ranker & Eval Harness

### Feature 4.1: Timestamp-Preserving Chunker & Dual Index (SQLite FTS5 + Dense Vectors)
- **Goal:** Group adjacent `TranscriptSegment` rows into overlapping 30-second windows (`window_sec=30.0`, `overlap_sec=5.0`) preserving exact `[start_time, end_time]`, and index each window in both:
  1. **SQLite FTS5:** Virtual table `transcript_chunks_fts(embedding_id UNINDEXED, video_id UNINDEXED, chunk_text)` for fast BM25 lexical matching.
  2. **Dense Vector Store (`backend/app/ai/providers/embeddings.py`):** Uses `sentence-transformers/all-MiniLM-L6-v2` + `chromadb` if installed, or a deterministic normalized 384-d token-n-gram dense embedding store persisted in SQLite/JSON under `./data/vectors` when heavy PyTorch wheels are not installed.
- **Files to Create:**
  1. `backend/app/ai/retrieval/chunker.py` (`build_timestamp_windows(segments, window_sec=30.0, overlap_sec=5.0)`)
  2. `backend/app/ai/providers/embeddings.py` (`EmbeddingProvider`, `index_video_chunks(db, video_id)`)
  3. Hook `index_video_chunks(db, video.id)` at the end of `run_video_pipeline` so processed videos are automatically indexed for Hybrid RAG!
  4. `backend/tests/unit/test_chunker_and_index.py`

---

### Feature 4.2: Stage-1 Hybrid RRF + Stage-2 Cross-Encoder Re-Ranking
- **Goal:**
  - **Stage 1 (Retrieval):** Query dense vectors (cosine similarity top-$K$, $K=20$) and SQLite FTS5 (`MATCH` top-$K$, $K=20$). Fuse rankings via Reciprocal Rank Fusion:
    $$\text{RRF}(d) = \sum_{m \in \{\text{dense}, \text{lexical}\}} \frac{1}{60 + \text{rank}_m(d)}$$
  - **Stage 2 (Cross-Encoder Re-Ranking):** Score top-20 `(query, chunk_text)` pairs jointly using `cross-encoder/ms-marco-MiniLM-L-6-v2` (with deterministic query-term proximity + coverage cross-attention scorer fallback when PyTorch cross-encoder weights are offline).
- **Files to Create:**
  1. `backend/app/ai/reranking/cross_encoder_reranker.py`
  2. `backend/app/ai/retrieval/hybrid_search.py`
  3. `backend/app/api/routes/search.py`:
     - `POST /api/v1/search/semantic` (returns ranked timestamp windows with `stage1_score`, `rerank_score`, `start_time`, `end_time`, `video_id`, `filename`, `chunk_text`, and latency breakdown `stage1_ms`, `stage2_rerank_ms`).
     - `POST /api/v1/search/transcripts` (lexical search across segments).
  4. `backend/tests/unit/test_hybrid_rerank.py`

---

### Feature 4.3: ML Evaluation Harness & Telemetry API
- **Goal:** Benchmark Stage-1 (Bi-Encoder + FTS5 RRF) vs. Stage-2 (Cross-Encoder Re-Ranked) on a golden evaluation dataset (`sample_data/evaluation_golden_set.json`) and expose `/api/v1/ml/eval/run`, `/api/v1/ml/eval/report`, and `/api/v1/system/telemetry`.
- **Exact Ranking Formulas (`backend/app/ai/evaluation/metrics.py`):**
  - $\text{Recall}@K = \frac{|\text{Relevant} \cap \text{Retrieved}@K|}{|\text{Relevant}|}$ for $K \in \{1, 3, 5, 10\}$
  - $\text{MRR}@10 = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{1}{\text{rank}_q}$ (0 if first relevant item rank $> 10$)
  - $\text{NDCG}@10 = \frac{\text{DCG}@10}{\text{IDCG}@10}$ where $\text{DCG}@10 = \sum_{i=1}^{10} \frac{\text{rel}_i}{\log_2(i + 1)}$
- **Files to Create:**
  1. `sample_data/evaluation_golden_set.json` (10 realistic developer video queries + corpus chunks with ground-truth relevant IDs).
  2. `backend/app/ai/evaluation/metrics.py`
  3. `backend/app/ai/evaluation/eval_harness.py`
  4. `backend/app/api/routes/ml_eval.py` (`POST /api/v1/ml/eval/run`, `GET /api/v1/ml/eval/report`, `GET /api/v1/system/telemetry`)
  5. `backend/tests/unit/test_eval_metrics.py`

---

### Feature 4.4: AI Clip Finder & Grounded Video Summariser
- **Goal:**
  - `POST /api/v1/search/clips`: Accepts `{"query": str, "min_duration": float, "max_duration": float, "top_k": int}` and returns candidate clips filtered/merged within `[min_duration, max_duration]` with relevance rationale.
  - `POST /api/v1/ai/summarize`: Generates a grounded `VideoSummary` (`summary_text`, `topics`, `chapters: [{"start_time": float, "title": str}]`) strictly from the video's `TranscriptSegment` rows (using `google-genai` SDK `gemini-2.5-flash` if `GEMINI_API_KEY` is set, or deterministic extractive transcript summarization when running locally without API keys).
- **Files to Create:**
  1. `backend/app/services/summary_service.py`
  2. Add routes to `backend/app/api/routes/search.py`
  3. `backend/tests/integration/test_clips_and_summary.py`

---

### Feature 4.5: AI Search & ML Benchmark UI
- **Goal:** Build `frontend/src/features/video-search/HybridSearchView.tsx` and wire it into `App.tsx` under `"hybrid-search"`.
- **Features in UI:**
  - Natural-language search input + toggle for "Enable Stage-2 Cross-Encoder Re-Ranking".
  - Results list showing video filename, `[start_time - end_time]` badge, transcript snippet, `Stage-1 RRF` vs `Stage-2 Cross-Encoder` score, and instant HTML5 video preview jumped to `start_time`.
  - "Run ML Evaluation Benchmark" button calling `POST /api/v1/ml/eval/run` and rendering a comparison table (`MRR@10`, `NDCG@10`, `Recall@1/3/5/10`, `p50/p95 Latency ms`) between Stage-1 and Stage-2.
  - Test file: `frontend/src/test/HybridSearch.test.tsx`.

---

## MILESTONE 5 — Official MCP Server, Docker & Public v1.0 Release

### Feature 5.1: Official Python MCP Server (`mcp_server/`)
- **Goal:** Expose the 8 read-only retrieval/inspection tools over STDIO backed directly by `backend/app/services`:
  1. `list_videos(collection_id: str | None = None, status: str | None = None)`
  2. `get_video_metadata(video_id: str)`
  3. `search_video_content(query: str, top_k: int = 5, use_reranker: bool = True)`
  4. `search_transcripts(query: str, video_id: str | None = None)`
  5. `find_video_clips(query: str, min_duration: float = 5.0, max_duration: float = 60.0)`
  6. `summarize_video(video_id: str)`
  7. `get_video_chapters(video_id: str)`
  8. `get_media_library_stats()`
- **Files to Create:**
  1. `mcp_server/__init__.py`
  2. `mcp_server/tools/video_tools.py` (pure Python functions calling `backend/app/services` so they work both via STDIO JSON-RPC / `mcp` SDK and direct unit tests).
  3. `mcp_server/server.py` (STDIO MCP server entrypoint).

---

### Feature 5.2: MCP Inspector & Settings UI + MCP Unit Tests
- **Goal:**
  - Build `frontend/src/features/settings/McpConfigView.tsx` wired into `App.tsx` under `"mcp-config"`, showing live library stats (`get_media_library_stats`), the 8 MCP tool schemas, and a one-click "Copy MCP JSON Config" for Claude Desktop, Cursor, and Gemini Antigravity.
  - Write `mcp_server/tests/test_mcp_tools.py` testing all 8 MCP tools against an indexed test video.
  - Write `frontend/src/test/McpConfig.test.tsx`.

---

### Feature 5.3: Docker, GitHub Actions CI, Docs & Final Ponytail Audit
- **Goal:**
  - Create `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `docs/installation.md`, and `docs/mcp-guide.md`.
  - Run full backend + MCP pytest suite and frontend vitest + production build.
  - Run final `ponytail-audit` to verify zero dead code, zero mock data, and 100% completion in `docs/PROJECT_STATUS.md`.
