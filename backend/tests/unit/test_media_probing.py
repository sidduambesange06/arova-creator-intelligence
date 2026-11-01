from pathlib import Path
import shutil
import subprocess
import pytest

from app.core.security import compute_sha256, discover_video_files, validate_media_path
from app.processing.metadata import get_ffmpeg_binary, probe_video_metadata
from app.processing.thumbnails import generate_video_thumbnail


def _create_sample_mp4(target: Path, duration: float = 1.5) -> Path:
    ffmpeg_bin = get_ffmpeg_binary()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration}:size=320x240:rate=24",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(target),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=30)
    return target


def test_path_traversal_protection_and_discovery(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()

    secret_file = outside_dir / "clip.mp4"
    secret_file.write_bytes(b"dummy")

    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(secret_file, allowed_roots=[allowed_dir])

    valid_mp4 = allowed_dir / "valid.mp4"
    valid_mp4.write_bytes(b"video-bytes")
    ignored_txt = allowed_dir / "notes.txt"
    ignored_txt.write_text("ignore")

    found = discover_video_files(allowed_dir, allowed_roots=[allowed_dir])
    assert found == [valid_mp4.resolve()]
    assert len(compute_sha256(valid_mp4)) == 64


def test_ffmpeg_metadata_probe_and_thumbnail(tmp_path: Path) -> None:
    sample_mp4 = _create_sample_mp4(tmp_path / "sample.mp4", duration=2.0)

    meta = probe_video_metadata(sample_mp4)
    assert meta.width == 320
    assert meta.height == 240
    assert meta.fps == 24.0
    assert 1.8 <= meta.duration <= 2.2
    assert meta.codec == "h264"
    assert meta.format == "mp4"
    assert meta.file_size > 0

    thumb = generate_video_thumbnail(
        video_path=sample_mp4,
        video_id="vid-test-1",
        timestamp_sec=0.5,
        output_dir=tmp_path / "media",
    )
    assert thumb.is_file()
    assert thumb.stat().st_size > 100


def test_ffmpeg_metadata_probe_fallback_without_ffprobe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify metadata extraction falls back to ffmpeg -i when ffprobe is missing."""
    sample_mp4 = _create_sample_mp4(tmp_path / "fallback_sample.mp4", duration=2.0)
    real_which = shutil.which

    def fake_which(cmd: str) -> str | None:
        if cmd == "ffprobe":
            return None
        return real_which(cmd)

    monkeypatch.setattr(shutil, "which", fake_which)
    meta = probe_video_metadata(sample_mp4)
    assert meta.width == 320
    assert meta.height == 240
    assert meta.fps == 24.0
    assert 1.8 <= meta.duration <= 2.2
    assert meta.codec == "h264"
    assert meta.format == "mp4"
    assert meta.file_size > 0

