from pathlib import Path
import subprocess
import wave
import pytest

from app.processing.audio import extract_audio_wav
from app.processing.metadata import get_ffmpeg_binary, has_audio_stream
from app.processing.scene_detection import detect_video_scenes


def _synthesize_test_media(target_mp4: Path, with_audio: bool = True) -> Path:
    ffmpeg_bin = get_ffmpeg_binary()
    if with_audio:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2.0:size=320x240:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=2.0",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            str(target_mp4),
        ]
    else:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2.0:size=320x240:rate=24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target_mp4),
        ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=30)
    return target_mp4


def test_extract_audio_wav_with_audio_and_no_silent_fallback(tmp_path: Path) -> None:
    # 1. Video with audio -> successfully extracts 16kHz mono PCM WAV
    media_with_audio = _synthesize_test_media(tmp_path / "clip_with_audio.mp4", with_audio=True)
    assert has_audio_stream(media_with_audio) is True

    wav_path = extract_audio_wav(media_with_audio, "vid_aud_1", output_dir=tmp_path / "media")
    assert wav_path.is_file()
    assert wav_path.stat().st_size > 0

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2

    # 2. Silent video (no audio stream) -> raises ValueError; zero silent WAV synthesized
    media_silent = _synthesize_test_media(tmp_path / "clip_silent.mp4", with_audio=False)
    assert has_audio_stream(media_silent) is False

    silent_wav_target = (tmp_path / "media" / "audio" / "vid_silent_1.wav")
    with pytest.raises(ValueError, match="contains no audio stream"):
        extract_audio_wav(media_silent, "vid_silent_1", output_dir=tmp_path / "media")

    # Verify no 1-second silent WAV was fabricated or left on disk
    assert not silent_wav_target.is_file()


def test_detect_video_scenes(tmp_path: Path) -> None:
    video_path = _synthesize_test_media(tmp_path / "scene_test.mp4", with_audio=False)
    scenes = detect_video_scenes(
        video_path=video_path,
        video_id="vid_scene_1",
        duration=2.0,
        threshold=25.0,
        output_dir=tmp_path / "media",
    )
    assert len(scenes) >= 1
    first_scene = scenes[0]
    assert first_scene.start_time == 0.0
    assert first_scene.end_time > 0.0
    if first_scene.thumbnail_path:
        assert Path(first_scene.thumbnail_path).is_file()
