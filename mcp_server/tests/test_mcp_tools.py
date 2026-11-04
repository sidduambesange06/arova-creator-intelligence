from collections.abc import Generator
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.ai.providers.embeddings import index_video_chunks
from app.core.config import settings
from app.database.session import Base, init_db
from app.models.entities import Transcript, TranscriptSegment, Video, VideoSummary
from app.processing.metadata import get_ffmpeg_binary
from mcp_server.tools import video_tools


def _independent_test_probe_ffprobe_duration(clip_path: Path) -> float:
    """Direct test-side FFprobe subprocess invocation.

    Does NOT reuse the production probe_video_metadata() helper.
    """
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
            str(clip_path),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=15,
        )
        info = json.loads(proc.stdout)
        dur = info.get("format", {}).get("duration")
        if dur:
            return round(float(dur), 3)
        for s in info.get("streams", []):
            if s.get("codec_type") == "video" and s.get("duration"):
                return round(float(s["duration"]), 3)

    ffmpeg_bin = shutil.which("ffmpeg") or get_ffmpeg_binary()
    proc = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-i", str(clip_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    if not match:
        raise RuntimeError(f"Independent test probe failed on {clip_path}")
    return round(int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3)), 3)


def _make_test_mp4(target: Path, duration: float = 2.0) -> Path:
    ffmpeg_bin = get_ffmpeg_binary()
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=320x240:rate=24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    return target



@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Session, None, None]:
    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(tmp_path))
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", str(tmp_path / "media"))
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", str(tmp_path / "vectors"))

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    test_file = tmp_path / "mcp_deep_dive.mp4"
    _make_test_mp4(test_file, duration=2.0)

    with TestingSession() as session:
        video = Video(
            filename="mcp_deep_dive.mp4",
            file_path=str(test_file),
            file_hash="hash_mcp_demo_123",
            duration=75.0,
            width=1920,
            height=1080,
            fps=30.0,
            codec="h264",
            format="mp4",
        )
        session.add(video)
        session.commit()

        transcript = Transcript(
            video_id=video.id,
            language="en",
            model_name="whisper-base",
            full_text="Model Context Protocol enables agents to connect to local tools and video knowledge.",
        )
        session.add(transcript)
        session.commit()

        segments = [
            (0.0, 25.0, "Model Context Protocol enables agents to connect to local tools and video knowledge."),
            (25.0, 50.0, "We implement eight read only tools for semantic retrieval and indexing."),
            (50.0, 75.0, "The system delivers real time transcript search and grounded summaries."),
        ]
        for s, e, text_val in segments:
            seg = TranscriptSegment(
                transcript_id=transcript.id,
                video_id=video.id,
                start_time=s,
                end_time=e,
                text=text_val,
                confidence=0.96,
            )
            session.add(seg)
        session.commit()

        summary = VideoSummary(
            video_id=video.id,
            summary_text="Model Context Protocol enables agents to connect to local tools and video knowledge.",
            topics_json=json.dumps(["MCP", "Semantic Retrieval", "AI Tools"]),
            chapters_json=json.dumps([
                {"title": "Introduction to MCP", "start_time": 0.0, "end_time": 25.0},
                {"title": "Read-Only Architecture", "start_time": 25.0, "end_time": 50.0},
                {"title": "Semantic Retrieval", "start_time": 50.0, "end_time": 75.0},
            ]),
            model_name="extractive-grounded-local",
        )
        session.add(summary)
        session.commit()

        from app.database.migrator import run_idempotent_backfill
        run_idempotent_backfill(session)
        index_video_chunks(session, video.id, storage_dir=tmp_path / "vectors")
        yield session

    Base.metadata.drop_all(bind=test_engine)


