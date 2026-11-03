from typing import Any
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.retrieval.hybrid_search import (
    HybridSearchResponse,
    SearchResultItem,
    run_hybrid_search,
)
from app.core.config import settings
from app.database.session import get_db
from app.models.entities import TranscriptSegment, Video
from app.services.summary_service import (
    answer_video_question,
    find_video_clips,
    generate_video_summary,
)

router = APIRouter(prefix="/api/v1", tags=["search-and-ai"])


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


class ClipSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    min_duration: float = Field(default=5.0, ge=1.0)
    max_duration: float = Field(default=60.0, le=300.0)
    top_k: int = Field(default=5, ge=1, le=20)
    video_id: str | None = None


class ClipResultItem(BaseModel):
    video_id: str
    filename: str
    start_time: float
    end_time: float
    duration: float
    transcript_snippet: str
    relevance_score: float
    rationale: str


class SummarizeRequest(BaseModel):
    video_id: str
    api_key: str | None = None
    consent_remote_ai: bool = False


class SummarizeResponse(BaseModel):
    video_id: str
    summary: str
    topics: list[str]
    chapters: list[dict[str, Any]]
    model_name: str
    remote_egress: bool = False
    provider: str = "local"
    egress_data_categories: list[str] = []
    consent_source: str | None = None


@router.post("/search/semantic", response_model=HybridSearchResponse)
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


@router.post("/search/transcripts", response_model=list[TranscriptSearchResult])
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


@router.post("/search/clips", response_model=list[ClipResultItem])
def search_clips(
    payload: ClipSearchRequest,
    db: Session = Depends(get_db),
) -> list[ClipResultItem]:
    clips = find_video_clips(
        db=db,
        query=payload.query,
        min_duration=payload.min_duration,
        max_duration=payload.max_duration,
        top_k=payload.top_k,
        video_id=payload.video_id,
    )
    return [ClipResultItem(**c) for c in clips]


@router.post("/ai/summarize", response_model=SummarizeResponse)
def summarize_video(
    payload: SummarizeRequest,
    db: Session = Depends(get_db),
) -> SummarizeResponse:
    try:
        summary_obj = generate_video_summary(
            db=db,
            video_id=payload.video_id,
            api_key=payload.api_key,
            consent_remote_ai=payload.consent_remote_ai,
        )
        is_remote = summary_obj.model_name.startswith("gemini")
        has_consent = payload.consent_remote_ai or settings.AI_REMOTE_CONSENT
        consent_source = "request" if payload.consent_remote_ai else ("admin_setting" if settings.AI_REMOTE_CONSENT else None)
        return SummarizeResponse(
            video_id=summary_obj.video_id,
            summary=summary_obj.summary_text,
            topics=json.loads(summary_obj.topics_json),
            chapters=json.loads(summary_obj.chapters_json),
            model_name=summary_obj.model_name,
            remote_egress=is_remote,
            provider="google-gemini" if is_remote else "local",
            egress_data_categories=["video_full_transcript"] if is_remote else [],
            consent_source=consent_source if is_remote else None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class AskQuestionRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Question about video content")
    video_id: str | None = Field(default=None, description="Optional video ID filter")
    api_key: str | None = None
    consent_remote_ai: bool = False


@router.post("/ai/ask")
def ask_video_ai(
    payload: AskQuestionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return answer_video_question(
        db=db,
        query=payload.query,
        video_id=payload.video_id,
        api_key=payload.api_key,
        consent_remote_ai=payload.consent_remote_ai,
    )


