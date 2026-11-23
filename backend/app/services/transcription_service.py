import inspect
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.providers.transcription import FasterWhisperProvider, TranscriptionProvider
from app.models.entities import Transcript, TranscriptSegment, Video
from app.processing.subtitles import normalize_word_timings


def transcribe_and_store(
    db: Session,
    video: Video,
    audio_path: Path,
    provider: TranscriptionProvider | None = None,
    *,
    language: str | None = None,
    beam_size: int | None = None,
    vad_filter: bool | None = None,
    word_timestamps: bool | None = None,
    condition_on_previous_text: bool | None = None,
) -> Transcript | None:
    """Run ASR provider on audio and persist genuine transcript and segment records.

    Returns:
        Transcript instance if speech segments were transcribed, None if no speech detected.
    """
    active_provider = provider or FasterWhisperProvider()
    call_kwargs: dict[str, object] = {}
    if language is not None:
        call_kwargs["language"] = language
    if beam_size is not None:
        call_kwargs["beam_size"] = beam_size
    if vad_filter is not None:
        call_kwargs["vad_filter"] = vad_filter
    if word_timestamps is not None:
        call_kwargs["word_timestamps"] = word_timestamps
    if condition_on_previous_text is not None:
        call_kwargs["condition_on_previous_text"] = condition_on_previous_text

    if call_kwargs:
        sig = inspect.signature(active_provider.transcribe)
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if not accepts_var_kw:
            call_kwargs = {k: v for k, v in call_kwargs.items() if k in sig.parameters}
        result = active_provider.transcribe(audio_path, **call_kwargs)
    else:
        result = active_provider.transcribe(audio_path)

    if not result or not result.segments or not result.full_text.strip():
        return None

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
        norm_words = normalize_word_timings(seg.words, media_duration=video.duration)
        segment_row = TranscriptSegment(
            id=str(uuid4()),
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=seg.start_time,
            end_time=seg.end_time,
            text=seg.text,
            confidence=seg.confidence,
            words_json=json.dumps(norm_words, ensure_ascii=False) if norm_words else None,
            timing_source="asr_estimated" if norm_words else None,
        )
        db.add(segment_row)

    db.commit()
    db.refresh(transcript)
    return transcript
