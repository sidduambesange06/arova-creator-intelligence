import errno
import hashlib
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import unicodedata
import uuid

from app.core.config import settings
from app.processing.metadata import get_ffmpeg_binary, probe_video_metadata

logger = logging.getLogger(__name__)

# Documented system error codes indicating hard links are not supported by the filesystem:
# POSIX: ENOSYS (Function not implemented), EOPNOTSUPP (Operation not supported), EXDEV (Cross-device link)
# Windows: winerror 1 (ERROR_INVALID_FUNCTION, FAT32/exFAT), 50 (ERROR_NOT_SUPPORTED), 120 (ERROR_CALL_NOT_IMPLEMENTED)
_UNSUPPORTED_HARDLINK_ERRNOS = {errno.ENOSYS, errno.EOPNOTSUPP, errno.EXDEV}
_UNSUPPORTED_HARDLINK_WINERRORS = {1, 50, 120}


def _validate_clip_timestamps(
    start_time: float,
    end_time: float,
    max_duration: float | None = None,
) -> tuple[float, float]:
    """Validate clip export timestamp boundaries.

    Rejects NaN, infinite, negative, or inverted intervals.
    Enforces strict source-duration validation when max_duration is known.
    """
    if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
        raise TypeError(f"Timestamps must be real numbers, got start={type(start_time)}, end={type(end_time)}")

    start = float(start_time)
    end = float(end_time)

    if not math.isfinite(start) or not math.isfinite(end):
        raise ValueError(f"Timestamps must be finite numbers: start={start_time}, end={end_time}")

    if start < 0.0:
        raise ValueError(f"start_time cannot be negative: {start}")

    if end <= start:
        raise ValueError(f"end_time ({end}s) must be strictly greater than start_time ({start}s)")

    if max_duration is not None:
        if not isinstance(max_duration, (int, float)) or not math.isfinite(max_duration) or max_duration < 0:
            raise ValueError(f"max_duration must be a finite non-negative number: {max_duration}")
        if max_duration > 0:
            if start >= max_duration:
                raise ValueError(f"start_time ({start}s) exceeds video duration ({max_duration}s)")
            if end > max_duration:
                raise ValueError(f"end_time ({end}s) exceeds video duration ({max_duration}s)")

    return start, end


def _sanitize_filename(name: str) -> str:
    """Sanitize filename stems and identifiers to safe Unicode characters.

    Retains Unicode letters (L*), numbers (N*), combining marks (M* e.g. Kannada/Hindi matras and viramas),
    and safe delimiters (hyphens, dots, underscores).
    Replaces path separators, traversal syntax, control codes, and punctuation with an underscore.
    """
    cleaned_chars: list[str] = []
    for ch in name.strip():
        if ch in ("-", ".", "_"):
            cleaned_chars.append(ch)
        else:
            cat = unicodedata.category(ch)
            if cat[0] in ("L", "N", "M"):
                cleaned_chars.append(ch)
            else:
                cleaned_chars.append("_")

    cleaned = "".join(cleaned_chars)
    # Collapse consecutive underscores and strip leading/trailing dots/underscores
    collapsed = re.sub(r"_{2,}", "_", cleaned).strip("._")
    return collapsed or "clip"


def _format_timestamp(seconds: float) -> str:
    """Format timestamp seconds with up to 3 decimal places without unnecessary trailing zeroes."""
    formatted = f"{seconds:.3f}".rstrip("0").rstrip(".")
    return formatted if formatted and formatted != "-0" else "0"


def _is_unsupported_hardlink_error(exc: OSError) -> bool:
    """Determine whether an OSError indicates that the filesystem does not support hard links."""
    if exc.errno in _UNSUPPORTED_HARDLINK_ERRNOS:
        return True
    winerr = getattr(exc, "winerror", None)
    if winerr in _UNSUPPORTED_HARDLINK_WINERRORS:
        return True
    return False