def test_all_eight_mcp_tools(db_session: Session) -> None:
    # 1. list_videos
    videos = video_tools.list_videos(db=db_session)
    assert len(videos) == 1
    assert videos[0]["filename"] == "mcp_deep_dive.mp4"
    video_id = videos[0]["id"]

    # 2. get_video_metadata
    meta = video_tools.get_video_metadata(video_id=video_id, db=db_session)
    assert meta["id"] == video_id
    assert meta["width"] == 1920
    assert meta["height"] == 1080
    assert meta["duration"] == 75.0
    # Host filesystem paths must be sanitized for display (not raw absolute system paths)
    assert not meta["file_path"].startswith("/")
    assert not (len(meta["file_path"]) > 2 and meta["file_path"][1] == ":")
    assert meta["file_path"] == "mcp_deep_dive.mp4"

    # 3. search_video_content
    search_res = video_tools.search_video_content(query="Model Context Protocol", top_k=3, db=db_session)
    assert len(search_res) >= 1
    assert search_res[0]["video_id"] == video_id
    assert search_res[0]["stage1_score"] > 0.0

    # 4. search_transcripts
    lex_res = video_tools.search_transcripts(query="Protocol", db=db_session)
    assert len(lex_res) >= 1
    assert "Model Context Protocol" in lex_res[0]["text"]

    # 5. find_video_clips
    clips = video_tools.find_video_clips(
        query="semantic retrieval",
        min_duration=10.0,
        max_duration=60.0,
        db=db_session,
    )
    assert len(clips) >= 1
    assert clips[0]["duration"] >= 10.0
    assert clips[0]["duration"] <= 60.0

    # 6. summarize_video
    summary = video_tools.summarize_video(video_id=video_id, db=db_session)
    assert summary["video_id"] == video_id
    assert len(summary["summary"]) > 0
    assert len(summary["topics"]) >= 1

    # 7. get_video_chapters
    chapters = video_tools.get_video_chapters(video_id=video_id, db=db_session)
    assert len(chapters) >= 1
    assert "start_time" in chapters[0]
    assert "title" in chapters[0]

    # 8. get_media_library_stats
    stats = video_tools.get_media_library_stats(db=db_session)
    assert stats["total_videos"] == 1
    assert stats["total_duration_sec"] == 75.0
    assert stats["total_transcripts_indexed"] == 1

    # 10. get_media_availability
    avail = video_tools.get_media_availability(video_id=video_id, db=db_session)
    assert avail["video_id"] == video_id
    assert avail["can_play"] is True
    assert avail["can_export"] is True

    # 11. find_duplicate_media
    dupes = video_tools.find_duplicate_media(db=db_session)
    assert isinstance(dupes, list)

    # 12. get_evidence_citations
    citations = video_tools.get_evidence_citations(query="Model Context Protocol", db=db_session)
    assert len(citations) >= 1
    assert citations[0]["video_id"] == video_id
    assert "citation_text" in citations[0]

    # 13. get_capability_status
    cap = video_tools.get_capability_status(db=db_session)
    assert cap["execution_profile"] == "fully_offline_no_ai"
    assert "capabilities" in cap

    # 9. export_video_clip (direct tool function check)
    clip_res = video_tools.export_video_clip(video_id=video_id, start_time=0.2, end_time=1.0, db=db_session)
    assert clip_res["video_id"] == video_id
    assert clip_res["start_time"] == 0.2
    assert clip_res["end_time"] == 1.0
    assert not clip_res["clip_path"].startswith("/")
    assert not (len(clip_res["clip_path"]) > 2 and clip_res["clip_path"][1] == ":")

    # Independently inspect the generated output file using direct test-side FFprobe subprocess
    # (does NOT reuse production probe_video_metadata helper)
    clip_file = Path(settings.MEDIA_STORAGE_DIR) / "clips" / clip_res["clip_filename"]
    assert clip_file.is_file()
    independent_duration = _independent_test_probe_ffprobe_duration(clip_file)
    # Justified tolerance: container header format duration rounded to millisecond precision (0.005s)
    assert clip_res["duration"] == pytest.approx(independent_duration, abs=0.005)
    assert clip_res["file_size"] == clip_file.stat().st_size


@pytest.mark.anyio
async def test_mcp_server_default_tools_are_eight_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AROVA_ENABLE_MCP_EXPORTS", raising=False)
    from mcp_server.server import create_mcp_server, mcp
    server = create_mcp_server()
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    expected_tools = [
        "list_videos",
        "get_video_metadata",
        "search_video_content",
        "search_transcripts",
        "find_video_clips",
        "summarize_video",
        "get_video_chapters",
        "get_media_library_stats",
        "get_media_availability",
        "find_duplicate_media",
        "get_evidence_citations",
        "get_capability_status",
    ]
    assert len(tools) == 12
    assert tool_names == expected_tools
    assert "export_video_clip" not in tool_names

    # Also verify module-level singleton instance executed by stdio runner
    singleton_tools = await mcp.list_tools()
    singleton_tool_names = [t.name for t in singleton_tools]
    assert len(singleton_tools) == 12
    assert "export_video_clip" not in singleton_tool_names


@pytest.mark.anyio
async def test_mcp_server_opt_in_exports() -> None:
    from mcp_server.server import create_mcp_server
    server = create_mcp_server(enable_exports=True)
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert len(tools) == 13
    assert "export_video_clip" in tool_names


