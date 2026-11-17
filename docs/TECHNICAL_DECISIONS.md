# Technical Decisions

---

## ADR-001: Local-First Storage Stack (SQLite FTS5 + Local JSON Vector Store)
- **Context:** Developers evaluating the repository or running local MCP servers should not need Docker Compose with PostgreSQL, Redis, or cloud API keys just to index and search local videos.
- **Decision:** Use SQLite (with FTS5 for lexical search) alongside a lightweight local JSON vector store for dense embeddings, stored under `./data/`.
- **Consequences:** Zero-install local startup; single-process write concurrency is sufficient for a local developer desktop/workstation engine.

## ADR-002: Strict Open-Source / Commercial IP Boundary
- **Context:** `arova-creator-intelligence` is public under Apache 2.0 and powers media indexing/retrieval while keeping Arova Creator OS commercial workflows private.
- **Decision:** Expose only media probing, ASR transcription, scene detection, hybrid vector+FTS5 retrieval, cross-encoder re-ranking, evaluation benchmarks, and read-only MCP retrieval tools. Exclude all commercial features (idea/hook/script generators, brand deal CRM, tone memory).
- **Consequences:** Clean developer positioning as a local Video RAG & MCP engine.

## ADR-003: Self-Contained FFmpeg Fallback via `imageio-ffmpeg`
- **Context:** Windows/macOS developer laptops often do not have `ffmpeg` and `ffprobe` pre-installed on system `PATH`.
- **Decision:** Prefer `shutil.which("ffmpeg")` / `shutil.which("ffprobe")` when installed on system `PATH`, and automatically fall back to the bundled `imageio_ffmpeg.get_ffmpeg_exe()` binary for both metadata probing and frame/audio extraction.
- **Consequences:** Zero manual FFmpeg installation required to run tests or ingest local MP4/MOV/MKV/WebM videos.

## ADR-004: Visual-Text Dual Memory Engine
- **Context:** Technical videos contain critical information presented visually in slide titles, code snippets, and diagrams that is never spoken aloud.
- **Decision:** Extract on-screen text from keyframe thumbnails and fuse it directly into sliding-window transcript chunks tagged with `[On-Screen Visual Text]: ...`. Tag search matches with their channel (`speech`, `visual`, `multimodal`).
- **Consequences:** Unifies speech and visual slide text in both dense vector and lexical FTS5 retrieval.

## ADR-005: FastMCP Default Read-Only Isolation & Developer Opt-In for Exports
- **Context:** Security guidelines dictate that AI agents in Launch 01 must only have read-only tools. The `export_video_clip` tool writes MP4 subclips to disk.
- **Decision:** Isolate the default MCP toolset to strictly the 8 read-only retrieval tools. Gate `export_video_clip` behind an explicit developer opt-in (`AROVA_ENABLE_MCP_EXPORTS=1` or `--enable-exports`).
- **Consequences:** Strictly enforces the read-only agent contract while preserving subclip slicing capability for explicit developer opt-in. (Implemented in commit `13dd684`).

## ADR-006: Canonical Task Numbering & Deliverable Separation for Launch 01
- **Context:** Early drafts assigned `TASK-010` to the automated release gate, while community governance documents (`NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` per Spec §10.2) were informal deliverables.
- **Decision:** Reconcile task IDs into a single canonical sequence:
  - `TASK-006`: `arova doctor` diagnostic CLI command (`WS-CLI`, `REQ-024`) — `VERIFIED`
  - `TASK-007`: `arova demo` synthetic first-use flow (`WS-CLI`, `REQ-025`, `REQ-032`) — `VERIFIED`
  - `TASK-008`: Thin Python client wrapper `arova-client` (`WS-CLI`, `REQ-023`) — `VERIFIED`
  - `TASK-009`: Tested client integration matrices in `docs/INTEGRATIONS.md` (`WS-DOC`, `REQ-033`) — `VERIFIED`
  - `TASK-010`: Open-source community governance files (`WS-DOC`, `REQ-031`) — `VERIFIED`
  - `TASK-011`: Automated release gate verification script (`WS-QA`, `REQ-029`) — `VERIFIED`
- **Consequences:** Provides exact 1:1 requirement traceability across all registers and eliminates ambiguity between release verification and community documentation.

## ADR-007: Staged Release Governance (Alpha vs Beta/Stable Scope Delineation)
- **Context:** An open-source developer Alpha (`v0.1.0-alpha`) requires verified local core engine mechanics, safe queries, bounded filesystems, prompt defanging, and robust recovery, but does not warrant enterprise SaaS certification or blocking local developer previews on external multi-machine non-developer physical setups.
- **Decision:** Separate release gates into staged milestones:
  - **Alpha (`v0.1.0-alpha`):** All 12 automated checks (Backend, Frontend, FastMCP, Doctor, Demo, 500-Video Stress, 215 Red-Team Cases, 100-Query Benchmark, Fault-Injection Resiliency, and CycloneDX SBOM) 100% passing. Localhost-only binding (`127.0.0.1`), 8 default read-only MCP tools, parameterized SQL, and source media immutability.
  - **Beta (`v0.2.0-beta`):** External non-developer multi-machine validation across independent macOS and Linux hosts; live Claude Desktop / Cursor GUI manual verification; PyPI package distribution.
  - **Stable (`v1.0.0`):** Model Context Protocol official registry publication and enterprise backward compatibility.
