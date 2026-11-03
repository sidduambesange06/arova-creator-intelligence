from pathlib import Path
import shutil
import subprocess
import pytest

from app.core.security import compute_sha256, discover_video_files, get_allowed_roots, validate_media_path
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

    # Direct relative '..' traversal check
    traversal_path = allowed_dir / ".." / "outside" / "clip.mp4"
    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(traversal_path, allowed_roots=[allowed_dir])

    valid_mp4 = allowed_dir / "valid.mp4"
    valid_mp4.write_bytes(b"video-bytes")
    ignored_txt = allowed_dir / "notes.txt"
    ignored_txt.write_text("ignore")

    found = discover_video_files(allowed_dir, allowed_roots=[allowed_dir])
    assert found == [valid_mp4.resolve()]
    assert len(compute_sha256(valid_mp4)) == 64


def test_nested_directory_discovery(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    nested_dir = allowed_dir / "season_1" / "episode_1"
    nested_dir.mkdir(parents=True)

    v1 = allowed_dir / "intro.mp4"
    v1.write_bytes(b"intro")
    v2 = nested_dir / "ep1.mkv"
    v2.write_bytes(b"ep1")

    # Discover from root
    found_all = discover_video_files(allowed_dir, allowed_roots=[allowed_dir])
    assert found_all == sorted([v1.resolve(), v2.resolve()])

    # Discover from nested directory directly
    found_nested = discover_video_files(nested_dir, allowed_roots=[allowed_dir])
    assert found_nested == [v2.resolve()]


def test_symlink_file_outside_root_rejected_and_excluded(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()

    outside_video = outside_dir / "secret.mp4"
    outside_video.write_bytes(b"secret-data")

    valid_video = allowed_dir / "normal.mp4"
    valid_video.write_bytes(b"normal-data")

    symlink_file = allowed_dir / "leak_symlink.mp4"
    try:
        symlink_file.symlink_to(outside_video)
    except OSError:
        pytest.skip("Symlink creation requires elevated privileges or Developer Mode on Windows")

    # Direct validation of symlink pointing outside must raise ValueError
    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(symlink_file, allowed_roots=[allowed_dir])

    # Direct discovery on symlink pointing outside must raise ValueError
    with pytest.raises(ValueError, match="outside allowed media roots"):
        discover_video_files(symlink_file, allowed_roots=[allowed_dir])

    # Directory discovery must exclude the symlink file resolving outside allowed roots
    discovered = discover_video_files(allowed_dir, allowed_roots=[allowed_dir])
    assert discovered == [valid_video.resolve()]
    assert outside_video.resolve() not in discovered
    assert symlink_file.resolve() not in discovered


def test_symlink_directory_outside_root_rejected_and_excluded(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()

    outside_video = outside_dir / "external.mp4"
    outside_video.write_bytes(b"external-video")

    valid_video = allowed_dir / "local.mp4"
    valid_video.write_bytes(b"local-video")

    symlink_dir = allowed_dir / "outside_link"
    try:
        symlink_dir.symlink_to(outside_dir, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation requires elevated privileges or Developer Mode on Windows")

    # Direct validation of symlink directory pointing outside must raise ValueError
    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(symlink_dir, allowed_roots=[allowed_dir])

    # Direct discovery on symlink directory pointing outside must raise ValueError
    with pytest.raises(ValueError, match="outside allowed media roots"):
        discover_video_files(symlink_dir, allowed_roots=[allowed_dir])

    # Directory discovery must exclude symlinked outside directories
    discovered = discover_video_files(allowed_dir, allowed_roots=[allowed_dir])
    assert discovered == [valid_video.resolve()]
    assert outside_video.resolve() not in discovered


def test_multiple_allowed_roots_configuration(tmp_path: Path) -> None:
    root1 = tmp_path / "library_a"
    root2 = tmp_path / "library_b"
    outside = tmp_path / "library_c"
    root1.mkdir()
    root2.mkdir()
    outside.mkdir()

    v1 = root1 / "video_a.mp4"
    v1.write_bytes(b"a")
    v2 = root2 / "video_b.webm"
    v2.write_bytes(b"b")
    v_outside = outside / "video_c.mp4"
    v_outside.write_bytes(b"c")

    configured_roots = get_allowed_roots(f"{root1},{root2}")
    assert len(configured_roots) == 2
    assert root1.resolve() in configured_roots
    assert root2.resolve() in configured_roots

    # Both roots are valid
    assert validate_media_path(v1, allowed_roots=configured_roots) == v1.resolve()
    assert validate_media_path(v2, allowed_roots=configured_roots) == v2.resolve()

    # Outside root is rejected
    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(v_outside, allowed_roots=configured_roots)

    # Discovered correctly from respective roots
    assert discover_video_files(root1, allowed_roots=configured_roots) == [v1.resolve()]
    assert discover_video_files(root2, allowed_roots=configured_roots) == [v2.resolve()]


def test_unsupported_extensions_and_empty_roots(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()

    doc = allowed_dir / "document.pdf"
    doc.write_bytes(b"pdf")
    audio = allowed_dir / "song.mp3"
    audio.write_bytes(b"mp3")
    img = allowed_dir / "picture.jpg"
    img.write_bytes(b"jpg")

    # Directory discovery ignores unsupported extensions
    found = discover_video_files(allowed_dir, allowed_roots=[allowed_dir])
    assert found == []

    # Direct discovery on unsupported file raises ValueError
    with pytest.raises(ValueError, match="Unsupported video extension"):
        discover_video_files(doc, allowed_roots=[allowed_dir])

    # Empty roots configuration results in deny-by-default
    empty_roots = get_allowed_roots("")
    assert empty_roots == []
    valid_video = allowed_dir / "test.mp4"
    valid_video.write_bytes(b"test")
    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(valid_video, allowed_roots=empty_roots)


def test_nonexistent_paths(tmp_path: Path) -> None:
    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()

    # Nonexistent path inside allowed root raises FileNotFoundError
    ghost_inside = allowed_dir / "ghost.mp4"
    with pytest.raises(FileNotFoundError, match="Media path does not exist"):
        validate_media_path(ghost_inside, allowed_roots=[allowed_dir])
    with pytest.raises(FileNotFoundError, match="Media path does not exist"):
        discover_video_files(ghost_inside, allowed_roots=[allowed_dir])

    # Nonexistent path outside allowed root raises ValueError (containment check precedes existence)
    ghost_outside = outside_dir / "ghost.mp4"
    with pytest.raises(ValueError, match="outside allowed media roots"):
        validate_media_path(ghost_outside, allowed_roots=[allowed_dir])


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
