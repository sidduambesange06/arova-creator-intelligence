from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.enums import (
    ExecutionProfile,
    IdentityState,
    LocationAvailability,
    RootPolicy,
    RootType,
    StageStatus,
    TrustLevel,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Task 4 Core Data Model: Libraries, Roots, Assets, Versions, Locations
# ---------------------------------------------------------------------------


class Library(Base):
    __tablename__ = "libraries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_profile: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ExecutionProfile.FULLY_OFFLINE_NO_AI.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    roots: Mapped[list["LibraryRoot"]] = relationship(
        back_populates="library", cascade="all, delete-orphan"
    )


class LibraryRoot(Base):
    __tablename__ = "library_roots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    library_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("libraries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    root_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RootType.UNKNOWN.value,
    )
    volume_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    marker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    policy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RootPolicy.LOCAL_ONLY.value,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    library: Mapped["Library"] = relationship(back_populates="roots")
    locations: Mapped[list["AssetLocation"]] = relationship(
        back_populates="root", cascade="all, delete-orphan"
    )
    scan_runs: Mapped[list["ScanRun"]] = relationship(
        back_populates="root", cascade="all, delete-orphan"
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    current_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    versions: Mapped[list["AssetVersion"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        foreign_keys="AssetVersion.asset_id",
    )


class AssetVersion(Base):
    __tablename__ = "asset_versions"
    __table_args__ = (
        Index(
            "uq_asset_versions_sha256",
            "sha256",
            unique=True,
            sqlite_where=text("sha256 IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_meta: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    supersedes_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset_versions.id", ondelete="SET NULL"), nullable=True
    )
    identity_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=IdentityState.IDENTITY_UNVERIFIED.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    asset: Mapped["Asset"] = relationship(back_populates="versions", foreign_keys=[asset_id])
    locations: Mapped[list["AssetLocation"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    stage_runs: Mapped[list["StageRun"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    moments: Mapped[list["Moment"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class AssetLocation(Base):
    __tablename__ = "asset_locations"
    __table_args__ = (
        Index("uq_asset_locations_root_relpath", "root_id", "rel_path_norm", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    root_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("library_roots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rel_path: Mapped[str] = mapped_column(Text, nullable=False)
    rel_path_norm: Mapped[str] = mapped_column(Text, nullable=False)
    stat_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    availability: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=LocationAvailability.AVAILABLE.value,
    )
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped["AssetVersion"] = relationship(back_populates="locations")
    root: Mapped["LibraryRoot"] = relationship(back_populates="locations")


class StageRun(Base):
    __tablename__ = "stage_runs"
    __table_args__ = (
        UniqueConstraint("version_id", "stage", "fingerprint", name="uq_stage_runs_version_stage_fp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=StageStatus.PENDING.value)
    skip_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped["AssetVersion"] = relationship(back_populates="stage_runs")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    producer_stage: Mapped[str] = mapped_column(String(64), nullable=False)
    producer_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    producer_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trust: Mapped[str] = mapped_column(String(32), nullable=False, default=TrustLevel.UNVERIFIED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    version: Mapped["AssetVersion"] = relationship(back_populates="artifacts")


class Moment(Base):
    __tablename__ = "moments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("asset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="scene")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    version: Mapped["AssetVersion"] = relationship(back_populates="moments")


class Annotation(Base):
    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    author_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trust: Mapped[str] = mapped_column(String(32), nullable=False, default=TrustLevel.UNVERIFIED.value)
    ai_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AIConsent(Base):
    __tablename__ = "ai_consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_host: Mapped[str] = mapped_column(String(255), nullable=False)
    data_categories: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    capabilities: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    budget_limit: Mapped[float | None] = mapped_column(Float, nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    runs: Mapped[list["AIRun"]] = relationship(back_populates="consent")


class AIRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_location: Mapped[str] = mapped_column(String(32), nullable=False)
    data_categories: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_refs: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    consent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ai_consents.id", ondelete="SET NULL"), nullable=True
    )
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    consent: Mapped["AIConsent | None"] = relationship(back_populates="runs")


class IDAlias(Base):
    __tablename__ = "id_aliases"
    __table_args__ = (
        Index(
            "uq_id_aliases_export",
            "entity_type",
            "foreign_id",
            "source_export_id",
            unique=True,
            sqlite_where=text("source_export_id IS NOT NULL"),
        ),
        Index(
            "uq_id_aliases_local",
            "entity_type",
            "foreign_id",
            unique=True,
            sqlite_where=text("source_export_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    foreign_id: Mapped[str] = mapped_column(String(64), nullable=False)
    local_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_export_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class AssetRelation(Base):
    __tablename__ = "asset_relations"

    src_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    dst_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    root_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("library_roots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    counts: Mapped[str | None] = mapped_column(Text, nullable=True)

    root: Mapped["LibraryRoot"] = relationship(back_populates="scan_runs")


# ---------------------------------------------------------------------------
# Existing Models (Preserved intact for backward compatibility)
# ---------------------------------------------------------------------------


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    codec: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    format: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Bridge columns to Task 4 Asset model
    asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("asset_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    collections: Mapped[list["CollectionVideo"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    transcripts: Mapped[list["Transcript"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    scenes: Mapped[list["VideoScene"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list["EmbeddingRecord"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    summaries: Mapped[list["VideoSummary"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    videos: Mapped[list["CollectionVideo"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionVideo(Base):
    __tablename__ = "collection_videos"
    __table_args__ = (UniqueConstraint("collection_id", "video_id", name="uq_collection_video"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )

    collection: Mapped["Collection"] = relationship(back_populates="videos")
    video: Mapped["Video"] = relationship(back_populates="collections")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    video: Mapped["Video"] = relationship(back_populates="transcripts")
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="transcript", cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    transcript_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    transcript: Mapped["Transcript"] = relationship(back_populates="segments")


class VideoScene(Base):
    __tablename__ = "video_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    video: Mapped["Video"] = relationship(back_populates="scenes")


class EmbeddingRecord(Base):
    __tablename__ = "embedding_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    embedding_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    video: Mapped["Video"] = relationship(back_populates="embeddings")


class VideoSummary(Base):
    __tablename__ = "video_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    topics_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    chapters_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)

    video: Mapped["Video"] = relationship(back_populates="summaries")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default="full_pipeline")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    video: Mapped["Video"] = relationship(back_populates="jobs")
