from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


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
