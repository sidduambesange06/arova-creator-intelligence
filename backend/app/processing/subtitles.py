from dataclasses import dataclass
import math
from pathlib import Path
import re
from typing import Any, Iterable
import unicodedata


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


def normalize_word_timings(
    words: list[dict[str, Any]] | None,
    *,
    media_duration: float | None = None,
) -> list[dict[str, Any]] | None:
    """Validate and normalize ASR word-level timings with finite, monotonic, bounded values.

    Preserves Unicode (NFC, retaining Indic matras/viramas/ZWJ/ZWNJ).
    Returns None if input is None or yields no valid words.
    """
    if not words:
        return None

    max_bound = float(media_duration) if (media_duration is not None and math.isfinite(media_duration) and media_duration > 0) else None
    normalized: list[dict[str, Any]] = []
    prev_start = 0.0

    for item in words:
        if not isinstance(item, dict):
            continue
        raw_word = item.get("word")
        if not isinstance(raw_word, str):
            continue
        clean_word = unicodedata.normalize("NFC", raw_word).strip()
        if not clean_word:
            continue

        try:
            start = float(item["start"])
            end = float(item["end"])
        except (KeyError, TypeError, ValueError):
            continue

        if not (math.isfinite(start) and math.isfinite(end)):
            continue

        start = max(0.0, start)
        if max_bound is not None:
            start = min(start, max_bound)
        if start < prev_start:
            start = prev_start

        end = max(start, end)
        if max_bound is not None:
            end = min(end, max_bound)
            if start > end:
                start = end

        prob_raw = item.get("probability")
        prob: float | None = None
        if prob_raw is not None:
            try:
                p_val = float(prob_raw)
                if math.isfinite(p_val):
                    prob = round(max(0.0, min(1.0, p_val)), 4)
            except (TypeError, ValueError):
                prob = None

        start_r = round(start, 3)
        end_r = round(max(start_r, end), 3)
        prev_start = start_r
        entry: dict[str, Any] = {"word": clean_word, "start": start_r, "end": end_r}
        if prob is not None:
            entry["probability"] = prob
        normalized.append(entry)

    return normalized or None


def _format_ms_timestamp(seconds: float, sep: str) -> str:
    safe_sec = max(0.0, float(seconds)) if math.isfinite(seconds) else 0.0
    total_ms = int(round(safe_sec * 1000.0))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{ms:03d}"


def _format_ass_timestamp(seconds: float) -> str:
    safe_sec = max(0.0, float(seconds)) if math.isfinite(seconds) else 0.0
    total_cs = int(round(safe_sec * 100.0))
    hours, rem = divmod(total_cs, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, cs = divmod(rem, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    """Escape ASS override braces, backslashes, and line breaks so untrusted text cannot inject tags."""
    nfc = unicodedata.normalize("NFC", text or "")
    normalized_nl = nfc.replace("\r\n", "\n").replace("\r", "\n")
    escaped = normalized_nl.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    return escaped.replace("\n", r"\N")


def _extract_seg_fields(seg: Any) -> tuple[float, float, str, list[dict[str, Any]] | None]:
    if isinstance(seg, dict):
        start = float(seg.get("start_time", 0.0))
        end = float(seg.get("end_time", start))
        text = str(seg.get("text", "")).strip()
        words = seg.get("words")
    else:
        start = float(getattr(seg, "start_time", 0.0))
        end = float(getattr(seg, "end_time", start))
        text = str(getattr(seg, "text", "")).strip()
        words = getattr(seg, "words", None)
    return start, max(start, end), text, words


def export_srt(segments: Iterable[Any]) -> str:
    """Export transcript segments as deterministic UTF-8 SubRip (.srt) text."""
    blocks: list[str] = []
    idx = 1
    for seg in segments:
        start, end, text, _ = _extract_seg_fields(seg)
        if not text:
            continue
        blocks.append(
            f"{idx}\n{_format_ms_timestamp(start, ',')} --> {_format_ms_timestamp(end, ',')}\n"
            f"{unicodedata.normalize('NFC', text)}"
        )
        idx += 1
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def export_vtt(segments: Iterable[Any]) -> str:
    """Export transcript segments as deterministic UTF-8 WebVTT (.vtt) text."""
    blocks: list[str] = ["WEBVTT"]
    for seg in segments:
        start, end, text, _ = _extract_seg_fields(seg)
        if not text:
            continue
        blocks.append(
            f"{_format_ms_timestamp(start, '.')} --> {_format_ms_timestamp(end, '.')}\n"
            f"{unicodedata.normalize('NFC', text)}"
        )
    return "\n\n".join(blocks) + "\n"


def export_ass(
    segments: Iterable[Any],
    *,
    title: str = "Arova Creator Intelligence Subtitles",
    include_karaoke: bool = False,
) -> str:
    """Export transcript segments as valid ASS v4+ (.ass) with safe tag escaping."""
    safe_title = unicodedata.normalize("NFC", title).replace("\r", " ").replace("\n", " ").strip()
    lines = [
        "[Script Info]",
        f"Title: {safe_title}",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,48,&H00FFFFFF,&H000088EF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,1,2,40,40,36,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for seg in segments:
        start, end, text, words = _extract_seg_fields(seg)
        if not text:
            continue
        if include_karaoke and words:
            norm_words = normalize_word_timings(words)
            if norm_words:
                parts: list[str] = []
                for w in norm_words:
                    dur_cs = max(1, int(round((w["end"] - w["start"]) * 100.0)))
                    parts.append(f"{{\\k{dur_cs}}}{_escape_ass_text(w['word'])}")
                body = " ".join(parts)
            else:
                body = _escape_ass_text(text)
        else:
            body = _escape_ass_text(text)
        lines.append(
            f"Dialogue: 0,{_format_ass_timestamp(start)},{_format_ass_timestamp(end)},Default,,0,0,0,,{body}"
        )
    return "\n".join(lines) + "\n"
