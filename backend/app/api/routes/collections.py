from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.media import (
    CollectionCreateRequest,
    CollectionOut,
    CollectionVideoAddRequest,
)
from app.services import media_service

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection_endpoint(
    payload: CollectionCreateRequest,
    db: Session = Depends(get_db),
) -> CollectionOut:
    try:
        return media_service.create_collection(
            db=db,
            name=payload.name,
            description=payload.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[CollectionOut])
def list_collections_endpoint(db: Session = Depends(get_db)) -> list[CollectionOut]:
    return media_service.list_collections(db=db)


@router.post("/{collection_id}/videos", response_model=CollectionOut)
def add_video_to_collection_endpoint(
    collection_id: str,
    payload: CollectionVideoAddRequest,
    db: Session = Depends(get_db),
) -> CollectionOut:
    try:
        return media_service.add_video_to_collection(
            db=db,
            collection_id=collection_id,
            video_id=payload.video_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