- **Consequences:** Unblocks open-source Alpha preview testing with zero false claims of enterprise certification, while cleanly staging broader ecosystem QA on the Beta/Stable roadmap.


## ADR-008: API / SDK / MCP Retrieval Channel Contract Freeze & 5-Gate `consent_source` Semantics (`M1` — `V12 Phase 0`)
- **Status:** Accepted & Verified (`2026-11-15`, `M1` Final Closure)
- **Context:** `M0` reconciliation (`ISS-019`) uncovered interface drift where `ArovaClient`, FastMCP tools, and `ToolExecutionEngine` omitted `channel`/`video_id` parity (and `get_media_availability` registered `asset_id` instead of `video_id`/`version_id`), invalid channels risked silent fallback, docs mixed stale counts/names (`8 tools`, `spoken | visual_ocr | summary`), and `/api/v1/ai/summarize` inferred `consent_source` with brittle string heuristics rather than real DB `AIConsent` + policy/scope/data-category provenance.
- **Decision:**
  1. Freeze `VALID_SEARCH_CHANNELS = ("all", "speech", "visual", "multimodal")` as the single authoritative channel enum across retrieval (`hybrid_search.py`), REST/OpenAPI (`search.py`), service (`summary_service.py`), Python SDK (`arova/client.py`), FastMCP (`mcp_server/`), and `ToolExecutionEngine` (`tool_engine.py`), rejecting invalid channel values loudly (`ValueError` / HTTP `400` / HTTP `422`) instead of falling back silently. Do **not** add compatibility aliases for `"spoken"`, `"visual_ocr"`, or `"summary"`, as commit `3843684` proved those strings never existed in runtime code, API schemas, SDK, or UI (they were documentation typos only).
  2. Enforce 5-gate `evaluate_consent()` validation (case/whitespace-normalized provider registration + `supported_capabilities`, multi-scope ID matching including wildcard/global while ignoring synthetic `Default Root`/`Default Library` migration rows, `expires_at`, `budget_limit`, `data_categories` with transcript aliases, and most-restrictive `Library.execution_profile` / `LibraryRoot.policy` + per-video scope intersection across multi-video Q&A candidates) and propagate real provenance (`_remote_egress`, `_provider`, `_consent_source`, `_egress_data_categories`), returning local-loopback answers cleanly while clearing `consent_source` and `consent_id` whenever `not response.remote_egress`.
  3. Preserve the `12` default read-only FastMCP tools + `1` opt-in `export_video_clip` (`AROVA_ENABLE_MCP_EXPORTS` / `--enable-exports`) security boundary and zero new runtime dependencies.
  4. Separate `M0–M1` (`V12 Phase 0: Foundation & Contract Freeze`) from `V12 Phase 1: Indic Creator Bench` (starting at `M2` after Founder approval).
- **Consequences:** Resolves and closes `ISS-019`; freezes developer interfaces cleanly ahead of `M2` (`V12 Phase 1: Indic Creator Bench`) without blocking offline/local operation or adding package bloat.

## ADR-009: Indic Creator Bench Dataset Contracts, Git-Ignored Audio & Unicode-Safe Normalization (`M2` — `V12 Phase 1`)
- **Status:** Accepted & Verified (`2026-11-15`, `M2`)
- **Context:** Establishing reproducible Indic speech evaluation requires strict schema contracts, attribution, tamper/traversal checks, Unicode preservation (where `google/fleurs` raw Telugu transcripts contain `\u200c` ZWNJ that naive normalizers strip), secret-safe ASR provenance, and keeping audio binaries out of Git.
- **Decision:**
  1. Freeze Draft 2020-12 schemas (`1.0.0`) under `sample_data/indic_creator_bench/schemas/` for descriptors, sample manifests, and secret-safe `ASRRunProvenance` / `BatchRunProvenance`.
  2. Materialize real smoke WAV assets strictly under git-ignored `data/indic_creator_bench/m2_smoke_10clip/audio/` while tracking only JSON/JSONL contracts, SHA-256 digests, and `CC-BY-4.0` attribution (`google/fleurs` @ `168de341b3db6859a9bac1c50a2ef5e3b47647e0`) in Git.
  3. Preserve verbatim `raw_transcription` and evaluate with `v2_indic_unicode_safe_nfc` (preserving combining matras, viramas, nukta, ZWJ, and ZWNJ) while keeping Hinglish excluded (`NO_VERIFIED_REFERENCE`).
- **Consequences:** Enables offline, zero-GPU, zero-API validation across 10 real speech clips (`hi_in`, `kn_in`, `ta_in`, `te_in`, `en_us`) and prepares deterministic provenance for `M3`.
