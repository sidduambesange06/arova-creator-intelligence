from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class ParsedSubtitleCue:
    """Normalized subtitle cue interval."""

    start_time: float
    end_time: float
    text: str


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CUE_TIMING_RE = re.compile(r"^\s*([0-9:.,]+)\s*-->\s*([0-9:.,]+)(.*)$")


def parse_subtitle_timestamp(ts_str: str) -> float:
    """Parse subtitle timestamp (SRT or WebVTT) into seconds as float.

    Supported formats:
      - HH:MM:SS,mmm or HH:MM:SS.mmm
      - MM:SS.mmm or MM:SS,mmm
    """
    ts_str = ts_str.strip().replace(",", ".")
    if ts_str.startswith("-") or "-" in ts_str:
        raise ValueError(f"Negative timestamp component in: {ts_str!r}")

    parts = ts_str.split(":")
    if len(parts) == 3:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        if hours < 0 or minutes < 0 or seconds < 0:
            raise ValueError(f"Negative timestamp component in: {ts_str!r}")
        return round(hours * 3600.0 + minutes * 60.0 + seconds, 3)
    if len(parts) == 2:
        minutes = float(parts[0])
        seconds = float(parts[1])
        if minutes < 0 or seconds < 0:
            raise ValueError(f"Negative timestamp component in: {ts_str!r}")
        return round(minutes * 60.0 + seconds, 3)
    raise ValueError(f"Invalid timestamp format: {ts_str!r}")


def parse_subtitles(content: str, filename_hint: str = "") -> list[ParsedSubtitleCue]:
    """Parse raw SRT or WebVTT string content into a list of normalized cues.

    Strips formatting tags, cue settings, voice tags, and comments.
    """
    if not content or not content.strip():
        return []

    if content.startswith("\ufeff"):
        content = content[1:]

    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n+", content.strip())

    cues: list[ParsedSubtitleCue] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        timing_idx = -1
        start_ts = 0.0
        end_ts = 0.0
        for idx, line in enumerate(lines):
            m = _CUE_TIMING_RE.match(line)
            if m:
                try:
                    s = parse_subtitle_timestamp(m.group(1))
                    e = parse_subtitle_timestamp(m.group(2))
                    if e >= s:
                        timing_idx = idx
                        start_ts = s
                        end_ts = e
                        break
                except ValueError:
                    continue

        if timing_idx == -1:
            # Header block, NOTE comment, or malformed cue without timing
            continue

        text_lines = lines[timing_idx + 1 :]
        if not text_lines:
            continue

        raw_text = " ".join(text_lines)
        clean_text = _HTML_TAG_RE.sub("", raw_text)
        clean_text = " ".join(clean_text.split())

        if clean_text:
            cues.append(ParsedSubtitleCue(start_time=start_ts, end_time=end_ts, text=clean_text))

    cues.sort(key=lambda c: (c.start_time, c.end_time))
    return cues


def find_sidecar_subtitles(video_path: str | Path) -> Path | None:
    """Locate matching sidecar subtitle file in the same directory as the video.

    Checks extensions (.srt, .vtt) with matching base name and common language suffixes.
    """
    path = Path(video_path).resolve()
    if not path.parent.is_dir():
        return None
    stem = path.stem.lower()
    suffixes = [
        f"{stem}.srt",
        f"{stem}.vtt",
        f"{stem}.en.srt",
        f"{stem}.en.vtt",
        f"{stem}.eng.srt",
        f"{stem}.eng.vtt",
    ]
    try:
        dir_files = {f.name.lower(): f for f in path.parent.iterdir() if f.is_file()}
        for s in suffixes:
            if s in dir_files:
                candidate = dir_files[s]
                if candidate.stat().st_size > 0:
                    return candidate
    except OSError:
        return None
    return None