def _atomically_claim_and_move(temp_path: Path, target_path: Path) -> bool:
    """Atomically claim target_path without overwriting.

    Uses os.link for atomic collision detection on hardlink-capable filesystems.
    Under documented unsupported-hardlink conditions (e.g. FAT32/exFAT), uses exclusive
    slot reservation (O_CREAT | O_EXCL) with guaranteed cleanup if promotion fails.

    Returns:
        True if target_path was successfully claimed and temp_path promoted.
        False if target_path already exists (collision).

    Raises:
        OSError: If a filesystem error (e.g. EACCES, ENOSPC, EROFS) occurs.
    """
    try:
        os.link(str(temp_path), str(target_path))
        temp_path.unlink(missing_ok=True)
        return True
    except FileExistsError:
        # Pre-existing file collision; caller will increment disambiguation suffix
        return False
    except OSError as link_err:
        if not _is_unsupported_hardlink_error(link_err):
            # Permission, disk space, read-only filesystem, etc. Must not be treated as collision or fallback
            raise

    # Fallback path: ONLY entered on filesystems where hard links are unsupported
    reserved_by_us = False
    reserved_stat: os.stat_result | None = None
    try:
        fd = os.open(str(target_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            reserved_stat = os.fstat(fd)
        finally:
            os.close(fd)
        reserved_by_us = True
        temp_path.replace(target_path)
        return True
    except FileExistsError:
        # Pre-existing file; slot was not claimed by us
        return False
    except Exception:
        # Promotion failed after we reserved the empty slot; clean up ONLY our reservation
        # by establishing file identity (inode/device on POSIX/NTFS and 0-byte size).
        # Note on stat-to-unlink race & threat model:
        # In a multi-user environment where an untrusted local user has write access to clips_dir,
        # a hostile process could theoretically replace the file between os.stat and target_path.unlink.
        # We do not claim absolute protection against hostile concurrent replacement on shared mounts;
        # Arova's threat model is single-user local storage where clips_dir is in the user's private storage.
        # Furthermore, if filesystem identity is unavailable (st_ino == 0), we fail safe by leaving
        # the orphan reservation rather than risking deleting an unverified file.
        if reserved_by_us and reserved_stat is not None and reserved_stat.st_ino != 0:
            try:
                curr_stat = os.stat(str(target_path))
                if (
                    curr_stat.st_size == 0
                    and (curr_stat.st_dev, curr_stat.st_ino)
                    == (reserved_stat.st_dev, reserved_stat.st_ino)
                ):
                    target_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def measure_clip_duration(clip_path: str | Path) -> float:
    """Measure the actual media container duration of an exported clip.

    Strictly measures the generated file using probe_video_metadata.
    Never fabricates, estimates, or falls back to requested intervals.

    Returns:
        float: Probed duration rounded to 3 decimal places.

    Raises:
        RuntimeError: If probing fails or returns an invalid, zero, negative, or non-finite duration.
    """
    path = Path(clip_path).resolve()
    if not path.is_file():
        raise RuntimeError(f"Clip file does not exist for duration measurement: {path}")

    try:
        meta = probe_video_metadata(path)
    except Exception as exc:
        logger.error(f"Failed to probe duration for clip {path.name}: {exc}")
        raise RuntimeError(f"Failed to probe clip duration: {exc}") from exc

    duration = meta.duration
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0.0:
        logger.error(f"Clip {path.name} probe returned invalid duration: {duration}")
        raise RuntimeError(f"Measured clip duration is invalid or non-positive: {duration}")

    return round(float(duration), 3)


def export_subclip(
    video_path: str | Path,
    start_time: float,
    end_time: float,
    output_dir: str | Path | None = None,
    video_id: str | None = None,
    max_duration: float | None = None,
) -> Path:
    """Export a trimmed video subclip using lossless stream copy with ultrafast fallback.

    Ensures safe non-overwriting destination reservation, fractional timestamp disambiguation,
    strict source duration validation, post-export media measurement verification,
    and automatic cleanup of unverified or partial files.

    Note on stream copy timing: Lossless stream copy (-c copy) seeks to the nearest GOP keyframe.
    The resulting clip duration reflects keyframe boundaries rather than frame-accurate cuts.
    """
    src_path = Path(video_path).resolve()
    if not src_path.is_file():
        raise FileNotFoundError(f"Source video not found: {src_path}")

    start_time, end_time = _validate_clip_timestamps(
        start_time=start_time,
        end_time=end_time,
        max_duration=max_duration,
    )

    clips_dir = Path(output_dir or Path(settings.MEDIA_STORAGE_DIR) / "clips").resolve()
    clips_dir.mkdir(parents=True, exist_ok=True)

    base_stem = _sanitize_filename(src_path.stem)
    if video_id:
        src_id = _sanitize_filename(str(video_id))[:12]
    else:
        src_id = hashlib.sha256(str(src_path).encode("utf-8")).hexdigest()[:8]

    start_fmt = _format_timestamp(start_time)
    end_fmt = _format_timestamp(end_time)
    candidate_stem = f"{base_stem}_{src_id}_{start_fmt}s-{end_fmt}s"

    ffmpeg_bin = get_ffmpeg_binary()
    temp_file = clips_dir / f".tmp_export_{uuid.uuid4().hex}.mp4"

    try:
        # Step 1: Lossless stream copy (-c copy)
        cmd_copy = [
            ffmpeg_bin,
            "-nostdin",
            "-ss",
            str(round(start_time, 3)),
            "-to",
            str(round(end_time, 3)),
            "-i",
            str(src_path),
            "-c",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
            str(temp_file),
        ]

        proc = subprocess.run(
            cmd_copy,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        # Step 2: Fallback to ultrafast libx264 transcode if stream copy fails or produces empty file
        # shortcut: falls back to ultrafast libx264 when stream copy fails on non-keyframe boundaries, upgrade to smart cut if sample-accurate GOP re-encoding is required.
        if proc.returncode != 0 or not temp_file.is_file() or temp_file.stat().st_size == 0:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            cmd_transcode = [
                ffmpeg_bin,
                "-nostdin",
                "-ss",
                str(round(start_time, 3)),
                "-to",
                str(round(end_time, 3)),
                "-i",
                str(src_path),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                str(temp_file),
            ]
            transcode_proc = subprocess.run(
                cmd_transcode,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
            if transcode_proc.returncode != 0 or not temp_file.is_file() or temp_file.stat().st_size == 0:
                err = transcode_proc.stderr or proc.stderr
                raise RuntimeError(f"FFmpeg clip export failed: {err}")

        # Step 3: Atomic reservation into final destination without overwriting existing clips
        promoted_path: Path | None = None
        for counter in range(0, 10000):
            suffix = "" if counter == 0 else f"_{counter}"
            candidate_path = clips_dir / f"{candidate_stem}{suffix}.mp4"
            if _atomically_claim_and_move(temp_file, candidate_path):
                promoted_path = candidate_path
                break

        if promoted_path is None:
            raise RuntimeError("Failed to allocate unique clip filename after 10000 attempts")

        # Step 4: Verification of the exported clip. Must be readable with valid duration.
        # If verification fails, discard ONLY the file generated by this request.
        try:
            measure_clip_duration(promoted_path)
        except Exception as verif_err:
            promoted_path.unlink(missing_ok=True)
            raise RuntimeError(f"Export verification failed: generated clip could not be measured: {verif_err}") from verif_err

        return promoted_path

    finally:
        # Guarantee partial / temporary file cleanup on any failure
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)
