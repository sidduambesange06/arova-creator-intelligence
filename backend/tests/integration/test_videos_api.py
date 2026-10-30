from collections.abc import Generator
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.session import Base, get_db, init_db
from app.main import app
from app.processing.metadata import get_ffmpeg_binary


def _make_test_mp4(target: Path, duration: float = 1.5) -> Path:
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
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "ALLOWED_MEDIA_ROOTS", str(tmp_path))
    monkeypatch.setattr(settings, "MEDIA_STORAGE_DIR", str(tmp_path / "media"))

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_import_list_stream_and_safe_delete_index(api_client: TestClient, tmp_path: Path) -> None:
    video_file = _make_test_mp4(tmp_path / "lecture.mp4", duration=2.0)

    col_res = api_client.post(
        "/api/v1/collections",
        json={"name": "AI Systems", "description": "Engineering recordings"},
    )
    assert col_res.status_code == 201
    collection_id = col_res.json()["id"]

    imp_res = api_client.post(
        "/api/v1/videos/import",
        json={"path": str(video_file), "collection_id": collection_id},
    )
    assert imp_res.status_code == 200
    imp_body = imp_res.json()
    assert len(imp_body["imported"]) == 1
    assert imp_body["skipped_duplicates"] == 0
    video_id = imp_body["imported"][0]["id"]
    assert imp_body["imported"][0]["width"] == 320
    assert imp_body["imported"][0]["height"] == 240
    assert collection_id in imp_body["imported"][0]["collection_ids"]

    dup_res = api_client.post(
        "/api/v1/videos/import",
        json={"path": str(video_file)},
    )
    assert dup_res.status_code == 200
    assert dup_res.json()["skipped_duplicates"] == 1

    list_res = api_client.get(f"/api/v1/videos?collection_id={collection_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    thumb_res = api_client.get(f"/api/v1/videos/{video_id}/thumbnail")
    assert thumb_res.status_code == 200
    assert thumb_res.headers["content-type"] == "image/jpeg"

    range_res = api_client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers={"Range": "bytes=0-127"},
    )
    assert range_res.status_code == 206
    assert range_res.headers["accept-ranges"] == "bytes"
    assert range_res.headers["content-range"].startswith("bytes 0-127/")
    assert len(range_res.content) == 128

    del_res = api_client.delete(f"/api/v1/videos/{video_id}/index")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_video_id"] == video_id
    assert video_file.is_file(), "Original source video file must NEVER be deleted!"

    after_list = api_client.get("/api/v1/videos")
    assert after_list.json() == []
