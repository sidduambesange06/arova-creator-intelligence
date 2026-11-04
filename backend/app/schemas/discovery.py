"""Pydantic schemas for Library, LibraryRoot, Media Discovery, and Scan Runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExecutionProfile, LocationAvailability, RootPolicy, RootType


class LibraryCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=128)
    execution_profile: str = Field(
        default=ExecutionProfile.FULLY_OFFLINE_NO_AI.value,
        description="Execution profile: fully_offline_no_ai, local_ai, byok_remote_ai, hybrid_ai",
    )


class LibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    execution_profile: str
    created_at: datetime
    roots_count: int = 0


class LibraryRootCreateRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Filesystem directory path within allowed media roots")
    label: str | None = Field(default=None, max_length=128, description="Friendly label for root directory")
    root_type: str = Field(
        default=RootType.LOCAL_FIXED.value,
        description="Root type: local_fixed, local_removable, network_smb, network_nfs, cloud_mounted, unknown",
    )
    policy: str = Field(
        default=RootPolicy.LOCAL_ONLY.value,
        description="Root policy: local_only, allow_remote, quarantined",
    )


class LibraryRootPolicyUpdate(BaseModel):
    policy: str = Field(..., description="Root policy: local_only, allow_remote, quarantined")


class LibraryRootOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    library_id: str
    label: str
    root_type: str
    volume_id: str | None
    marker_id: str | None
    policy: str
    status: str
    last_scan_at: datetime | None
    locations_count: int = 0


class ScanRunCounts(BaseModel):
    scanned_files: int = 0
    discovered_media: int = 0
    new_assets: int = 0
    new_versions: int = 0
    new_locations: int = 0
    updated_locations: int = 0
    missing_locations: int = 0
    relocated_locations: int = 0
    errors: int = 0


class ScanRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    root_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    checkpoint: str | None = None
    counts: dict[str, Any] = Field(default_factory=dict)


class AssetLocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version_id: str
    root_id: str
    rel_path: str
    rel_path_norm: str
    stat_key: str | None
    last_seen_at: datetime
    availability: str
    missing_since: datetime | None


class AssetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    sha256: str | None
    size_bytes: int
    media_meta: str
    supersedes_version_id: str | None
    identity_state: str
    created_at: datetime
    locations: list[AssetLocationOut] = Field(default_factory=list)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    current_version_id: str | None
    created_at: datetime
    versions: list[AssetVersionOut] = Field(default_factory=list)
