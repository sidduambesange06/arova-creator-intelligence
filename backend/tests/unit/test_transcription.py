from pathlib import Path
import wave
import pytest

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


class EmptySpeechProvider:
    def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        return TranscriptionResult(
            language="en",
            model_name="empty-provider-test",
            full_text="",
            segments=[],
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
        assert transcript is not None
        assert transcript.video_id == video.id
        assert transcript.model_name == "dummy-whisper-test"
        assert len(transcript.segments) == 2
        assert transcript.segments[0].text == "Welcome to the video"
        assert transcript.segments[0].confidence == 0.98

        # 2. Re-transcribe -> verifies old segments are replaced without orphan leaks
        updated = transcribe_and_store(db, video, wav_file, provider=DummyProvider())
        assert updated is not None
        assert db.query(Transcript).filter_by(video_id=video.id).count() == 1
        assert db.query(TranscriptSegment).filter_by(video_id=video.id).count() == 2
        assert updated.id != transcript.id

        # 3. Transcribe with empty speech provider -> returns None, stores no empty records
        empty_res = transcribe_and_store(db, video, wav_file, provider=EmptySpeechProvider())
        assert empty_res is None

    Base.metadata.drop_all(bind=test_engine)


def test_faster_whisper_provider_offline_raises_runtime_error_no_fake_segments(tmp_path: Path) -> None:
    wav_file = _make_dummy_wav(tmp_path / "fallback.wav")
    provider = FasterWhisperProvider(model_size_or_path="nonexistent_local_model_xyz")

    # When faster_whisper weights are unavailable, provider must report unavailable
    # and strictly refuse to synthesize fake speech segments or false confidence scores.
    assert provider.is_available() is False
    with pytest.raises(RuntimeError, match=r"(?:model_not_installed|dependency_missing)"):
        provider.transcribe(wav_file, language="en")


def test_zero_fake_output_regression(tmp_path: Path) -> None:
    # Regression test: verifies that no part of the transcription provider or service
    # emits fake '[Speech Segment N]' or fabricated 0.95 confidence
    provider = FasterWhisperProvider(model_size_or_path="uninstalled_model")
    wav_file = _make_dummy_wav(tmp_path / "test.wav")
    try:
        res = provider.transcribe(wav_file)
        for seg in res.segments:
            assert "[Speech Segment" not in seg.text
            assert seg.confidence != 0.95
    except RuntimeError as exc:
        assert "model_not_installed" in str(exc) or "dependency_missing" in str(exc)
