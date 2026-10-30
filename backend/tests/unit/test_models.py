from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.database.session import Base, init_db
from app.models.entities import Collection, CollectionVideo, ProcessingJob, Video


def test_sqlite_schema_and_cascade_delete() -> None:
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(test_engine)

    inspector = inspect(test_engine)
    tables = set(inspector.get_table_names())
    assert {
        "videos",
        "collections",
        "collection_videos",
        "transcripts",
        "transcript_segments",
        "video_scenes",
        "embedding_records",
        "video_summaries",
        "processing_jobs",
    }.issubset(tables)

    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        video = Video(
            filename="demo.mp4",
            file_path="/tmp/demo.mp4",
            file_hash="abc123hash",
            file_size=1024,
            duration=12.5,
            width=1920,
            height=1080,
            fps=30.0,
            codec="h264",
            format="mp4",
        )
        col = Collection(name="Tutorials", description="Tech demos")
        db.add_all([video, col])
        db.flush()

        link = CollectionVideo(collection_id=col.id, video_id=video.id)
        job = ProcessingJob(video_id=video.id, job_type="probe", status="completed", progress=100.0)
        db.add_all([link, job])
        db.commit()

        vid_id = video.id
        db.delete(video)
        db.commit()

        assert db.query(ProcessingJob).filter_by(video_id=vid_id).count() == 0
        assert db.query(CollectionVideo).filter_by(video_id=vid_id).count() == 0
        assert db.query(Collection).filter_by(id=col.id).count() == 1

    Base.metadata.drop_all(bind=test_engine)

