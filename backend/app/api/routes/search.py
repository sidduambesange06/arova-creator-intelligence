from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.retrieval.hybrid_search import (
    HybridSearchResponse,
    SearchResultItem,
    run_hybrid_search,
)
from app.database.session import get_db
from app.models.entities import TranscriptSegment, Video

router = APIRouter(prefix="/api/v1/search", tags=["search"])


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=10, ge=1, le=50)
    use_reranker: bool = Field(default=True, description="Enable Stage-2 Cross-Encoder ML re-ranking")
    video_id: str | None = Field(default=None, description="Optional video ID filter")


class TranscriptSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    video_id: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class TranscriptSearchResult(BaseModel):
    id: str
    video_id: str
    filename: str
    start_time: float
    end_time: float
    text: str
    confidence: float


@router.post("/semantic", response_model=HybridSearchResponse)
def search_semantic(
    payload: SemanticSearchRequest,
    db: Session = Depends(get_db),
) -> HybridSearchResponse:
    return run_hybrid_search(
        db=db,
        query=payload.query,
        top_k=payload.top_k,
        use_reranker=payload.use_reranker,
        video_id_filter=payload.video_id,
    )


@router.post("/transcripts", response_model=list[TranscriptSearchResult])
def search_transcripts(
    payload: TranscriptSearchRequest,
    db: Session = Depends(get_db),
) -> list[TranscriptSearchResult]:
    query = (
        db.query(TranscriptSegment, Video.filename)
        .join(Video, Video.id == TranscriptSegment.video_id)
        .filter(TranscriptSegment.text.ilike(f"%{payload.query.strip()}%"))
    )
    if payload.video_id:
        query = query.filter(TranscriptSegment.video_id == payload.video_id)

    rows = query.order_by(TranscriptSegment.start_time.asc()).limit(payload.limit).all()

    return [
        TranscriptSearchResult(
            id=seg.id,
            video_id=seg.video_id,
            filename=filename,
            start_time=seg.start_time,
            end_time=seg.end_time,
            text=seg.text,
            confidence=seg.confidence,
        )
        for seg, filename in rows
    ]
