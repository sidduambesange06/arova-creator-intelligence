from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from app.processing.metadata import get_ffmpeg_binary
from app.processing.thumbnails import generate_video_thumbnail


@dataclass(frozen=True)
class DetectedScene:
    scene_index: int
    start_time: float
    end_time: float
    thumbnail_path: str | None


def detect_video_scenes(
    video_path: str | Path,
    video_id: str,
    duration: float,
    threshold: float = 27.0,
    output_dir: str | Path | None = None,
) -> list[DetectedScene]:
    src = Path(video_path).resolve()
    ffmpeg_bin = get_ffmpeg_binary()
    total_dur = max(round(duration, 3), 0.1)

    scene_factor = round(threshold / 100.0, 3)
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-i",
        str(src),
        "-vf",
        f"select='gt(scene,{scene_factor})',showinfo",
        "-f",
        "null",
        "-",
    ]

    cut_points: list[float] = []
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        stderr = proc.stderr or ""
        for match in re.finditer(r"pts_time:(\d+(?:\.\d+)?)", stderr):
            t = round(float(match.group(1)), 3)
            if 0.1 < t < total_dur - 0.1:
                cut_points.append(t)
    except Exception:
        cut_points = []

    # Sort & deduplicate cut points with minimum 0.2s distance
    cut_points = sorted(set(cut_points))
    filtered_cuts: list[float] = []
    for c in cut_points:
        if not filtered_cuts or (c - filtered_cuts[-1]) >= 0.2:
            filtered_cuts.append(c)

    boundaries = [0.0] + filtered_cuts + [total_dur]
    scenes: list[DetectedScene] = []

    for idx in range(len(boundaries) - 1):
        s_start = round(boundaries[idx], 3)
        s_end = round(boundaries[idx + 1], 3)
        if s_end <= s_start:
            continue
        midpoint = round((s_start + s_end) / 2.0, 3)

        thumb_str: str | None = None
        try:
            thumb_path = generate_video_thumbnail(
                video_path=src,
                video_id=f"{video_id}_scene_{idx}",
                timestamp_sec=midpoint,
                output_dir=output_dir,
            )
            thumb_str = str(thumb_path)
        except Exception:
            thumb_str = None

        scenes.append(
            DetectedScene(
                scene_index=idx,
                start_time=s_start,
                end_time=s_end,
                thumbnail_path=thumb_str,
            )
        )

    if not scenes:
        scenes.append(
            DetectedScene(
                scene_index=0,
                start_time=0.0,
                end_time=total_dur,
                thumbnail_path=None,
            )
        )

    return scenes

