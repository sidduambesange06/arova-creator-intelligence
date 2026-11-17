"""REST API router for Library, Media Roots, Discovery, and Scan Runs."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.database.session import get_db
from app.models.entities import Asset, AssetLocation, AssetVersion, Library, LibraryRoot, ScanRun
from app.schemas.discovery import (
    AssetLocationOut,
    AssetOut,
    AssetVersionOut,
    LibraryCreateRequest,
    LibraryOut,
    LibraryRootCreateRequest,
    LibraryRootOut,
    LibraryRootPolicyUpdate,
    ScanRunOut,
)
from app.services import discovery_service

router = APIRouter(prefix="/api/v1/libraries", tags=["discovery"])


@router.post("", response_model=LibraryOut, status_code=status.HTTP_201_CREATED)
def create_library_endpoint(
    payload: LibraryCreateRequest,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> LibraryOut:
    lib = discovery_service.create_or_get_library(
        db=db,
        label=payload.label,
        execution_profile=payload.execution_profile,
    )
    return LibraryOut(
        id=lib.id,
        label=lib.label,
        execution_profile=lib.execution_profile,
        created_at=lib.created_at,
        roots_count=len(lib.roots),
    )


@router.get("", response_model=list[LibraryOut])
def list_libraries_endpoint(
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> list[LibraryOut]:
    libs = db.query(Library).all()
    return [
        LibraryOut(
            id=lib.id,
            label=lib.label,
            execution_profile=lib.execution_profile,
            created_at=lib.created_at,
            roots_count=len(lib.roots),
        )
        for lib in libs
    ]


@router.post("/{library_id}/roots", response_model=LibraryRootOut, status_code=status.HTTP_201_CREATED)
def register_root_endpoint(
    library_id: str,
    payload: LibraryRootCreateRequest,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> LibraryRootOut:
    try:
        root = discovery_service.register_library_root(
            db=db,
            library_id=library_id,
            path=payload.path,
            label=payload.label,
            root_type=payload.root_type,
            policy=payload.policy,
        )
        return LibraryRootOut(
            id=root.id,
            library_id=root.library_id,
            label=root.label,
            root_type=root.root_type,
            volume_id=root.volume_id,
            marker_id=root.marker_id,
            policy=root.policy,
            status=root.status,
            last_scan_at=root.last_scan_at,
            locations_count=len(root.locations),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{library_id}/roots", response_model=list[LibraryRootOut])
def list_library_roots_endpoint(
    library_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> list[LibraryRootOut]:
    roots = discovery_service.list_library_roots(db=db, library_id=library_id)
    return [
        LibraryRootOut(
            id=r.id,
            library_id=r.library_id,
            label=r.label,
            root_type=r.root_type,
            volume_id=r.volume_id,
            marker_id=r.marker_id,
            policy=r.policy,
            status=r.status,
            last_scan_at=r.last_scan_at,
            locations_count=len(r.locations),
        )
        for r in roots
    ]


@router.get("/roots/{root_id}", response_model=LibraryRootOut)
def get_root_endpoint(
    root_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> LibraryRootOut:
    root = discovery_service.get_library_root(db=db, root_id=root_id)
    if not root:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Root not found: {root_id}")
    return LibraryRootOut(
        id=root.id,
        library_id=root.library_id,
        label=root.label,
        root_type=root.root_type,
        volume_id=root.volume_id,
        marker_id=root.marker_id,
        policy=root.policy,
        status=root.status,
        last_scan_at=root.last_scan_at,
        locations_count=len(root.locations),
    )


@router.patch("/roots/{root_id}/policy", response_model=LibraryRootOut)
def update_root_policy_endpoint(
    root_id: str,
    payload: LibraryRootPolicyUpdate,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> LibraryRootOut:
    try:
        root = discovery_service.update_library_root_policy(db=db, root_id=root_id, policy=payload.policy)
        return LibraryRootOut(
            id=root.id,
            library_id=root.library_id,
            label=root.label,
            root_type=root.root_type,
            volume_id=root.volume_id,
            marker_id=root.marker_id,
            policy=root.policy,
            status=root.status,
            last_scan_at=root.last_scan_at,
            locations_count=len(root.locations),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/roots/{root_id}/scan", response_model=ScanRunOut)
def trigger_root_scan_endpoint(
    root_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> ScanRunOut:
    try:
        scan_run = discovery_service.run_root_media_scan(db=db, root_id=root_id)
        counts = json.loads(scan_run.counts) if scan_run.counts else {}
        return ScanRunOut(
            id=scan_run.id,
            root_id=scan_run.root_id,
            status=scan_run.status,
            started_at=scan_run.started_at,
            finished_at=scan_run.finished_at,
            checkpoint=scan_run.checkpoint,
            counts=counts,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/roots/{root_id}/scans", response_model=list[ScanRunOut])
def list_root_scans_endpoint(
    root_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> list[ScanRunOut]:
    runs = discovery_service.list_scan_runs_for_root(db=db, root_id=root_id)
    results = []
    for r in runs:
        counts = json.loads(r.counts) if r.counts else {}
        results.append(
            ScanRunOut(
                id=r.id,
                root_id=r.root_id,
                status=r.status,
                started_at=r.started_at,
                finished_at=r.finished_at,
                checkpoint=r.checkpoint,
                counts=counts,
            )
        )
    return results


@router.get("/scans/{scan_id}", response_model=ScanRunOut)
def get_scan_endpoint(
    scan_id: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> ScanRunOut:
    run = discovery_service.get_scan_run(db=db, scan_id=scan_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ScanRun not found: {scan_id}")
    counts = json.loads(run.counts) if run.counts else {}
    return ScanRunOut(
        id=run.id,
        root_id=run.root_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        checkpoint=run.checkpoint,
        counts=counts,
    )


@router.get("/{library_id}/assets", response_model=list[AssetOut])
def list_library_assets_endpoint(
    library_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_auth),
) -> list[AssetOut]:
    assets, _ = discovery_service.list_library_assets(
        db=db, library_id=library_id, limit=limit, offset=offset
    )
    results = []
    for a in assets:
        versions_out = []
        for v in a.versions:
            locations_out = [
                AssetLocationOut(
                    id=loc.id,
                    version_id=loc.version_id,
                    root_id=loc.root_id,
                    rel_path=loc.rel_path,
                    rel_path_norm=loc.rel_path_norm,
                    stat_key=loc.stat_key,
                    last_seen_at=loc.last_seen_at,
                    availability=loc.availability,
                    missing_since=loc.missing_since,
                )
                for loc in v.locations
            ]
            versions_out.append(
                AssetVersionOut(
                    id=v.id,
                    asset_id=v.asset_id,
                    sha256=v.sha256,
                    size_bytes=v.size_bytes,
                    media_meta=v.media_meta,
                    supersedes_version_id=v.supersedes_version_id,
                    identity_state=v.identity_state,
                    created_at=v.created_at,
                    locations=locations_out,
                )
            )
        results.append(
            AssetOut(
                id=a.id,
                current_version_id=a.current_version_id,
                created_at=a.created_at,
                versions=versions_out,
            )
        )
    return results
