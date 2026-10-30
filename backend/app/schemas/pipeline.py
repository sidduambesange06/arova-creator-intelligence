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
