"""Pydantic schemas for Task 4D: Portable Media Memory, Archive Export/Import, Annotations, and Availability."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ArchiveEntryManifest(BaseModel):
    name: str
    sha256: str
    size_bytes: int


class ArchiveManifest(BaseModel):
    format_version: str = "1.0.0"
    export_id: str
    created_at: datetime
    generator: str = "Arova Creator Intelligence"
    library_id: str | None = None
    records_count: dict[str, int] = Field(default_factory=dict)
    entries: list[ArchiveEntryManifest] = Field(default_factory=list)


class ExportRequest(BaseModel):
    library_id: str | None = None
    asset_ids: list[str] | None = None
    include_artifacts: bool = True


class ExportSummary(BaseModel):
    export_id: str
    format_version: str = "1.0.0"
    created_at: datetime
    archive_name: str
    file_size_bytes: int
    sha256: str
    records_count: dict[str, int] = Field(default_factory=dict)


class ImportDryRunReport(BaseModel):
    valid: bool
    format_version: str
    export_id: str
    total_entries: int
    records_to_import: dict[str, int] = Field(default_factory=dict)
    matching_existing_records: dict[str, int] = Field(default_factory=dict)
    duplicate_conflicts: int = 0
    proposed_id_remappings: int = 0
    estimated_size_bytes: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ImportResult(BaseModel):
    status: str  # "success" | "dry_run" | "rejected"
    export_id: str
    imported_counts: dict[str, int] = Field(default_factory=dict)
    remapped_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AnnotationCreate(BaseModel):
    target_type: str = Field(description="Target entity: 'version', 'moment', or 'asset'")
    target_id: str = Field(description="UUID of the target entity")
    author_type: str = Field(default="human", description="'human', 'ai', or 'asr'")
    display_name: str = Field(description="Display name or label for the annotation")
    trust: str = Field(default="human_confirmed", description="Trust level")
    body: str = Field(description="Annotation body / comment content")
    ai_run_id: str | None = None


class AnnotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_type: str
    target_id: str
    author_type: str
    display_name: str
    trust: str
    ai_run_id: str | None = None
    body: str
    created_at: datetime


class MediaAvailabilityOut(BaseModel):
    version_id: str
    video_id: str | None = None
    availability: str  # "available" | "unavailable" | "missing" | "relink_required"
    can_play: bool
    can_export: bool
    file_path: str | None = None
    root_type: str | None = None
    last_seen_at: datetime | None = None


class DuplicateLocationItem(BaseModel):
    location_id: str
    root_id: str
    rel_path: str
    availability: str
    last_seen_at: datetime | None = None


class DuplicateGroupOut(BaseModel):
    sha256: str
    version_id: str
    size_bytes: int
    locations_count: int
    locations: list[DuplicateLocationItem] = Field(default_factory=list)


class RelinkRequest(BaseModel):
    version_id: str
    new_file_path: str


class RelinkResponse(BaseModel):
    version_id: str
    location_id: str
    status: str
    rel_path: str
    message: str

