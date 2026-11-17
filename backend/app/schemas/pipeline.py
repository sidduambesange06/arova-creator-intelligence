from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class TranscriptSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    start_time: float
    end_time: float
    text: str
    confidence: float


class TranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    language: str
    model_name: str
    full_text: str
    segments: list[TranscriptSegmentOut] = Field(default_factory=list)


class VideoSceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    scene_index: int
    start_time: float
    end_time: float
    thumbnail_path: str | None


class ProcessingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    job_type: str
    status: str
    progress: float
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class StageRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_id: str
    stage: str
    fingerprint: str
    status: str
    skip_reason: str | None = None
    attempt: int
    lease_until: datetime | None = None
    heartbeat_at: datetime | None = None
    error_code: str | None = None
    error_detail: str | None = None
    output_ref: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_id: str
    kind: str
    producer_stage: str
    producer_model: str | None = None
    producer_revision: str | None = None
    config_hash: str | None = None
    is_current: bool
    trust: str
    created_at: datetime