def test_mcp_export_probe_failure_raises_and_cleans_up(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that if duration probing fails, export raises RuntimeError and cleans up generated clip."""
    videos = video_tools.list_videos(db=db_session)
    video_id = videos[0]["id"]
    clips_dir = Path(settings.MEDIA_STORAGE_DIR) / "clips"

    def fake_probe_failure(p):
        raise ValueError("Simulated corrupted media container header")

    import app.processing.clip_export as ce
    monkeypatch.setattr(ce, "probe_video_metadata", fake_probe_failure)

    with pytest.raises(RuntimeError, match="could not be measured"):
        video_tools.export_video_clip(video_id=video_id, start_time=0.2, end_time=1.0, db=db_session)

    # Verify no orphan clip file was left in clips_dir
    created_clips = list(clips_dir.glob("*.mp4"))
    assert len(created_clips) == 0


def test_mcp_read_only_tools_leave_database_unmutated(db_session: Session) -> None:
    """Verify that calling read-only tools causes zero database mutations."""
    from app.models.entities import EmbeddingRecord, VideoScene

    counts_before = {
        "videos": db_session.query(Video).count(),
        "transcripts": db_session.query(Transcript).count(),
        "segments": db_session.query(TranscriptSegment).count(),
        "scenes": db_session.query(VideoScene).count(),
        "summaries": db_session.query(VideoSummary).count(),
        "embeddings": db_session.query(EmbeddingRecord).count(),
    }

    videos = video_tools.list_videos(db=db_session)
    video_id = videos[0]["id"]

    video_tools.get_video_metadata(video_id=video_id, db=db_session)
    video_tools.search_video_content(query="Model Context Protocol", top_k=3, db=db_session)
    video_tools.search_transcripts(query="Protocol", db=db_session)
    video_tools.find_video_clips(query="semantic retrieval", min_duration=10.0, max_duration=60.0, db=db_session)
    video_tools.summarize_video(video_id=video_id, db=db_session)
    video_tools.get_video_chapters(video_id=video_id, db=db_session)
    video_tools.get_media_library_stats(db=db_session)
    video_tools.get_media_availability(video_id=video_id, db=db_session)
    video_tools.find_duplicate_media(db=db_session)
    video_tools.get_evidence_citations(query="Model Context Protocol", db=db_session)
    video_tools.get_capability_status(db=db_session)

    counts_after = {
        "videos": db_session.query(Video).count(),
        "transcripts": db_session.query(Transcript).count(),
        "segments": db_session.query(TranscriptSegment).count(),
        "scenes": db_session.query(VideoScene).count(),
        "summaries": db_session.query(VideoSummary).count(),
        "embeddings": db_session.query(EmbeddingRecord).count(),
    }
    assert counts_before == counts_after

    # Calling summarize_video on an unknown video ID must raise ValueError without mutating DB
    with pytest.raises(ValueError, match=r"(?:No summary|not found)"):
        video_tools.summarize_video(video_id=99999, db=db_session)

    assert db_session.query(VideoSummary).count() == counts_before["summaries"]


def test_mcp_non_persistent_summary_and_path_safety(db_session: Session) -> None:
    """Verify that summarizing a video without an existing VideoSummary does not mutate DB,

    and that host filesystem paths are sanitized.
    """
    # Create a secondary video with transcript segments but NO VideoSummary
    video2 = Video(
        filename="unsummarized.mp4",
        file_path="C:\\Users\\SecretUser\\Documents\\Sensitive\\unsummarized.mp4",
        thumbnail_path="C:\\Users\\SecretUser\\Documents\\Sensitive\\thumb.jpg",
        file_hash="hash_unsummarized",
        duration=30.0,
    )
    db_session.add(video2)
    db_session.commit()

    transcript2 = Transcript(
        video_id=video2.id,
        language="en",
        model_name="whisper-base",
        full_text="This is an unsummarized video about privacy and safety in video systems.",
    )
    db_session.add(transcript2)
    db_session.commit()

    seg = TranscriptSegment(
        transcript_id=transcript2.id,
        video_id=video2.id,
        start_time=0.0,
        end_time=10.0,
        text="This is an unsummarized video about privacy and safety in video systems.",
        confidence=0.98,
    )
    db_session.add(seg)
    db_session.commit()

    # 1. Path disclosure test: get_video_metadata must NOT leak C:\Users\... or absolute path
    meta = video_tools.get_video_metadata(video_id=video2.id, db=db_session)
    assert "SecretUser" not in meta["file_path"]
    assert "Sensitive" not in meta["file_path"]
    assert not meta["file_path"].startswith("C:")
    assert meta["file_path"] == "unsummarized.mp4"
    assert meta["thumbnail_path"] == "thumb.jpg"

    # 2. Non-persistent summary test: summarize_video must succeed without adding VideoSummary to DB
    summary_count_before = db_session.query(VideoSummary).count()
    res = video_tools.summarize_video(video_id=video2.id, db=db_session)
    assert res["video_id"] == video2.id
    assert "privacy and safety" in res["summary"]
    assert res["model_name"] == "extractive-non-persistent-mcp"

    summary_count_after = db_session.query(VideoSummary).count()
    assert summary_count_after == summary_count_before

    # 3. Non-persistent chapter test: get_video_chapters must succeed without mutating DB
    chapters = video_tools.get_video_chapters(video_id=video2.id, db=db_session)
    assert len(chapters) >= 1
    assert db_session.query(VideoSummary).count() == summary_count_before

