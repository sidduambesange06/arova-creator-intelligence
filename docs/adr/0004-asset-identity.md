# ADR-0004: Asset Identity, Multi-Mode Execution, and Media Memory Architecture

**Status:** Accepted  
**Date:** 2026-11-02  
**Author:** Principal Backend Engineer  
**Scope:** Core Data Model, Alembic Migrations, and Execution Profiles (Task 4 Stage 4A)

---

## 1. Context and Problem Statement

Arova Creator Intelligence initially tracked media files through a single `videos` table keyed by arbitrary UUIDs and filesystem paths. This model conflated three distinct concepts:
1. Physical location on disk (which may move, disconnect, or duplicate).
2. Logical content identity (an intellectual media asset across edits/versions).
3. Exact byte identity (the immutable byte stream with specific duration, timecodes, and derived transcripts/scenes/embeddings).

Furthermore, derived data (transcripts, scene cuts, OCR, embeddings, and summaries) was linked directly to `video_id`. When a file was moved or duplicated, or when media bytes changed at the same path, timestamps and derived evidence became decoupled or invalid.

Additionally, Arova requires an offline-first architecture supporting four distinct execution profiles (`FULLY_OFFLINE_NO_AI`, `LOCAL_AI`, `BYOK_REMOTE_AI`, `HYBRID_AI`) with strict, non-bypassable boundaries for local privacy, remote AI consent, and cross-machine portability.

---

## 2. Decision and Reference Schema Mapping

We introduce a four-layer media memory hierarchy that cleanly wraps existing tables without destroying existing data or breaking current search and processing contracts:

```
[Library] (stores ExecutionProfile, default: fully_offline_no_ai)
   │
   ├── [LibraryRoot] (root_type: local_fixed|removable|network, policy: local_only|allow_remote)
   │      │
   │      └── [AssetLocation] (rel_path, availability: AVAILABLE|UNAVAILABLE|MISSING|RELINK_REQUIRED)
   │
   └── [Asset] (stable logical media identity)
          │
          └── [AssetVersion] (immutable byte identity, deterministic UUIDv5)
                 │
                 ├── [StageRun] (resumable processing state, skip_reason: CapabilityReason)
                 ├── [Artifact] (derived data, atomic superseding via is_current)
                 ├── [Moment] (timestamped interval [start_ms, end_ms])
                 ├── [Annotation] (human/AI attribution, display_name, trust)
                 └── [Legacy Bridge: Video, Transcript, VideoScene, EmbeddingRecord, VideoSummary]
```

### Table Mapping Matrix

| Reference Entity | Physical Database Table | Relationship to Existing Code |
|---|---|---|
| `libraries` | `libraries` | New table. Defines workspace boundary and `execution_profile`. |
| `library_roots` | `library_roots` | New table. Tracks storage mounts (`volume_id`, `root_type`, `policy`). |
| `assets` | `assets` | New table. Stable logical asset UUID. |
| `asset_versions` | `asset_versions` | New table. Immutable byte identity (`sha256`, UUIDv5, `media_meta`). |
| `asset_locations` | `asset_locations` | New table. Path relative to a root (`rel_path`, `rel_path_norm`, `availability`). |
| `videos` (Legacy) | `videos` | Preserved intact. Gained `asset_id` and `version_id` foreign keys. |
| `transcripts` | `transcripts` | Preserved intact. References `video_id` and attaches to exact version. |
| `transcript_segments` | `transcript_segments` | Preserved intact. Provides millisecond-accurate text intervals. |
| `video_scenes` | `video_scenes` | Preserved intact. Maps to visual scene cuts. |
| `embedding_records` | `embedding_records` | Preserved intact. Dense vector representations. |
| `video_summaries` | `video_summaries` | Preserved intact. Cached grounded video summaries. |
| `stage_runs` | `stage_runs` | New table. Resumable pipeline stages with leases and `skip_reason`. |
| `artifacts` | `artifacts` | New table. Generic artifact registry with atomic `is_current` superseding. |
| `moments` | `moments` | New table. Stable timestamp intervals (`start_ms`, `end_ms`, `kind`). |
| `annotations` | `annotations` | New table. Human/AI annotations with attribution and trust provenance. |
| `ai_consents` | `ai_consents` | New table. Scoped consent metadata (zero secrets/keys stored). |
| `ai_runs` | `ai_runs` | New table. Provenance log for AI invocations with consent FK. |
| `id_aliases` | `id_aliases` | New table. Foreign-to-local ID mapping scoped by `source_export_id`. |
| `asset_relations` | `asset_relations` | New table. Asset-to-asset edges (`duplicate_of`, `derived_from`, `proxy_of`). |
| `scan_runs` | `scan_runs` | New table. Checkpoint and inventory state for root scans. |

---

## 3. Deterministic Version Identity

For any newly verified media file with full streaming SHA-256 digest, the `version_id` is derived deterministically as UUIDv5 using the fixed namespace:

```python
NAMESPACE_AROVA_VERSION = uuid.UUID("15e68111-cb50-55cb-9518-e6ed85b67dfd")
version_id = uuid.uuid5(NAMESPACE_AROVA_VERSION, lowercase_sha256_hex)
```

- Guarantees identical byte streams produce identical version IDs across independent machines and installations.
- Legacy unverified versions retain their legacy ID and are flagged `identity_state = "identity_unverified"` with `sha256 = NULL` until verified by Tier C streaming hash.
- Upgrading an unverified version to a deterministic version preserves all foreign keys transactionally and logs the old-to-new mapping in `id_aliases`.

---

## 4. Alembic Migration Strategy & Database Safety

1. **Pre-Migration Backup:** Before executing any migration on an existing database, the runner executes `VACUUM INTO '<db_path>.backup.<timestamp>'` (or verified physical copy), ensuring non-destructive recovery if a migration fails.
2. **Baseline Stamping:** Existing databases created via `Base.metadata.create_all()` lack an `alembic_version` table. The runner inspects the database: if legacy tables (`videos`) exist without `alembic_version`, it automatically stamps the database with baseline revision `0001_initial_schema` before upgrading to forward revisions.
3. **SQLite Batch Mode:** All schema alterations utilize Alembic's `batch_alter_table` to recreate tables safely within SQLite's transactional DDL constraints.
4. **Idempotent Backfill:** Existing `Video` rows are automatically backfilled into `Library`, `LibraryRoot`, `Asset`, `AssetVersion`, and `AssetLocation` records. Rerunning backfill is a strict no-op.
5. **No `create_all()` on Startup:** Startup executes explicit Alembic migrations, eliminating runtime schema drifting.

---

## 5. Multi-Mode Security & Consent Precedence

A remote provider call is permitted only when **all** of the following conditions are met:
1. Library `execution_profile` is `BYOK_REMOTE_AI` or eligible `HYBRID_AI`.
2. Source root `policy` is `ALLOW_REMOTE` (`LOCAL_ONLY` always denies egress).
3. Active, unexpired, unrevoked `ai_consents` record matches provider, endpoint host, capability, and data categories.
4. Provider capability is validated and available.
5. Configured budget limits have not been exceeded.

The most restrictive setting always wins. `FULLY_OFFLINE_NO_AI` and `LOCAL_AI` strictly deny all outbound network activity.

