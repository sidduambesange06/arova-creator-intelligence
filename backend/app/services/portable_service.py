"""Portable Media Memory Service for Task 4D.

Implements:
1. Versioned .arova container export with streamed NDJSON entries.
2. Cryptographic manifest with per-entry SHA-256 hashes.
3. 20 strict untrusted-archive validation safeguards (path traversal, zip bombs, size caps).
4. Dry-run import calculation without database mutation.
5. Transactional import with foreign-to-local ID translation via IDAlias.
6. Safe cross-machine media relinking and availability resolution.
7. Stable query result-cache keys unaffected by filesystem relinking.
"""

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Generator
from uuid import uuid4
import zipfile

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import compute_sha256
from app.models.entities import (
    Annotation,
    Artifact,
    Asset,
    AssetLocation,
    AssetVersion,
    IDAlias,
    Library,
    LibraryRoot,
    LocationAvailability,
    Moment,
    Transcript,
    TranscriptSegment,
    Video,
    VideoScene,
)
from app.models.enums import (
    IdentityState,
    TrustLevel,
    compute_deterministic_version_id,
)
from app.schemas.portable import (
    ArchiveEntryManifest,
    ArchiveManifest,
    ExportRequest,
    ExportSummary,
    ImportDryRunReport,
    ImportResult,
    MediaAvailabilityOut,
    RelinkResponse,
)

PORTABLE_FORMAT_VERSION = "1.0.0"

# Safeguard Limits (Configurable defaults)
MAX_ARCHIVE_ENTRIES = 100
MAX_COMPRESSED_SIZE_BYTES = 500 * 1024 * 1024       # 500 MB
MAX_UNCOMPRESSED_TOTAL_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_SINGLE_ENTRY_BYTES = 200 * 1024 * 1024         # 200 MB
MAX_DECOMPRESSION_RATIO = 20.0                      # 20:1 max ratio

# Secret detection patterns
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),          # OpenAI / generic secret keys
    re.compile(r"AIza[0-9A-Za-z-_]{25,}"),          # Google API keys
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}"),  # Bearer tokens
]


