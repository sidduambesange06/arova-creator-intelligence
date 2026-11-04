# TASK-4D Repository Truth Audit & Architecture Blueprint

**Task:** TASK-4D — Portable Media Memory, Versioned API, and Cross-Machine Intelligence Transfer  
**Date:** 2026-11-04  
**Author:** Principal Systems Architect & Antigravity Autonomous Loop  
**Status:** Dependencies Verified & Ready for Implementation  

---

## 1. Repository & Baseline Truth Audit

### 1.1 Git State & Working Tree
- **Active Branch:** `feat/task4-media-discovery` (tracking `origin/feat/task4-media-discovery`)
- **Base Commit:** `74247c7 fix(test): ensure test database has sample video row for explorer pagination test`
- **Working Tree:**
  - Modified: `backend/app/api/routes/jobs.py`, `backend/app/cli/demo.py`, `backend/app/schemas/pipeline.py`, `backend/app/workers/pipeline_runner.py`, `reports/audit/BENCHMARK_100_QUERIES.md`
  - Untracked: `backend/app/services/pipeline_orchestrator.py`, `backend/tests/unit/test_resumable_processing.py`
  - Protected & Untouched: `reports/audit/BASELINE.md`, `reports/audit/SBOM.json`, `data/app.db`
- **Regression Health:** 177 passed, 1 skipped out of 178 backend/MCP tests (29.21s). 8 passed out of 8 frontend Vitest tests (3.23s). 0 failures.

### 1.2 Upstream Dependency Verification
- **Task 4A (Media Memory Foundations):** `VERIFIED_COMPLETE`. 4-layer hierarchy (`Library` -> `Asset` -> `AssetVersion` -> `AssetLocation`), `Moment`, `Annotation`, `IDAlias`, and `Artifact` tables deployed via Alembic migration `0002_task4_media_memory.py`. Full migration cycle (`upgrade head` -> `downgrade base` -> `upgrade head`) verified clean.
- **Task 4B (Media Discovery and Safety):** `VERIFIED_COMPLETE`. Media root registration, recursive traversal excluding build artifacts, streaming SHA-256 chunk hashing, deterministic UUIDv5 version addressing (`NAMESPACE_AROVA_VERSION`), duplicate/relink handling, and missing/restored availability tracking operational. PR #11 CI passed (3/3 jobs green).
- **Task 4C (Resumable Intelligence Processing):** `VERIFIED_COMPLETE`. `PipelineOrchestrator` with 7-stage DAG, deterministic SHA-256 fingerprints, idempotent execution skips, worker lease locking, heartbeats, stale run recovery, graceful cancellation, resumption, atomic artifact superseding (`is_current`), disk space safeguards, and structured error codes verified across 11 unit tests and 6 fault injection tests.

---

## 2. Architecture & Design Blueprint: TASK-4D

### 2.1 The Portable `.arova` Container Specification
- **Container Format:** Standard ZIP file with extension `.arova` containing streamed NDJSON (Newline Delimited JSON) records and a root cryptographic manifest.
- **Format Version:** `1.0.0`
- **Internal File Structure:**
  ```
  archive.arova (ZIP)
  ├── manifest.json
  ├── assets.ndjson
  ├── versions.ndjson
  ├── locations.ndjson
  ├── transcripts.ndjson
  ├── transcript_segments.ndjson
  ├── scenes.ndjson
  ├── moments.ndjson
  ├── annotations.ndjson
  └── artifacts.ndjson
  ```
- **Portability Invariant:** Zero absolute filesystem paths (`C:\...` or `/home/...`), zero API keys/credentials, zero machine-specific usernames. All location entries use normalized root-relative paths (`rel_path_norm`).
- **Cryptographic Integrity:** Every entry in `manifest.json` specifies its exact uncompressed byte length and SHA-256 digest.

### 2.2 Security & Safety Baseline (20 Mandatory Safeguards)
1. Archive type check (`.arova` extension, valid ZIP header).
2. Manifest schema validation (`format_version`, `export_id`, `created_at`, `entries`).
3. Format version compatibility verification (`1.x` supported).
4. Strict entry presence check against declared manifest entries.
5. Authoritative SHA-256 digest validation of every extracted entry.
6. Absolute path rejection in archive filenames (`/etc/...`, `C:\...`).
7. Path traversal rejection (`../`, `..\\`).
8. Windows drive path rejection (`C:`, `D:`).
9. Symlink, hardlink, and device file rejection.
10. Maximum archive entry count limit (default: 100 entries).
11. Maximum compressed archive size limit (default: 500 MB).
12. Maximum uncompressed total size limit (default: 2 GB).
13. Maximum individual entry size limit (default: 200 MB).
14. Maximum decompression ratio limit (default: 20:1, rejects ZIP bombs).
15. Nested archive recursion rejection.
16. Secret scanning on all exported metadata (regex scan for API keys, bearer tokens).
17. Referential integrity validation across imported entities.
18. Line-by-line NDJSON JSON schema validation.
19. Duplicate record detection without silent overwriting.
20. Non-destructive transactional import with dry-run support.

