from pathlib import Path
import subprocess
import wave

from app.core.config import settings
from app.processing.metadata import get_ffmpeg_binary


def extract_audio_wav(
    video_path: str | Path,
    video_id: str,
    output_dir: str | Path | None = None,
) -> Path:
    src = Path(video_path).resolve()
    base_dir = Path(output_dir or settings.MEDIA_STORAGE_DIR) / "audio"
    base_dir.mkdir(parents=True, exist_ok=True)
    target_wav = (base_dir / f"{video_id}.wav").resolve()

    ffmpeg_bin = get_ffmpeg_binary()
    cmd = [
        ffmpeg_bin,
        "-y",
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

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    stderr = proc.stderr or ""

    # Silent video or no audio stream fallback
    if (
        proc.returncode != 0
        or "Output file does not contain any stream" in stderr
        or "matches no streams" in stderr
        or "does not contain any stream" in stderr
        or not target_wav.is_file()
        or target_wav.stat().st_size == 0
    ):
        with wave.open(str(target_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 16000)

    return target_wav

