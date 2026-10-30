from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TranscriptChunk:
    video_id: str
    chunk_text: str
    start_time: float
    end_time: float
    segment_ids: list[str] = field(default_factory=list)


def build_timestamp_windows(
    segments: list[Any],
    video_id: str,
    window_sec: float = 30.0,
    overlap_sec: float = 5.0,
) -> list[TranscriptChunk]:
    if not segments:
        return []

    # Normalize segment items (support ORM objects or dicts)
    parsed_segs = []
    for s in segments:
        if isinstance(s, dict):
            s_id = str(s.get("id", ""))
            start = float(s.get("start_time", 0.0))
            end = float(s.get("end_time", 0.0))
            text = str(s.get("text", "")).strip()
        else:
            s_id = str(getattr(s, "id", ""))
            start = float(getattr(s, "start_time", 0.0))
            end = float(getattr(s, "end_time", 0.0))
            text = str(getattr(s, "text", "")).strip()

        if text and end > start:
            parsed_segs.append({"id": s_id, "start": start, "end": end, "text": text})

    if not parsed_segs:
        return []

    parsed_segs.sort(key=lambda x: x["start"])

    chunks: list[TranscriptChunk] = []
    n = len(parsed_segs)
    i = 0

    while i < n:
        w_start = parsed_segs[i]["start"]
        current_window: list[dict[str, Any]] = []
        j = i

        while j < n:
            current_window.append(parsed_segs[j])
            w_end = parsed_segs[j]["end"]
            if (w_end - w_start) >= window_sec:
                break
            j += 1

        chunk_text = " ".join(s["text"] for s in current_window).strip()
        c_start = round(current_window[0]["start"], 3)
        c_end = round(current_window[-1]["end"], 3)
        c_ids = [s["id"] for s in current_window if s["id"]]

        chunks.append(
            TranscriptChunk(
                video_id=video_id,
                chunk_text=chunk_text,
                start_time=c_start,
                end_time=c_end,
                segment_ids=c_ids,
            )
        )

        if j >= n - 1:
            break

        # Move to next window with overlap
        target_next_start = c_end - overlap_sec
        next_i = i + 1
        while next_i <= j and parsed_segs[next_i]["start"] < target_next_start:
            next_i += 1
        if next_i <= i:
            next_i = i + 1
        i = next_i

    return chunks
