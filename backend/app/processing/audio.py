from pathlib import Path
import subprocess

from app.core.config import settings
from app.processing.metadata import get_ffmpeg_binary, has_audio_stream


def extract_audio_wav(
    video_path: str | Path,
    video_id: str,
    output_dir: str | Path | None = None,
) -> Path:
    """Extract a 16kHz mono 16-bit PCM WAV from a video file containing an audio stream.

    Raises:
        FileNotFoundError: If the source video file does not exist.
        ValueError: If the video contains no audio stream or extraction fails.
    """
    src = Path(video_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Media file not found: {src}")

    if not has_audio_stream(src):
        raise ValueError(f"Media file '{src.name}' contains no audio stream.")

    base_dir = Path(output_dir or settings.MEDIA_STORAGE_DIR) / "audio"
    base_dir.mkdir(parents=True, exist_ok=True)
    target_wav = (base_dir / f"{video_id}.wav").resolve()

    ffmpeg_bin = get_ffmpeg_binary()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-protocol_whitelist",
        "file,pipe,null",
        "-i",
        str(src),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(target_wav),
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    stderr = proc.stderr or ""

    if (
        proc.returncode != 0
        or not target_wav.is_file()
        or target_wav.stat().st_size == 0
    ):
        if target_wav.is_file():
            try:
                target_wav.unlink(missing_ok=True)
            except OSError:
                pass
        raise ValueError(
            f"Failed to extract audio from '{src.name}': {stderr.strip() or 'No audio stream or conversion failure'}"
        )

    return target_wav