### 2.3 ID Remapping & Foreign Key Translation (`id_aliases`)
- When importing on Computer B, assets and entities may receive local UUIDs while recording their foreign exported IDs in `id_aliases`:
  - `entity_type`: `asset` | `version` | `moment` | `annotation`
  - `foreign_id`: Original UUID from source machine.
  - `local_id`: New or resolved local UUID on destination machine.
  - `source_export_id`: UUID of the export archive.

### 2.4 Availability & Search Playback Contract
- Search and media queries return:
  - `asset_id`: Stable logical asset UUID.
  - `version_id`: Deterministic byte-level version UUID.
  - `availability`: `AVAILABLE` | `UNAVAILABLE` | `MISSING` | `RELINK_REQUIRED`
  - `can_play`: `True` if local media file is accessible on disk, else `False`.
  - `can_export`: `True` if local media file is accessible, else `False`.
  - `evidence_refs`: Timestamps and excerpts preserved regardless of file availability.

### 2.5 Read-Only MCP Tool Extensions
- MCP remains strictly read-only:
  1. `get_media_availability(version_id: str | None = None, video_id: str | None = None) -> dict`: Checks physical file presence and root status.
  2. `find_duplicate_media() -> list[dict]`: Identifies assets sharing identical SHA-256 versions across multiple locations.
  3. `get_evidence_citations(query: str, video_id: str | None = None) -> list[dict]`: Returns timestamped citations and evidence excerpts even when source media is offline.
  4. Capability Status API exposing `CapabilityStatus` and `CapabilityReason`.

---

## 3. Subtask Implementation Sequence

1. **TASK-4D.1: Versioned REST API & Schemas:**
   - Schemas in `backend/app/schemas/portable.py`.
   - Endpoints for media availability, duplicate discovery, annotations CRUD, and search availability contract updates.
2. **TASK-4D.2: Portable Memory Service (`portable_service.py`):**
   - Streamed ZIP writer and reader.
   - NDJSON serialization and deserialization.
   - Per-entry SHA-256 calculation and manifest creation.
3. **TASK-4D.3: Safe Export Engine:**
   - Database extraction of `Asset`, `AssetVersion`, `AssetLocation`, `Transcript`, `TranscriptSegment`, `VideoScene`, `Moment`, `Annotation`, and `Artifact`.
   - Path normalization and secret redaction.
4. **TASK-4D.4: Safe Import Engine & 20 Safeguards:**
   - Deep archive validation (ZIP bomb, traversal, size limits).
   - Dry-run import calculation (differences, conflicts, proposed remappings).
   - Transactional import with `IDAlias` mapping and rollback.
5. **TASK-4D.5: Cross-Machine Relinking & Cache Stability:**
   - Synthetic round trip between `C:/Creators/Videos/` and `D:/Media/Imported/`.
   - Relinking service attaching new local roots to preserved versions.
   - Stable result-cache key function.
6. **TASK-4D.6: MCP Read-Only Tools & Capability Status:**
   - Implementation of read-only MCP tools in `mcp_server/tools/video_tools.py` and `server.py`.
   - Comprehensive test verifying zero state-mutating MCP tools.

---

## 4. Identified Technical Risks & Mitigations

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **ZIP Path Traversal Attacks** | High | Resolve all paths relative to archive root; reject any entry with `..`, leading slashes, or drive letters (`C:`). |
| **Decompression Bomb (ZIP Bomb)** | Critical | Track cumulative uncompressed byte count during streaming; enforce 20:1 max ratio and 2 GB total cap. |
| **Accidental Secret Export** | High | Explicit model column serialization; regex scanner checking for `sk-`, `AIza`, and bearer tokens prior to writing. |
| **Referential Integrity Mismatches** | Medium | Validate parent-child relations during dry run; use `id_aliases` for foreign ID translation. |
| **High Memory on Large Libraries** | Medium | Stream NDJSON records line-by-line; never load full dataset into memory. |

---

## 5. Next Action
Proceed immediately to **TASK-4D.1**: Define portable schemas, annotation CRUD endpoints, and search availability contract extensions.

