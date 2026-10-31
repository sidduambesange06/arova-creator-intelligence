from pathlib import Path
import re
import subprocess

from app.core.config import settings
from app.processing.metadata import get_ffmpeg_binary


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def export_subclip(
    video_path: str | Path,
    start_time: float,
    end_time: float,
    output_dir: str | Path | None = None,
) -> Path:
    """Export a trimmed video subclip using lossless stream copy with ultrafast fallback."""
    src_path = Path(video_path).resolve()
    if not src_path.is_file():
        raise FileNotFoundError(f"Source video not found: {src_path}")

    if start_time < 0 or end_time <= start_time:
        raise ValueError(f"Invalid timestamp range: start={start_time}, end={end_time}")

    clips_dir = Path(output_dir or Path(settings.MEDIA_STORAGE_DIR) / "clips").resolve()
    clips_dir.mkdir(parents=True, exist_ok=True)

    base_stem = _sanitize_filename(src_path.stem)
    out_filename = f"{base_stem}_clip_{int(start_time)}_{int(end_time)}.mp4"
    out_path = clips_dir / out_filename

    ffmpeg_bin = get_ffmpeg_binary()

    # Step 1: Attempt lossless stream copy (-c copy)
    cmd_copy = [
        ffmpeg_bin,
        "-y",
        "-ss",
        str(round(start_time, 2)),
        "-to",
        str(round(end_time, 2)),
        "-i",
        str(src_path),
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        str(out_path),
    ]

    proc = subprocess.run(cmd_copy, capture_output=True, text=True, timeout=60)

    # Step 2: Fallback to ultrafast libx264 re-encoding if stream copy fails or produces empty file
    # shortcut: falls back to ultrafast libx264 when stream copy fails on non-keyframe boundaries, upgrade to smart cut if sample-accurate GOP re-encoding is required.
    if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        cmd_transcode = [
            ffmpeg_bin,
            "-y",
            "-ss",
            str(round(start_time, 2)),
            "-to",
            str(round(end_time, 2)),
            "-i",
            str(src_path),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            str(out_path),
        ]
        transcode_proc = subprocess.run(cmd_transcode, capture_output=True, text=True, timeout=60)
        if transcode_proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
            err = transcode_proc.stderr or proc.stderr
            raise RuntimeError(f"FFmpeg clip export failed: {err}")

    return out_path
