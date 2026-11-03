from pathlib import Path
import subprocess

from app.core.config import settings
from app.processing.metadata import get_ffmpeg_binary


def generate_video_thumbnail(
    video_path: str | Path,
    video_id: str,
    timestamp_sec: float = 0.5,
    output_dir: str | Path | None = None,
) -> Path:
    src = Path(video_path).resolve()
    base_dir = Path(output_dir or settings.MEDIA_STORAGE_DIR) / "thumbnails"
    base_dir.mkdir(parents=True, exist_ok=True)
    target = (base_dir / f"{video_id}.jpg").resolve()

    ffmpeg_bin = get_ffmpeg_binary()
    seek = max(0.0, round(timestamp_sec, 3))
    cmd = [
        ffmpeg_bin,
        "-y",
        "-protocol_whitelist",
        "file,pipe,null",
        "-ss",
        str(seek),
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(target),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=30)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"Thumbnail generation failed for {src.name}")
    return target

