from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.providers.transcription import FasterWhisperProvider, TranscriptionProvider
from app.models.entities import Transcript, TranscriptSegment, Video


def transcribe_and_store(
    db: Session,
    video: Video,
    audio_path: Path,
    provider: TranscriptionProvider | None = None,
) -> Transcript:
    active_provider = provider or FasterWhisperProvider()
    result = active_provider.transcribe(audio_path)

    # Clean existing transcripts for this video
    existing = db.query(Transcript).filter_by(video_id=video.id).all()
    for item in existing:
        db.delete(item)
    db.flush()

    transcript_id = str(uuid4())
    transcript = Transcript(
        id=transcript_id,
        video_id=video.id,
        language=result.language,
        model_name=result.model_name,
        full_text=result.full_text,
    )
    db.add(transcript)
    db.flush()

    for seg in result.segments:
        segment_row = TranscriptSegment(
            id=str(uuid4()),
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=seg.start_time,
            end_time=seg.end_time,
            text=seg.text,
            confidence=seg.confidence,
        )
        db.add(segment_row)

    db.commit()
    db.refresh(transcript)
    return transcript

