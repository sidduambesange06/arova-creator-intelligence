from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class VideoImportRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Local file or directory path within allowed roots")
    collection_id: str | None = None


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    file_path: str
    file_hash: str
    file_size: int
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    format: str
    thumbnail_path: str | None
    processing_status: str
    created_at: datetime
    collection_ids: list[str] = Field(default_factory=list)


class VideoImportResponse(BaseModel):
    imported: list[VideoOut]
    skipped_duplicates: int


class CollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None


class CollectionVideoAddRequest(BaseModel):
    video_id: str


class CollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    created_at: datetime
    video_count: int = 0


class ClipExportRequest(BaseModel):
    start_time: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end_time: float = Field(..., gt=0.0, description="End timestamp in seconds")


class ClipExportResponse(BaseModel):
    video_id: str
    clip_filename: str
    start_time: float
    end_time: float
    duration: float
    file_size: int
    download_url: str


