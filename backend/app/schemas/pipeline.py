from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class WordTimingOut(BaseModel):
    word: str
    start: float
    end: float
    probability: float | None = None


class TranscriptSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    start_time: float
    end_time: float
    text: str
    confidence: float
    words: list[WordTimingOut] | None = None
    timing_source: str | None = None


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


class OcrFrameEvidenceOut(BaseModel):
    scene_index: int
    timestamp_sec: float
    text: str
    thumbnail_path: str | None = None


class VideoOcrStatusOut(BaseModel):
    video_id: str
    version_id: str | None = None
    status: str  # engine_unavailable | not_processed | running | completed_no_text | completed_with_text | failed
    engine_available: bool
    engine_name: str | None = None
    engine_version: str | None = None
    stage_status: str | None = None
    skip_reason: str | None = None
    error_message: str | None = None
    extracted_count: int = 0
    frames: list[OcrFrameEvidenceOut] = Field(default_factory=list)
    remediation_hint: str | None = None


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