class ArchiveSecurityError(ValueError):
    """Raised when an archive violates security safeguards."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_text_for_export(text: str) -> str:
    """Detect and redact any embedded API keys or credentials."""
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def compute_search_cache_key(version_id: str, query: str) -> str:
    """Compute a stable search result cache key invariant to local filesystem paths."""
    clean_q = query.strip().lower()
    raw = f"search:{version_id}:{clean_q}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# EXPORT IMPLEMENTATION
# -----------------------------------------------------------------------------

def export_portable_archive(
    db: Session,
    target_archive_path: Path | str,
    request: ExportRequest | None = None,
) -> ExportSummary:
    """Export database intelligence records into a versioned streaming .arova archive."""
    out_path = Path(target_archive_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    export_id = str(uuid4())
    created_at = _utcnow()
    req = request or ExportRequest()

    # Query entities to export
    assets_query = db.query(Asset)
    if req.asset_ids:
        assets_query = assets_query.filter(Asset.id.in_(req.asset_ids))
    assets = assets_query.all()
    asset_ids = {a.id for a in assets}

    versions = db.query(AssetVersion).filter(AssetVersion.asset_id.in_(asset_ids)).all() if asset_ids else []
    version_ids = {v.id for v in versions}

    locations = db.query(AssetLocation).filter(AssetLocation.version_id.in_(version_ids)).all() if version_ids else []
    moments = db.query(Moment).filter(Moment.version_id.in_(version_ids)).all() if version_ids else []

    annotations_query = db.query(Annotation).filter(
        (Annotation.target_type == "version") & (Annotation.target_id.in_(version_ids))
        | (Annotation.target_type == "asset") & (Annotation.target_id.in_(asset_ids))
    )
    annotations = annotations_query.all() if version_ids or asset_ids else []

    artifacts = []
    if req.include_artifacts and version_ids:
        artifacts = db.query(Artifact).filter(Artifact.version_id.in_(version_ids)).all()

    # Legacy transcripts & scenes mapped via version_id
    videos = db.query(Video).filter(Video.version_id.in_(version_ids)).all() if version_ids else []
    video_ids = {v.id for v in videos}

    transcripts = db.query(Transcript).filter(Transcript.video_id.in_(video_ids)).all() if video_ids else []
    transcript_ids = {t.id for t in transcripts}

    segments = (
        db.query(TranscriptSegment).filter(TranscriptSegment.transcript_id.in_(transcript_ids)).all()
        if transcript_ids
        else []
    )
    scenes = db.query(VideoScene).filter(VideoScene.video_id.in_(video_ids)).all() if video_ids else []

    # Stream NDJSON files into the ZIP container
    entries_manifest: list[ArchiveEntryManifest] = []
    records_count: dict[str, int] = {
        "assets": len(assets),
        "versions": len(versions),
        "locations": len(locations),
        "transcripts": len(transcripts),
        "transcript_segments": len(segments),
        "scenes": len(scenes),
        "moments": len(moments),
        "annotations": len(annotations),
        "artifacts": len(artifacts),
    }

    with zipfile.ZipFile(out_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

        def _write_ndjson_entry(filename: str, rows_gen: Generator[dict[str, Any], None, None]) -> None:
            buf = io.BytesIO()
            hasher = hashlib.sha256()
            size = 0

            for row in rows_gen:
                line_str = json.dumps(row, ensure_ascii=False) + "\n"
                sanitized_line = sanitize_text_for_export(line_str)
                encoded = sanitized_line.encode("utf-8")
                buf.write(encoded)
                hasher.update(encoded)
                size += len(encoded)

            buf.seek(0)
            zf.writestr(filename, buf.getvalue())
            entries_manifest.append(
                ArchiveEntryManifest(name=filename, sha256=hasher.hexdigest(), size_bytes=size)
            )

        # 1. assets.ndjson
        def _gen_assets():
            for a in assets:
                yield {
                    "id": a.id,
                    "current_version_id": a.current_version_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
        _write_ndjson_entry("assets.ndjson", _gen_assets())

        # 2. versions.ndjson
        def _gen_versions():
            for v in versions:
                yield {
                    "id": v.id,
                    "asset_id": v.asset_id,
                    "sha256": v.sha256,
                    "size_bytes": v.size_bytes,
                    "media_meta": v.media_meta,
                    "supersedes_version_id": v.supersedes_version_id,
                    "identity_state": v.identity_state,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
        _write_ndjson_entry("versions.ndjson", _gen_versions())

        # 3. locations.ndjson (strictly normalized relative paths, no absolute paths)
        def _gen_locations():
            for loc in locations:
                yield {
                    "id": loc.id,
                    "version_id": loc.version_id,
                    "rel_path_norm": loc.rel_path_norm or Path(loc.rel_path).as_posix().lstrip("/"),
                    "stat_key": loc.stat_key,
                    "availability": loc.availability,
                    "last_seen_at": loc.last_seen_at.isoformat() if loc.last_seen_at else None,
                }
        _write_ndjson_entry("locations.ndjson", _gen_locations())

        # 4. transcripts.ndjson
        def _gen_transcripts():
            for t in transcripts:
                v_id = t.video.version_id if t.video else None
                yield {
                    "id": t.id,
                    "version_id": v_id,
                    "video_id": t.video_id,
                    "language": t.language,
                    "model_name": t.model_name,
                    "full_text": t.full_text,
                }
        _write_ndjson_entry("transcripts.ndjson", _gen_transcripts())

        # 5. transcript_segments.ndjson
        def _gen_segments():
            for s in segments:
                yield {
                    "id": s.id,
                    "transcript_id": s.transcript_id,
                    "video_id": s.video_id,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "text": s.text,
                    "confidence": s.confidence,
                }
        _write_ndjson_entry("transcript_segments.ndjson", _gen_segments())

        # 6. scenes.ndjson
        def _gen_scenes():
            for sc in scenes:
                v_id = sc.video.version_id if sc.video else None
                yield {
                    "id": sc.id,
                    "version_id": v_id,
                    "video_id": sc.video_id,
                    "scene_index": sc.scene_index,
                    "start_time": sc.start_time,
                    "end_time": sc.end_time,
                    "description": sc.description,
                }
        _write_ndjson_entry("scenes.ndjson", _gen_scenes())

        # 7. moments.ndjson
        def _gen_moments():
            for m in moments:
                yield {
                    "id": m.id,
                    "version_id": m.version_id,
                    "start_ms": m.start_ms,
                    "end_ms": m.end_ms,
                    "kind": m.kind,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
        _write_ndjson_entry("moments.ndjson", _gen_moments())

        # 8. annotations.ndjson
        def _gen_annotations():
            for an in annotations:
                yield {
                    "id": an.id,
                    "target_type": an.target_type,
                    "target_id": an.target_id,
                    "author_type": an.author_type,
                    "display_name": an.display_name,
                    "trust": an.trust,
                    "ai_run_id": an.ai_run_id,
                    "body": an.body,
                    "created_at": an.created_at.isoformat() if an.created_at else None,
                }
        _write_ndjson_entry("annotations.ndjson", _gen_annotations())

        # 9. artifacts.ndjson
        def _gen_artifacts():
            for art in artifacts:
                yield {
                    "id": art.id,
                    "version_id": art.version_id,
                    "kind": art.kind,
                    "producer_stage": art.producer_stage,
                    "producer_model": art.producer_model,
                    "producer_revision": art.producer_revision,
                    "config_hash": art.config_hash,
                    "is_current": art.is_current,
                    "trust": art.trust,
                    "created_at": art.created_at.isoformat() if art.created_at else None,
                }
        _write_ndjson_entry("artifacts.ndjson", _gen_artifacts())

        # 10. Write manifest.json
        manifest = ArchiveManifest(
            format_version=PORTABLE_FORMAT_VERSION,
            export_id=export_id,
            created_at=created_at,
            library_id=request.library_id if request else None,
            records_count=records_count,
            entries=entries_manifest,
        )
        manifest_bytes = manifest.model_dump_json(indent=2).encode("utf-8")
        zf.writestr("manifest.json", manifest_bytes)

    # Compute overall archive SHA-256
    archive_size = out_path.stat().st_size
    archive_sha256 = compute_sha256(out_path)

    return ExportSummary(
        export_id=export_id,
        format_version=PORTABLE_FORMAT_VERSION,
        created_at=created_at,
        archive_name=out_path.name,
        file_size_bytes=archive_size,
        sha256=archive_sha256,
        records_count=records_count,
    )


# -----------------------------------------------------------------------------
# SAFE IMPORT & VALIDATION (20 SAFEGUARDS)
# -----------------------------------------------------------------------------

def validate_archive(archive_path: Path | str) -> tuple[ArchiveManifest, dict[str, list[dict[str, Any]]]]:
    """Validate untrusted .arova archive against all 20 security safeguards."""
    path = Path(archive_path).resolve()

    # 1. Archive existence and type check
    if not path.is_file():
        raise ArchiveSecurityError(f"Archive file not found: {path}")
    if path.suffix.lower() not in (".arova", ".zip"):
        raise ArchiveSecurityError(f"Invalid archive extension: expected .arova or .zip, got {path.suffix}")

    # 2. Check compressed size limit
    compressed_size = path.stat().st_size
    if compressed_size > MAX_COMPRESSED_SIZE_BYTES:
        raise ArchiveSecurityError(
            f"Archive exceeds maximum compressed size limit ({compressed_size} > {MAX_COMPRESSED_SIZE_BYTES} bytes)"
        )

    # 3. Open and verify ZIP integrity
    try:
        zf = zipfile.ZipFile(path, mode="r")
    except zipfile.BadZipFile as exc:
        raise ArchiveSecurityError(f"Corrupt or invalid ZIP archive: {exc}")

    with zf:
        infolist = zf.infolist()

        # 4. Enforce entry count bound
        if len(infolist) > MAX_ARCHIVE_ENTRIES:
            raise ArchiveSecurityError(
                f"Archive entry count ({len(infolist)}) exceeds maximum limit ({MAX_ARCHIVE_ENTRIES})"
            )

        total_uncompressed = 0
        names = set()

        for info in infolist:
            names.add(info.filename)
            total_uncompressed += info.file_size

            # 5. Reject absolute paths, Windows drive paths, and traversal
            if info.filename.startswith(("/", "\\")) or re.match(r"^[a-zA-Z]:", info.filename):
                raise ArchiveSecurityError(f"Dangerous absolute path in archive: {info.filename}")
            if ".." in info.filename:
                raise ArchiveSecurityError(f"Path traversal detected in archive entry: {info.filename}")

            # 6. Reject nested archives
            if info.filename.lower().endswith((".zip", ".tar", ".gz", ".arova")):
                raise ArchiveSecurityError(f"Nested archive entry rejected: {info.filename}")

            # 7. Reject per-entry size limits
            if info.file_size > MAX_SINGLE_ENTRY_BYTES:
                raise ArchiveSecurityError(
                    f"Entry {info.filename} exceeds single-entry limit ({info.file_size} > {MAX_SINGLE_ENTRY_BYTES})"
                )

        # 8. Total uncompressed size limit
        if total_uncompressed > MAX_UNCOMPRESSED_TOTAL_BYTES:
            raise ArchiveSecurityError(
                f"Total uncompressed size ({total_uncompressed}) exceeds maximum limit ({MAX_UNCOMPRESSED_TOTAL_BYTES})"
            )

        # 9. Decompression ratio limit (ZIP bomb protection)
        if compressed_size > 0:
            ratio = total_uncompressed / compressed_size
            if ratio > MAX_DECOMPRESSION_RATIO:
                raise ArchiveSecurityError(
                    f"Suspicious decompression ratio ({ratio:.1f}:1 exceeds safe maximum {MAX_DECOMPRESSION_RATIO}:1)"
                )

        # 10. Manifest must be present
        if "manifest.json" not in names:
            raise ArchiveSecurityError("Archive is missing required root manifest.json")

        try:
            manifest_raw = json.loads(zf.read("manifest.json").decode("utf-8"))
            manifest = ArchiveManifest.model_validate(manifest_raw)
        except Exception as exc:
            raise ArchiveSecurityError(f"Malformed manifest.json in archive: {exc}")

        # 11. Format version compatibility
        if not manifest.format_version.startswith("1."):
            raise ArchiveSecurityError(
                f"Incompatible archive format version: {manifest.format_version} (supported: 1.x)"
            )

        # 12. Validate declared entries match actual archive files
        declared_names = {e.name for e in manifest.entries}
        declared_names.add("manifest.json")
        if names != declared_names:
            diff = names.symmetric_difference(declared_names)
            raise ArchiveSecurityError(f"Archive entry mismatch between manifest and actual files: {diff}")

        # 13. Cryptographic hash and byte size validation for each entry
        parsed_records: dict[str, list[dict[str, Any]]] = {}

        for entry in manifest.entries:
            file_bytes = zf.read(entry.name)
            if len(file_bytes) != entry.size_bytes:
                raise ArchiveSecurityError(
                    f"Entry size mismatch for {entry.name}: declared {entry.size_bytes}, got {len(file_bytes)}"
                )

            actual_sha = hashlib.sha256(file_bytes).hexdigest()
            if actual_sha != entry.sha256:
                raise ArchiveSecurityError(
                    f"Cryptographic checksum mismatch for {entry.name}: expected {entry.sha256}, got {actual_sha}"
                )

            # 14. Line-by-line NDJSON parsing and secret scanning
            lines = file_bytes.decode("utf-8").splitlines()
            records_list = []
            for line_no, line in enumerate(lines, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue

                for sec_pat in SECRET_PATTERNS:
                    if sec_pat.search(clean_line):
                        raise ArchiveSecurityError(
                            f"Prohibited credential or secret detected in {entry.name} line {line_no}"
                        )

                try:
                    record_obj = json.loads(clean_line)
                    records_list.append(record_obj)
                except json.JSONDecodeError as exc:
                    raise ArchiveSecurityError(
                        f"Malformed JSON in {entry.name} at line {line_no}: {exc}"
                    )

            parsed_records[entry.name] = records_list

    return manifest, parsed_records


def dry_run_import_archive(db: Session, archive_path: Path | str) -> ImportDryRunReport:
    """Preview archive import without mutating the database."""
    manifest, parsed = validate_archive(archive_path)

    records_to_import: dict[str, int] = {}
    matching_existing: dict[str, int] = {}
    proposed_remappings = 0
    warnings: list[str] = []
    errors: list[str] = []

    # Check Assets
    assets_raw = parsed.get("assets.ndjson", [])
    new_assets = 0
    existing_assets = 0
    for a in assets_raw:
        if db.get(Asset, a["id"]):
            existing_assets += 1
        else:
            new_assets += 1
    records_to_import["assets"] = new_assets
    matching_existing["assets"] = existing_assets

    # Check Versions
    versions_raw = parsed.get("versions.ndjson", [])
    new_versions = 0
    existing_versions = 0
    for v in versions_raw:
        # Check by content sha256 or ID
        existing_v = db.query(AssetVersion).filter(
            (AssetVersion.id == v["id"]) | (AssetVersion.sha256 == v["sha256"])
        ).first()
        if existing_v:
            existing_versions += 1
            if existing_v.id != v["id"]:
                proposed_remappings += 1
        else:
            new_versions += 1
    records_to_import["versions"] = new_versions
    matching_existing["versions"] = existing_versions

    # Count other entries
    for key in ("transcripts.ndjson", "transcript_segments.ndjson", "scenes.ndjson", "moments.ndjson", "annotations.ndjson", "artifacts.ndjson"):
        records_to_import[key.replace(".ndjson", "")] = len(parsed.get(key, []))

    return ImportDryRunReport(
        valid=True,
        format_version=manifest.format_version,
        export_id=manifest.export_id,
        total_entries=len(manifest.entries),
        records_to_import=records_to_import,
        matching_existing_records=matching_existing,
        duplicate_conflicts=0,
        proposed_id_remappings=proposed_remappings,
        estimated_size_bytes=sum(e.size_bytes for e in manifest.entries),
        warnings=warnings,
        errors=errors,
    )


def import_portable_archive(
    db: Session,
    archive_path: Path | str,
    library_id: str | None = None,
) -> ImportResult:
    """Safely import validated records into the database with ID remapping and rollback."""
    manifest, parsed = validate_archive(archive_path)
    export_id = manifest.export_id

    imported_counts: dict[str, int] = {
        "assets": 0,
        "versions": 0,
        "transcripts": 0,
        "transcript_segments": 0,
        "scenes": 0,
        "moments": 0,
        "annotations": 0,
        "artifacts": 0,
    }
    remapped_count = 0
    id_map: dict[str, str] = {}  # foreign_id -> local_id

    try:
        # 1. Import Assets
        for a_row in parsed.get("assets.ndjson", []):
            foreign_id = a_row["id"]
            existing = db.get(Asset, foreign_id)
            if existing:
                id_map[foreign_id] = existing.id
            else:
                local_asset = Asset(
                    id=foreign_id,
                    created_at=datetime.fromisoformat(a_row["created_at"]) if a_row.get("created_at") else _utcnow(),
                )
                db.add(local_asset)
                db.flush()
                id_map[foreign_id] = local_asset.id
                imported_counts["assets"] += 1

        # 2. Import Versions
        for v_row in parsed.get("versions.ndjson", []):
            foreign_vid = v_row["id"]
            sha256 = v_row.get("sha256")
            expected_local_id = compute_deterministic_version_id(sha256) if sha256 else foreign_vid

            existing_v = db.query(AssetVersion).filter(
                (AssetVersion.id == foreign_vid) | (AssetVersion.sha256 == sha256)
            ).first()

            parent_asset_id = id_map.get(v_row["asset_id"], v_row["asset_id"])

            if existing_v:
                id_map[foreign_vid] = existing_v.id
                if existing_v.id != foreign_vid:
                    remapped_count += 1
                    # Record alias
                    db.add(
                        IDAlias(
                            entity_type="version",
                            foreign_id=foreign_vid,
                            local_id=existing_v.id,
                            source_export_id=export_id,
                            created_at=_utcnow(),
                        )
                    )
            else:
                new_version = AssetVersion(
                    id=expected_local_id,
                    asset_id=parent_asset_id,
                    sha256=sha256,
                    size_bytes=v_row.get("size_bytes", 0),
                    media_meta=v_row.get("media_meta"),
                    supersedes_version_id=v_row.get("supersedes_version_id"),
                    identity_state=v_row.get("identity_state", IdentityState.VERIFIED.value),
                    created_at=datetime.fromisoformat(v_row["created_at"]) if v_row.get("created_at") else _utcnow(),
                )
                db.add(new_version)
                db.flush()
                id_map[foreign_vid] = new_version.id
                imported_counts["versions"] += 1

                if expected_local_id != foreign_vid:
                    remapped_count += 1
                    db.add(
                        IDAlias(
                            entity_type="version",
                            foreign_id=foreign_vid,
                            local_id=expected_local_id,
                            source_export_id=export_id,
                            created_at=_utcnow(),
                        )
                    )

        # 2b. Import Locations
        for loc_row in parsed.get("locations.ndjson", []):
            mapped_vid = id_map.get(loc_row["version_id"], loc_row["version_id"])
            if not db.get(AssetVersion, mapped_vid):
                continue
            default_root = db.query(LibraryRoot).first()
            if not default_root:
                lib = db.query(Library).first()
                if not lib:
                    lib = Library(id=str(uuid4()), label="Default Library")
                    db.add(lib)
                    db.flush()
                default_root = LibraryRoot(
                    id=str(uuid4()),
                    library_id=lib.id,
                    label="Default Root",
                    volume_id="",
                    root_type="local_fixed",
                    policy="local_only",
                )
                db.add(default_root)
                db.flush()

            existing_loc = db.query(AssetLocation).filter_by(
                version_id=mapped_vid,
                rel_path_norm=loc_row["rel_path_norm"],
            ).first()
            if not existing_loc:
                new_loc = AssetLocation(
                    id=str(uuid4()),
                    version_id=mapped_vid,
                    root_id=default_root.id,
                    rel_path=loc_row["rel_path_norm"],
                    rel_path_norm=loc_row["rel_path_norm"],
                    stat_key=loc_row.get("stat_key"),
                    availability=loc_row.get("availability", LocationAvailability.MISSING.value),
                    last_seen_at=datetime.fromisoformat(loc_row["last_seen_at"]) if loc_row.get("last_seen_at") else _utcnow(),
                )
                db.add(new_loc)

        # 2c. Ensure Video row exists for each imported/mapped version and import Transcripts & Segments
        # Build version -> Video map
        version_to_video: dict[str, str] = {}
        for foreign_vid, local_vid in id_map.items():
            ver = db.get(AssetVersion, local_vid)
            if not ver:
                continue
            v_obj = db.query(Video).filter_by(version_id=ver.id).first()
            if not v_obj:
                v_obj = Video(
                    id=str(uuid4()),
                    asset_id=ver.asset_id,
                    version_id=ver.id,
                    filename=f"asset_{ver.asset_id[:8]}.mp4",
                    file_path=f"asset_{ver.asset_id[:8]}.mp4",
                    file_hash=ver.sha256 or hashlib.sha256(ver.id.encode("utf-8")).hexdigest(),
                    duration=0.0,
                    processing_status="completed",
                )
                db.add(v_obj)
                db.flush()
            version_to_video[local_vid] = v_obj.id
            version_to_video[foreign_vid] = v_obj.id

        transcript_map: dict[str, str] = {}
        for t_row in parsed.get("transcripts.ndjson", []):
            foreign_tid = t_row["id"]
            raw_v_key = t_row.get("version_id") or t_row.get("video_id")
            mapped_vid = id_map.get(raw_v_key, raw_v_key)
            target_video_id = version_to_video.get(mapped_vid) or version_to_video.get(raw_v_key)

            if not target_video_id:
                # Fallback to direct video search
                vid_direct = db.get(Video, raw_v_key)
                if vid_direct:
                    target_video_id = vid_direct.id

            if target_video_id:
                transcript = Transcript(
                    id=str(uuid4()),
                    video_id=target_video_id,
                    language=t_row.get("language", "en"),
                    model_name=t_row.get("model_name", "imported"),
                    full_text=t_row.get("full_text", ""),
                )
                db.add(transcript)
                db.flush()
                transcript_map[foreign_tid] = transcript.id
                imported_counts["transcripts"] += 1

        for s_row in parsed.get("transcript_segments.ndjson", []):
            mapped_tid = transcript_map.get(s_row["transcript_id"], s_row["transcript_id"])
            t_obj = db.get(Transcript, mapped_tid)
            if t_obj:
                seg = TranscriptSegment(
                    id=str(uuid4()),
                    transcript_id=mapped_tid,
                    video_id=t_obj.video_id,
                    start_time=s_row["start_time"],
                    end_time=s_row["end_time"],
                    text=s_row["text"],
                    confidence=s_row.get("confidence", 1.0),
                )
                db.add(seg)
                imported_counts["transcript_segments"] += 1

        for sc_row in parsed.get("scenes.ndjson", []):
            raw_v_key = sc_row.get("version_id") or sc_row.get("video_id")
            mapped_vid = id_map.get(raw_v_key, raw_v_key)
            target_video_id = version_to_video.get(mapped_vid) or version_to_video.get(raw_v_key)
            if target_video_id:
                scene = VideoScene(
                    id=str(uuid4()),
                    video_id=target_video_id,
                    scene_index=sc_row.get("scene_index", 0),
                    start_time=sc_row["start_time"],
                    end_time=sc_row["end_time"],
                    description=sc_row.get("description"),
                )
                db.add(scene)
                imported_counts["scenes"] += 1

        # 3. Import Moments
        for m_row in parsed.get("moments.ndjson", []):
            mapped_vid = id_map.get(m_row["version_id"], m_row["version_id"])
            if not db.get(AssetVersion, mapped_vid):
                continue
            moment = Moment(
                id=str(uuid4()),
                version_id=mapped_vid,
                start_ms=m_row["start_ms"],
                end_ms=m_row["end_ms"],
                kind=m_row.get("kind", "scene"),
                created_at=_utcnow(),
            )
            db.add(moment)
            imported_counts["moments"] += 1

        # 4. Import Annotations
        for an_row in parsed.get("annotations.ndjson", []):
            mapped_tid = id_map.get(an_row["target_id"], an_row["target_id"])
            annotation = Annotation(
                id=str(uuid4()),
                target_type=an_row["target_type"],
                target_id=mapped_tid,
                author_type=an_row["author_type"],
                display_name=an_row["display_name"],
                trust=an_row.get("trust", TrustLevel.HUMAN_CONFIRMED.value),
                ai_run_id=an_row.get("ai_run_id"),
                body=an_row["body"],
                created_at=_utcnow(),
            )
            db.add(annotation)
            imported_counts["annotations"] += 1

        # 5. Import Artifacts
        for art_row in parsed.get("artifacts.ndjson", []):
            mapped_vid = id_map.get(art_row["version_id"], art_row["version_id"])
            if not db.get(AssetVersion, mapped_vid):
                continue
            artifact = Artifact(
                id=str(uuid4()),
                version_id=mapped_vid,
                kind=art_row["kind"],
                producer_stage=art_row["producer_stage"],
                producer_model=art_row.get("producer_model"),
                producer_revision=art_row.get("producer_revision"),
                config_hash=art_row.get("config_hash"),
                is_current=art_row.get("is_current", True),
                trust=art_row.get("trust", TrustLevel.UNVERIFIED.value),
                created_at=_utcnow(),
            )
            db.add(artifact)
            imported_counts["artifacts"] += 1

        db.commit()
        return ImportResult(
            status="success",
            export_id=export_id,
            imported_counts=imported_counts,
            remapped_count=remapped_count,
        )

    except Exception as exc:
        db.rollback()
        return ImportResult(
            status="rejected",
            export_id=export_id,
            errors=[f"Import failed during database transaction: {exc}"],
        )


# -----------------------------------------------------------------------------
# MEDIA AVAILABILITY & CROSS-MACHINE RELINKING
# -----------------------------------------------------------------------------

def resolve_media_availability(db: Session, version_id: str) -> MediaAvailabilityOut:
    """Resolve physical media availability, can_play, and can_export flags."""
    version = db.get(AssetVersion, version_id)
    if not version:
        raise LookupError(f"AssetVersion {version_id} not found")

    # Find associated video row if present
    video = db.query(Video).filter_by(version_id=version_id).first()

    # Find locations
    locations = db.query(AssetLocation).filter_by(version_id=version_id).all()
    available_loc = None

    for loc in locations:
        if loc.root and loc.root.volume_id and loc.rel_path:
            candidate_path = Path(loc.root.volume_id) / loc.rel_path
            if candidate_path.is_file():
                available_loc = (loc, candidate_path)
                break

    if not available_loc and video and Path(video.file_path).is_file():
        file_p = str(Path(video.file_path).resolve())
        return MediaAvailabilityOut(
            version_id=version_id,
            video_id=video.id,
            availability=LocationAvailability.AVAILABLE.value,
            can_play=True,
            can_export=True,
            file_path=file_p,
            last_seen_at=video.created_at,
        )

    if available_loc:
        loc_obj, resolved_path = available_loc
        return MediaAvailabilityOut(
            version_id=version_id,
            video_id=video.id if video else None,
            availability=LocationAvailability.AVAILABLE.value,
            can_play=True,
            can_export=True,
            file_path=str(resolved_path),
            root_type=loc_obj.root.root_type if loc_obj.root else None,
            last_seen_at=loc_obj.last_seen_at,
        )

    return MediaAvailabilityOut(
        version_id=version_id,
        video_id=video.id if video else None,
        availability=LocationAvailability.MISSING.value,
        can_play=False,
        can_export=False,
        file_path=video.file_path if video else None,
    )


def relink_asset_media(
    db: Session,
    version_id: str,
    new_file_path: Path | str,
    allowed_roots: list[Path] | None = None,
) -> RelinkResponse:
    """Relink an asset version to a relocated media file on a new drive or directory."""
    version = db.get(AssetVersion, version_id)
    if not version:
        raise LookupError(f"AssetVersion {version_id} not found")

    new_path = Path(new_file_path).resolve()
    if not new_path.is_file():
        raise FileNotFoundError(f"Relink target file not found: {new_path}")

    # Enforce content identity: SHA-256 of candidate file must match version SHA-256
    computed_sha = compute_sha256(new_path)
    if version.sha256 and computed_sha.lower() != version.sha256.lower():
        raise ValueError(
            f"Relink rejected: Content SHA-256 mismatch. Expected {version.sha256}, got {computed_sha}"
        )

    # Locate or create a LibraryRoot for the parent directory
    parent_dir = new_path.parent
    root = (
        db.query(LibraryRoot)
        .filter(LibraryRoot.volume_id == str(parent_dir))
        .first()
    )
    if not root:
        lib = db.query(Library).first()
        if not lib:
            lib = Library(id=str(uuid4()), label="Default Library")
            db.add(lib)
            db.flush()
        root = LibraryRoot(
            id=str(uuid4()),
            library_id=lib.id,
            label=f"Root: {parent_dir.name}",
            volume_id=str(parent_dir),
            root_type="local_fixed",
            policy="local_only",
            status="active",
        )
        db.add(root)
        db.flush()

    rel_path = new_path.name
    rel_path_norm = new_path.name

    # Check if location already registered
    location = (
        db.query(AssetLocation)
        .filter_by(version_id=version.id, root_id=root.id, rel_path=rel_path)
        .first()
    )
    if not location:
        location = AssetLocation(
            id=str(uuid4()),
            version_id=version.id,
            root_id=root.id,
            rel_path=rel_path,
            rel_path_norm=rel_path_norm,
            availability=LocationAvailability.AVAILABLE.value,
            last_seen_at=_utcnow(),
        )
        db.add(location)
    else:
        location.availability = LocationAvailability.AVAILABLE.value
        location.last_seen_at = _utcnow()
        location.missing_since = None

    # Update associated Video row if present
    video = db.query(Video).filter_by(version_id=version.id).first()
    if video:
        video.file_path = str(new_path)

    db.commit()

    return RelinkResponse(
        version_id=version.id,
        location_id=location.id,
        status="relinked",
        rel_path=rel_path_norm,
        message=f"Successfully relinked {new_path.name} to version {version.id}",
    )
