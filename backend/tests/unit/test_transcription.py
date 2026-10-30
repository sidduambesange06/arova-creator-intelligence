from pathlib import Path
import wave

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.providers.transcription import (
    FasterWhisperProvider,
    SegmentResult,
    TranscriptionResult,
)
from app.database.session import Base, init_db
from app.models.entities import Transcript, TranscriptSegment, Video
from app.services.transcription_service import transcribe_and_store


class DummyProvider:
    def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(
            language="en",
            model_name="dummy-whisper-test",
            full_text="Welcome to the video intelligence demo.",
            segments=[
                SegmentResult(0.0, 2.5, "Welcome to the video", 0.98),
                SegmentResult(2.5, 5.0, "intelligence demo.", 0.95),
            ],
        )


def _make_dummy_wav(target: Path) -> Path:
    with wave.open(str(target), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 32000)  # 2.0s
    return target


def test_transcribe_and_store_db_persistence(tmp_path: Path) -> None:
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(test_engine)
    Session = sessionmaker(bind=test_engine)

    wav_file = _make_dummy_wav(tmp_path / "sample.wav")

    with Session() as db:
        video = Video(
            filename="demo.mp4",
            file_path="/tmp/demo.mp4",
            file_hash="hash987",
            duration=5.0,
        )
        db.add(video)
        db.commit()

        # 1. Transcribe with dummy provider
        transcript = transcribe_and_store(db, video, wav_file, provider=DummyProvider())
        assert transcript.video_id == video.id
        assert transcript.model_name == "dummy-whisper-test"
        assert len(transcript.segments) == 2
        assert transcript.segments[0].text == "Welcome to the video"

        # 2. Re-transcribe -> verifies old segments are replaced without orphan leaks
        updated = transcribe_and_store(db, video, wav_file, provider=DummyProvider())
        assert db.query(Transcript).filter_by(video_id=video.id).count() == 1
        assert db.query(TranscriptSegment).filter_by(video_id=video.id).count() == 2
        assert updated.id != transcript.id

    Base.metadata.drop_all(bind=test_engine)


def test_faster_whisper_provider_offline_fallback(tmp_path: Path) -> None:
    wav_file = _make_dummy_wav(tmp_path / "fallback.wav")
    provider = FasterWhisperProvider(model_size="base")
    res = provider.transcribe(wav_file, language="en")
    assert res.language == "en"
    assert len(res.segments) >= 1
    assert res.segments[0].start_time == 0.0
    assert res.segments[0].end_time > 0.0
    assert len(res.full_text) > 0
