from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.providers.embeddings import index_video_chunks
from app.models.entities import Transcript, TranscriptSegment, Video
from app.processing.subtitles import parse_subtitles


def ingest_subtitles_for_video(
    db: Session,
    video: Video,
    content: str,
    source_name: str = "subtitles",
    language: str = "en",
    media_storage_dir: Path | None = None,
) -> Transcript:
    """Parse and store subtitle cues as video transcripts, then refresh hybrid RAG index."""
    cues = parse_subtitles(content, filename_hint=source_name)
    if not cues:
        raise ValueError(f"No valid subtitle cues parsed from {source_name}")

    # Clean existing transcripts for this video
    existing = db.query(Transcript).filter_by(video_id=video.id).all()
    for item in existing:
        db.delete(item)
    db.flush()

    full_text = " ".join(cue.text for cue in cues)
    transcript_id = str(uuid4())
    transcript = Transcript(
        id=transcript_id,
        video_id=video.id,
        language=language,
        model_name=f"subtitles:{source_name}",
        full_text=full_text,
    )
    db.add(transcript)
    db.flush()

    for cue in cues:
        segment_row = TranscriptSegment(
            id=str(uuid4()),
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=cue.start_time,
            end_time=cue.end_time,
            text=cue.text,
            confidence=1.0,
        )
        db.add(segment_row)

    db.commit()
    db.refresh(transcript)

    # Refresh timestamp windows and hybrid search index
    index_video_chunks(
        db=db,
        video_id=video.id,
        storage_dir=media_storage_dir,
    )

    return transcript
