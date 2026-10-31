from pathlib import Path
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database.session import SessionLocal, init_db
from app.models.entities import Video
from app.processing.metadata import get_ffmpeg_binary
from app.services import media_service
from app.workers.pipeline_runner import run_video_pipeline


def main() -> None:
    init_db()
    db = SessionLocal()

    # Check if video already exists
    existing = db.query(Video).filter_by(filename="demo_developer_lecture.mp4").first()
    if existing:
        print(f"Demo video already indexed: {existing.id} ({existing.filename})")
        db.close()
        return

    sample_dir = ROOT_DIR / "sample_data"
    sample_dir.mkdir(parents=True, exist_ok=True)
    target_mp4 = sample_dir / "demo_developer_lecture.mp4"

    # Synthesize a realistic 12-second multi-scene MP4 with audio using ffmpeg
    ffmpeg_bin = get_ffmpeg_binary()
    print(f"Generating demo video at: {target_mp4}")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=12:size=640x360:rate=24",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=12",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        str(target_mp4),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print("Demo MP4 synthesized successfully.")

    # Import video into media library
    import_resp = media_service.import_videos(
        db=db,
        target_path=str(target_mp4),
        allowed_roots=[ROOT_DIR],
    )
    imported_video = import_resp.imported[0]
    print(f"Imported Video ID: {imported_video.id}")

    # Run processing pipeline (Scenes + Audio + ASR + Chunker + Dual Index)
    print("Running end-to-end processing pipeline...")
    job_id = run_video_pipeline(video_id=imported_video.id, db=db)
    print(f"Processing Pipeline completed! Job ID: {job_id}")

    # Generate initial grounded summary
    from app.services.summary_service import generate_video_summary
    summary = generate_video_summary(db=db, video_id=imported_video.id)
    print(f"Grounded summary generated: {summary.summary_text[:100]}...")

    db.close()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    main()

