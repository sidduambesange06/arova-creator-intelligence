from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess

import imageio_ffmpeg


@dataclass(frozen=True)
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    format: str
    file_size: int
    has_audio: bool = False


def get_ffmpeg_binary() -> str:
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def get_ffprobe_binary() -> str | None:
    return shutil.which("ffprobe")


def _parse_fps(raw_fps: str) -> float:
    if "/" in raw_fps:
        num, den = raw_fps.split("/", 1)
        den_f = float(den)
        return round(float(num) / den_f, 2) if den_f else 0.0
    return round(float(raw_fps), 2)


def probe_video_metadata(video_path: str | Path) -> VideoMetadata:
    path = Path(video_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")

    file_size = path.stat().st_size
    ext_format = path.suffix.lstrip(".").lower() or "unknown"

    ffprobe_bin = shutil.which("ffprobe")
    if ffprobe_bin:
        cmd = [
            ffprobe_bin,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
                timeout=30,
            )
            info = json.loads(proc.stdout)
            streams = info.get("streams", [])
            v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            fmt = info.get("format", {})
            return VideoMetadata(
                duration=round(float(fmt.get("duration") or v_stream.get("duration") or 0.0), 3),
                width=int(v_stream.get("width") or 0),
                height=int(v_stream.get("height") or 0),
                fps=_parse_fps(str(v_stream.get("r_frame_rate") or "0/1")),
                codec=str(v_stream.get("codec_name") or "unknown"),
                format=ext_format,
                file_size=file_size,
                has_audio=has_audio,
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            raise ValueError(f"Unable to probe invalid media file: {path.name}")

    ffmpeg_bin = get_ffmpeg_binary()
    proc = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    stderr = proc.stderr or ""
    if "Invalid data found" in stderr or "No such file" in stderr:
        raise ValueError(f"Unable to probe invalid media file: {path.name}")

    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    duration = (
        round(int(dur_match.group(1)) * 3600 + int(dur_match.group(2)) * 60 + float(dur_match.group(3)), 3)
        if dur_match
        else 0.0
    )

    codec = "unknown"
    width, height = 0, 0
    fps = 0.0
    has_audio = False
    for line in stderr.splitlines():
        if "Video:" in line:
            c_match = re.search(r"Video:\s*([a-zA-Z0-9_-]+)", line)
            if c_match:
                codec = c_match.group(1)
            res_match = re.search(r",\s*(\d{2,5})x(\d{2,5})(?:[\s,\[])", line)
            if res_match:
                width, height = int(res_match.group(1)), int(res_match.group(2))
            fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", line)
            if fps_match:
                fps = round(float(fps_match.group(1)), 2)
        if "Audio:" in line:
            has_audio = True

    return VideoMetadata(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        codec=codec,
        format=ext_format,
        file_size=file_size,
        has_audio=has_audio,
    )


def has_audio_stream(video_path: str | Path) -> bool:
    """Check whether a video file contains an active audio stream."""
    try:
        meta = probe_video_metadata(video_path)
        return meta.has_audio
    except Exception:
        return False
