from dataclasses import dataclass
import json
import re
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.retrieval.hybrid_search import run_hybrid_search
from app.core.config import settings
from app.models.entities import Transcript, Video, VideoSummary


@dataclass
class ChapterMarker:
    start_time: float
    title: str


def find_video_clips(
    db: Session,
    query: str,
    min_duration: float = 5.0,
    max_duration: float = 60.0,
    top_k: int = 5,
    video_id: str | None = None,
) -> list[dict[str, Any]]:
    # Retrieve top candidates via hybrid search
    search_resp = run_hybrid_search(
        db=db,
        query=query,
        top_k=top_k * 2,
        use_reranker=True,
        video_id_filter=video_id,
    )

    clips: list[dict[str, Any]] = []
    for item in search_resp.results:
        raw_dur = item.end_time - item.start_time
        s_time = item.start_time
        e_time = item.end_time

        # Adjust bounds to respect [min_duration, max_duration]
        if raw_dur < min_duration:
            e_time = round(s_time + min_duration, 2)
        elif raw_dur > max_duration:
            e_time = round(s_time + max_duration, 2)

        clip_dur = round(e_time - s_time, 2)
        rationale = f"Matches '{query}' with relevance score {item.rerank_score:.3f} and stage-1 score {item.stage1_score:.3f}."

        clips.append(
            {
                "video_id": item.video_id,
                "filename": item.filename,
                "start_time": s_time,
                "end_time": e_time,
                "duration": clip_dur,
                "transcript_snippet": item.chunk_text,
                "relevance_score": item.rerank_score,
                "rationale": rationale,
            }
        )

        if len(clips) >= top_k:
            break

    return clips


def generate_video_summary(
    db: Session,
    video_id: str,
    api_key: str | None = None,
) -> VideoSummary:
    video = db.query(Video).filter_by(id=video_id).first()
    if not video:
        raise LookupError(f"Video {video_id} not found")

    transcript = db.query(Transcript).filter_by(video_id=video_id).first()
    if not transcript or not transcript.segments:
        raise ValueError(f"No transcript found for video {video_id}. Process video ASR first.")

    # Check for existing summary
    existing = db.query(VideoSummary).filter_by(video_id=video_id).first()
    if existing:
        return existing

    segments = sorted(transcript.segments, key=lambda s: s.start_time)
    full_text = transcript.full_text or " ".join(s.text for s in segments)

    key = api_key or settings.GEMINI_API_KEY
    if key and key.strip():
        try:
            # Use google-genai SDK if key is provided
            from google import genai  # type: ignore

            client = genai.Client(api_key=key.strip())
            prompt = (
                f"You are a factual video summarizer. Summarize this transcript accurately:\n\n"
                f"{full_text[:6000]}\n\n"
                f"Output valid JSON with keys 'summary', 'topics' (list of strings), and 'chapters' (list of {{'start_time': float, 'title': str}})."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            parsed = json.loads(response.text)
            summary_text = parsed.get("summary", full_text[:300])
            topics = parsed.get("topics", ["Video Overview"])
            chapters = parsed.get("chapters", [{"start_time": 0.0, "title": "Introduction"}])
            model_name = "gemini-2.5-flash"
        except Exception:
            # fallback to extractive grounded summarizer
            summary_text, topics, chapters, model_name = _extractive_summary(segments, full_text)
    else:
        summary_text, topics, chapters, model_name = _extractive_summary(segments, full_text)

    summary_record = VideoSummary(
        id=str(uuid4()),
        video_id=video.id,
        summary_text=summary_text,
        topics_json=json.dumps(topics),
        chapters_json=json.dumps(chapters),
        model_name=model_name,
    )
    db.add(summary_record)
    db.commit()
    db.refresh(summary_record)
    return summary_record


def _extractive_summary(segments: list, full_text: str) -> tuple[str, list[str], list[dict], str]:
    # Extract topics from word frequency
    words = re.findall(r"\b[a-zA-Z]{4,}\b", full_text.lower())
    stop_words = {"this", "that", "with", "from", "have", "video", "about", "which", "will"}
    freq: dict[str, int] = {}
    for w in words:
        if w not in stop_words:
            freq[w] = freq.get(w, 0) + 1
    top_topics = [w.capitalize() for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5]]
    if not top_topics:
        top_topics = ["Engineering", "Video Overview"]

    # Build grounded summary text
    summary_sentences = [s.text.strip() for s in segments[:3] if s.text.strip()]
    summary_text = " ".join(summary_sentences) or full_text[:250]

    # Build timestamped chapters based on temporal thirds
    n = len(segments)
    chapters = []
    if n >= 3:
        chapters.append({"start_time": segments[0].start_time, "title": f"Introduction: {top_topics[0] if top_topics else 'Overview'}"})
        mid_idx = n // 2
        chapters.append({"start_time": segments[mid_idx].start_time, "title": f"Core Discussion: {top_topics[1] if len(top_topics) > 1 else 'Architecture'}"})
        late_idx = (2 * n) // 3
        chapters.append({"start_time": segments[late_idx].start_time, "title": f"Summary & Wrap-up"})
    else:
        chapters.append({"start_time": segments[0].start_time, "title": "Main Session"})

    return summary_text, top_topics, chapters, "extractive-grounded-local"

