"""Unit & API tests for M3.2 word-level transcript persistence and SRT/VTT/ASS subtitle export."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.providers.transcription import SegmentResult, TranscriptionResult
from app.database.session import get_db
from app.main import app
from app.models.entities import Base, Transcript, TranscriptSegment, Video
from app.processing.subtitles import (
    export_ass,
    export_srt,
    export_vtt,
    normalize_word_timings,
    parse_subtitles,
)
from app.schemas.pipeline import TranscriptSegmentOut
from app.services.transcription_service import transcribe_and_store


def test_normalize_word_timings_bounds_finite_monotonic_and_unicode():
    raw_words = [
        {"word": "  नमस्ते ", "start": -0.2, "end": 0.4567, "probability": 0.91},
        {"word": "గేమ్స్\u200cలో", "start": 0.40, "end": 0.90, "probability": 0.88},  # overlaps previous end
        {"word": "bad_nan", "start": float("nan"), "end": 1.0},
        {"word": "bad_inf", "start": 1.0, "end": float("inf")},
        {"word": "inverted", "start": 1.8, "end": 1.2},
        {"word": "tail", "start": 2.5, "end": 3.5, "probability": 0.75},
    ]
    normalized = normalize_word_timings(raw_words, media_duration=3.0)
    assert normalized is not None
    # NaN and Inf dropped; inverted clamped so end >= start; negative start clamped to 0.0; tail clamped to 3.0
    words_text = [w["word"] for w in normalized]
    assert words_text == ["नमस्ते", "గేమ్స్\u200cలో", "inverted", "tail"]
    assert "\u200c" in normalized[1]["word"]  # ZWNJ preserved

    for w in normalized:
        assert 0.0 <= w["start"] <= w["end"] <= 3.0
    # Monotonic non-decreasing start policy
    for prev, curr in zip(normalized, normalized[1:]):
        assert curr["start"] >= prev["start"]


def test_export_srt_and_vtt_deterministic_rounding_and_roundtrip():
    segments = [
        {"start_time": 0.0, "end_time": 1.25, "text": "Hello {world} \\ test"},
        {"start_time": 59.9999, "end_time": 61.5, "text": "ज़िंदगी और प्रौद्योगिकी"},
    ]
    srt = export_srt(segments)
    assert "00:00:00,000 --> 00:00:01,250" in srt
    assert "00:01:00,000 --> 00:01:01,500" in srt  # rollover-safe rounding (no 00:00:60,000)
    assert "ज़िंदगी और प्रौद्योगिकी" in srt

    reparsed_srt = parse_subtitles(srt, "out.srt")
    assert len(reparsed_srt) == 2
    assert reparsed_srt[1].start_time == 60.0
    assert reparsed_srt[1].text == "ज़िंदगी और प्रौद्योगिकी"

    vtt = export_vtt(segments)
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:01:00.000 --> 00:01:01.500" in vtt
    reparsed_vtt = parse_subtitles(vtt, "out.vtt")
    assert len(reparsed_vtt) == 2
    assert reparsed_vtt[1].text == "ज़िंदगी और प्रौद्योगिकी"


def test_export_ass_valid_structure_escaping_and_karaoke():
    segments = [
        {
            "start_time": 0.0,
            "end_time": 2.0,
            "text": "Line 1 {\\b1}injected\nLine 2 \\ slash",
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": "{tag}", "start": 0.5, "end": 1.2},
            ],
        },
        {
            "start_time": 59.996,
            "end_time": 61.0,
            "text": "தமிழ் சென்னை",
        },
    ]
    ass = export_ass(segments, title="M3 Test")
    assert "[Script Info]" in ass
    assert "[V4+ Styles]" in ass
    assert "[Events]" in ass
    # Escaped override braces & backslash + newline -> \N
    assert r"Line 1 \{\\b1\}injected\NLine 2 \\ slash" in ass
    # Centisecond rollover-safe timestamp (59.996 -> 0:01:00.00)
    assert "Dialogue: 0,0:01:00.00,0:01:01.00,Default,,0,0,0,,தமிழ் சென்னை" in ass

    ass_karaoke = export_ass(segments, include_karaoke=True)
    assert r"{\k50}Hello {\k70}\{tag\}" in ass_karaoke


class _FakeWordProvider:
    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_path: Path, **kwargs) -> TranscriptionResult:
        return TranscriptionResult(
            language="hi",
            model_name="faster-whisper-small",
            full_text="नमस्ते भारत",
            segments=[
                SegmentResult(
                    start_time=0.0,
                    end_time=1.5,
                    text="नमस्ते भारत",
                    confidence=-0.15,
                    words=[
                        {"word": "नमस्ते", "start": 0.0, "end": 0.7, "probability": 0.95},
                        {"word": "भारत", "start": 0.75, "end": 1.6, "probability": 0.92},  # slightly past duration 1.5
                    ],
                )
            ],
        )


def test_word_timings_persistence_backward_compat_and_export_api(tmp_path: Path):
    db_path = tmp_path / "m3_subtitles.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    try:
        video = Video(
            id=str(uuid4()),
            filename="sample_hi.mp4",
            file_path=str(tmp_path / "sample_hi.mp4"),
            file_hash="a" * 64,
            duration=1.5,
        )
        db.add(video)
        db.commit()

        dummy_audio = tmp_path / "audio.wav"
        dummy_audio.write_bytes(b"RIFF")

        tx = transcribe_and_store(db, video, dummy_audio, provider=_FakeWordProvider())
        assert tx is not None
        assert len(tx.segments) == 1
        seg = tx.segments[0]
        assert seg.timing_source == "asr_estimated"
        assert seg.words is not None
        assert len(seg.words) == 2
        assert seg.words[1]["end"] == 1.5  # clamped to video.duration

        # Backward compatibility: legacy segment with no words_json still validates
        legacy_seg = TranscriptSegment(
            id=str(uuid4()),
            transcript_id=tx.id,
            video_id=video.id,
            start_time=1.5,
            end_time=2.0,
            text="Legacy line",
            confidence=0.9,
        )
        out_legacy = TranscriptSegmentOut.model_validate(legacy_seg)
        assert out_legacy.words is None
        assert out_legacy.timing_source is None

        # Test REST API export endpoints
        def _override_get_db():
            s = SessionLocal()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override_get_db
        try:
            client = TestClient(app)
            r_tx = client.get(f"/api/v1/videos/{video.id}/transcript")
            assert r_tx.status_code == 200
            tx_payload = r_tx.json()
            assert tx_payload["segments"][0]["timing_source"] == "asr_estimated"
            assert len(tx_payload["segments"][0]["words"]) == 2

            r_srt = client.get(f"/api/v1/videos/{video.id}/subtitles/export?format=srt")
            assert r_srt.status_code == 200
            assert "नमस्ते भारत" in r_srt.text

            r_vtt = client.get(f"/api/v1/videos/{video.id}/subtitles/export?format=vtt")
            assert r_vtt.status_code == 200
            assert r_vtt.text.startswith("WEBVTT\n\n")

            r_ass = client.get(f"/api/v1/videos/{video.id}/subtitles/export?format=ass&karaoke=true")
            assert r_ass.status_code == 200
            assert "[Events]" in r_ass.text
            assert r"{\k70}नमस्ते" in r_ass.text

            r_bad = client.get(f"/api/v1/videos/{video.id}/subtitles/export?format=invalid")
            assert r_bad.status_code == 400
        finally:
            app.dependency_overrides.pop(get_db, None)
    finally:
        db.close()
        engine.dispose()
