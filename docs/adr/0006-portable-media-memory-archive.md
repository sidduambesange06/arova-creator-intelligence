# ADR-0006: Portable Media Memory Container Specification (.arova)

**Status:** Accepted  
**Date:** 2026-11-04  
**Author:** Principal Systems Architect  
**Scope:** Cross-Machine Intelligence Portability, Archive Integrity, and Untrusted Archive Defense (Task 4D)

---

## 1. Context and Problem Statement
Arova Creator Intelligence generates rich derived media intelligence:
- Exact content addressing (SHA-256 and UUIDv5).
- Hierarchical media locations.
- Scene cuts, keyframe timings, and moments.
- Speech transcripts and segment timecodes.
- On-screen OCR visual annotations.
- Multi-stage pipeline processing records and artifacts.

When a creator moves to a new machine, changes storage drives, or collaborates across workstations:
1. Re-indexing hundreds of gigabytes of video from scratch is computationally expensive and wastes hours.
2. Raw SQLite databases cannot be trivially shared because local filesystem paths (`C:\Users\Name\Videos`) differ across machines.
3. Transmitting raw video files across machines is unnecessary when the video already exists on both machines or can be relinked.
4. Archives imported from external sources must be treated as untrusted data vulnerable to path traversal (`../../`), zip bombs, corrupted records, or embedded secrets.

---

## 2. Decision and Container Specification

We establish a standardized, versioned, streaming archive format with the `.arova` file extension (based on ZIP encapsulation of NDJSON data files):

```
my_library_export.arova (ZIP archive)
├── manifest.json                # Metadata, schema version, cryptographic hash index
├── assets.ndjson                # Logical media assets
├── versions.ndjson              # Immutable byte identities & media metadata
├── locations.ndjson             # Normalized relative paths
├── transcripts.ndjson           # Full text & speech models
├── transcript_segments.ndjson   # Millisecond timecodes and words
├── scenes.ndjson                # Scene cuts and thumbnails references
├── moments.ndjson               # Timestamped interval markers
├── annotations.ndjson           # Human & AI visual/speech annotations
└── artifacts.ndjson             # Pipeline derived artifacts
```

### 2.1 Format Invariants
- **Format Version:** `1.0.0`
- **NDJSON Streaming:** All records are serialized line-by-line as UTF-8 NDJSON. Readers and writers process streams line-by-line, guaranteeing $O(1)$ memory consumption.
- **Strict Relative Paths:** Absolute paths (e.g. `C:\...`, `/home/...`) are forbidden. Locations store `rel_path_norm` relative to an unspecified library root.
- **Zero Secrets Invariant:** Environment variables, API keys, bearer tokens, or user credentials are strictly excluded. Exporter runs regex secret redaction before writing.
- **Source Media Exclusion:** Source video files are not included by default; the archive packages media intelligence only.

### 2.2 Archive Manifest Schema (`manifest.json`)
```json
{
  "format_version": "1.0.0",
  "export_id": "c1f7b028-2b89-4991-9543-c006509f7a77",
  "created_at": "2026-11-04T05:30:00Z",
  "generator": "Arova Creator Intelligence 0.1.0",
  "library_id": "default-library-uuid",
  "records_count": {
    "assets": 12,
    "versions": 14,
    "locations": 15,
    "transcripts": 12,
    "transcript_segments": 420,
    "scenes": 65,
    "moments": 65,
    "annotations": 70,
    "artifacts": 80
  },
  "entries": [
    {
      "name": "assets.ndjson",
      "sha256": "4b92...",
      "size_bytes": 1024
    },
    ...
  ]
}
```

### 2.3 Strict Untrusted Archive Defense (20 Pillars)
1. **Archive Type Check:** Extension must be `.arova` or `.zip`.
2. **ZIP File Validation:** Header verification; corrupt/truncated ZIPs rejected with HTTP 400.
3. **Manifest Schema Validation:** Must contain required fields and compatible `format_version`.
4. **Declared Entry Match:** No extra undeclared files; no missing declared files.
5. **Cryptographic Verification:** SHA-256 computed on extraction must strictly match `manifest.json`.
6. **No Absolute Paths:** Rejects `/...` or `\...`.
7. **No Directory Traversal:** Rejects entries containing `..`.
8. **No Windows Drive Letters:** Rejects `C:`, `D:`.
9. **No Symlinks or Special Files:** Regular files only.
10. **Entry Count Bound:** Max 100 entries per archive.
11. **Compressed Size Limit:** Max 500 MB (configurable).
12. **Uncompressed Size Limit:** Max 2 GB (configurable).
13. **Individual Entry Limit:** Max 200 MB per NDJSON file.
14. **Decompression Ratio Cap:** Max 20:1 ratio, mitigating ZIP bomb vectors.
15. **No Nested Archives:** Sub-archives (`.zip`, `.tar`) rejected.
16. **Secret Sanitization:** Metadata scanned for API key patterns.
17. **Referential Integrity:** Parent-child relations validated prior to DB insert.
18. **Line-by-Line JSON Schema:** Malformed JSON lines rejected with error line number.
19. **Dry Run Preview:** Full validation without database mutation.
20. **Transactional Rollback:** All-or-nothing database commit with foreign-to-local ID translation in `id_aliases`.

---

## 3. Cross-Machine Relinking & Result Cache Stability
When an imported asset's version SHA-256 matches local media discovered in a new directory, a new `AssetLocation` is registered. Because `version_id` is content-derived and deterministic (UUIDv5), search result cache keys derived from `(version_id, query_hash)` remain stable across machine transfers.

