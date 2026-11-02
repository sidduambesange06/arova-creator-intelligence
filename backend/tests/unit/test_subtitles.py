from pathlib import Path
import pytest

from app.processing.subtitles import (
    ParsedSubtitleCue,
    find_sidecar_subtitles,
    parse_subtitle_timestamp,
    parse_subtitles,
)


def test_parse_subtitle_timestamp_formats() -> None:
    # Standard SRT format (comma)
    assert parse_subtitle_timestamp("00:01:23,456") == 83.456
    # Standard WebVTT format (dot)
    assert parse_subtitle_timestamp("00:01:23.456") == 83.456
    # MM:SS format
    assert parse_subtitle_timestamp("02:15.500") == 135.5
    assert parse_subtitle_timestamp("00:05,200") == 5.2
    # Fractional precision
    assert parse_subtitle_timestamp("00:00:01.5") == 1.5
    assert parse_subtitle_timestamp("00:00:00.000") == 0.0

    # Invalid timestamp errors
    with pytest.raises(ValueError):
        parse_subtitle_timestamp("invalid")
    with pytest.raises(ValueError):
        parse_subtitle_timestamp("-00:01:00.000")
    with pytest.raises(ValueError):
        parse_subtitle_timestamp("01:02:03:04")


def test_parse_srt_format() -> None:
    raw_srt = """1
00:00:01,000 --> 00:00:03,500
Hello <i>world</i>!
This is line two.

2
00:00:04,200 --> 00:00:07,000
Second cue with <font color="#ff0000">colored</font> text.
"""
    cues = parse_subtitles(raw_srt, filename_hint="sample.srt")
    assert len(cues) == 2
    assert cues[0] == ParsedSubtitleCue(
        start_time=1.0,
        end_time=3.5,
        text="Hello world! This is line two.",
    )
    assert cues[1] == ParsedSubtitleCue(
        start_time=4.2,
        end_time=7.0,
        text="Second cue with colored text.",
    )


def test_parse_webvtt_format() -> None:
    raw_vtt = """WEBVTT - Demonstration File
Kind: captions
Language: en

NOTE
This is an introductory comment block
that should be skipped by parser.

cue-identifier-1
00:00:01.500 --> 00:00:04.000 position:20% align:start
<v Narrator>Welcome to the <c.yellow>Arova</c> tutorial.</v>

00:05.000 --> 00:08.500 line:0
Discover media locally with zero cloud upload.
"""
    cues = parse_subtitles(raw_vtt, filename_hint="sample.vtt")
    assert len(cues) == 2
    assert cues[0] == ParsedSubtitleCue(
        start_time=1.5,
        end_time=4.0,
        text="Welcome to the Arova tutorial.",
    )
    assert cues[1] == ParsedSubtitleCue(
        start_time=5.0,
        end_time=8.5,
        text="Discover media locally with zero cloud upload.",
    )


def test_parse_subtitles_unicode_and_bom() -> None:
    raw_content = "\ufeff1\r\n00:00:00,500 --> 00:00:03,000\r\nನಮಸ್ಕಾರ ಸ್ನೇಹಿತರೆ (Hello friends)\r\n\r\n2\r\n00:00:03,500 --> 00:00:06,000\r\nनमस्ते दुनिया\r\n"
    cues = parse_subtitles(raw_content)
    assert len(cues) == 2
    assert cues[0].text == "ನಮಸ್ಕಾರ ಸ್ನೇಹಿತರೆ (Hello friends)"
    assert cues[1].text == "नमस्ते दुनिया"


def test_parse_subtitles_inverted_timestamps_and_empty() -> None:
    # Inverted timestamps are discarded
    raw_invalid = """1
00:00:10,000 --> 00:00:05,000
Invalid interval

2
00:00:12,000 --> 00:00:15,000
Valid interval
"""
    cues = parse_subtitles(raw_invalid)
    assert len(cues) == 1
    assert cues[0].text == "Valid interval"

    # Empty content
    assert parse_subtitles("") == []
    assert parse_subtitles("   \n\n  ") == []


def test_find_sidecar_subtitles(tmp_path: Path) -> None:
    video_file = tmp_path / "lecture.mp4"
    video_file.write_bytes(b"dummy video content")

    # When no sidecar exists
    assert find_sidecar_subtitles(video_file) is None

    # Sidecar .srt exists
    srt_file = tmp_path / "lecture.srt"
    srt_file.write_text("1\n00:00:01,000 --> 00:00:02,000\nTest\n", encoding="utf-8")
    found = find_sidecar_subtitles(video_file)
    assert found is not None
    assert found.name == "lecture.srt"

    # Priority check: language specific sidecar .en.srt
    srt_file.unlink()
    en_vtt = tmp_path / "lecture.en.vtt"
    en_vtt.write_text("WEBVTT\n\n00:01.000 --> 00:02.000\nHello\n", encoding="utf-8")
    found_en = find_sidecar_subtitles(video_file)
    assert found_en is not None
    assert found_en.name == "lecture.en.vtt"
