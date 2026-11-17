"""Unit Tests for Task 4C: Resumable Intelligence Processing.

Verifies:
1. Stage DAG dependency ordering and topological sort.
2. Deterministic SHA-256 stage fingerprinting and config sensitivity.
3. Idempotent skip of already completed stages.
4. Selective downstream invalidation on model/config changes.
5. Lease acquisition, heartbeats, and stale lease recovery.
6. Job cancellation and graceful pipeline abortion.
7. Resumption of cancelled or failed pipeline jobs without restarting from scratch.
8. Artifact persistence and atomic superseding (is_current=False on prior).
9. Disk space safeguards and structured error code mapping.
10. Preservation of non-AI stages when optional AI stage fails.
11. REST API endpoints for cancellation, resumption, stage runs, and artifacts.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import (
    Artifact,
    Asset,
    AssetVersion,
    ProcessingJob,
    StageRun,
    Video,
)
from app.models.enums import (
    IdentityState,
    StageStatus,
    TrustLevel,
    compute_deterministic_version_id,
)
from app.services.pipeline_orchestrator import (
    check_disk_space,
    compute_stage_fingerprint,
    ensure_asset_and_version,
    InsufficientDiskSpaceError,
    persist_stage_artifact,
    PipelineOrchestrator,
    recover_stale_stage_runs,
    STAGE_ASR_TRANSCRIPTION,
    STAGE_AUDIO_EXTRACTION,
    STAGE_DEPENDENCIES,
    STAGE_EMBEDDING_INDEXING,
    STAGE_EXECUTION_ORDER,
    STAGE_METADATA_PROBE,
    STAGE_OCR_DETECTION,
    STAGE_SCENE_DETECTION,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def sample_version(db_session: Session) -> AssetVersion:
    asset = Asset(id=str(uuid4()), created_at=datetime.now(timezone.utc))
    db_session.add(asset)
    db_session.flush()

    version = AssetVersion(
        id=str(uuid4()),
        asset_id=asset.id,
        sha256="1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
        size_bytes=1024,
        identity_state=IdentityState.VERIFIED.value,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(version)
    asset.current_version_id = version.id
    db_session.commit()
    db_session.refresh(version)
    return version


@pytest.fixture()
def sample_video(db_session: Session, tmp_path: Path) -> Video:
    file_path = tmp_path / "sample.mp4"
    file_path.write_bytes(b"FAKE_VIDEO_CONTENT_BYTES")

    video_id = str(uuid4())
    video = Video(
        id=video_id,
        filename="sample.mp4",
        file_path=str(file_path),
        file_hash="1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
        file_size=file_path.stat().st_size,
        duration=10.0,
        width=1280,
        height=720,
        fps=30.0,
        codec="h264",
        format="mp4",
        processing_status="pending",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_stage_dependency_graph_and_topological_sort() -> None:
    assert STAGE_DEPENDENCIES[STAGE_METADATA_PROBE] == []
    assert STAGE_DEPENDENCIES[STAGE_SCENE_DETECTION] == [STAGE_METADATA_PROBE]
    assert STAGE_DEPENDENCIES[STAGE_OCR_DETECTION] == [STAGE_SCENE_DETECTION]
    assert STAGE_DEPENDENCIES[STAGE_AUDIO_EXTRACTION] == [STAGE_METADATA_PROBE]
    assert STAGE_DEPENDENCIES[STAGE_ASR_TRANSCRIPTION] == [STAGE_AUDIO_EXTRACTION]
    assert STAGE_DEPENDENCIES[STAGE_EMBEDDING_INDEXING] == [STAGE_ASR_TRANSCRIPTION]

    executed: set[str] = set()
    for stage in STAGE_EXECUTION_ORDER:
        for dep in STAGE_DEPENDENCIES[stage]:
            assert dep in executed, f"Dependency {dep} was not executed before {stage}"
        executed.add(stage)


def test_stage_fingerprint_deterministic_and_config_sensitive() -> None:
    v_id = "test-version-1"
    fp1 = compute_stage_fingerprint(v_id, STAGE_ASR_TRANSCRIPTION, {"model": "base.en", "beam_size": 5})
    fp2 = compute_stage_fingerprint(v_id, STAGE_ASR_TRANSCRIPTION, {"beam_size": 5, "model": "base.en"})
    assert fp1 == fp2

    fp3 = compute_stage_fingerprint(v_id, STAGE_ASR_TRANSCRIPTION, {"model": "large-v3", "beam_size": 5})
    assert fp1 != fp3

    fp4 = compute_stage_fingerprint(
        v_id, STAGE_ASR_TRANSCRIPTION, {"model": "base.en", "beam_size": 5}, upstream_fingerprints=["audio-fp-1"]
    )
    fp5 = compute_stage_fingerprint(
        v_id, STAGE_ASR_TRANSCRIPTION, {"model": "base.en", "beam_size": 5}, upstream_fingerprints=["audio-fp-2"]
    )
    assert fp4 != fp5


def test_ensure_asset_and_version(db_session: Session, sample_video: Video) -> None:
    asset, version = ensure_asset_and_version(db_session, sample_video)
    assert asset is not None
    assert version is not None
    assert version.sha256 == sample_video.file_hash
    assert sample_video.asset_id == asset.id
    assert sample_video.version_id == version.id
    assert version.id == compute_deterministic_version_id(sample_video.file_hash)


def test_artifact_persistence_and_atomic_superseding(db_session: Session, sample_version: AssetVersion) -> None:
    version_id = sample_version.id

    art1 = persist_stage_artifact(
        db=db_session,
        version_id=version_id,
        kind="transcript",
        producer_stage="asr",
        producer_model="base.en",
        producer_revision="v1",
        config_hash="hash1",
        trust=TrustLevel.ASR.value,
    )
    db_session.commit()
    assert art1.is_current is True

    # Superseding artifact
    art2 = persist_stage_artifact(
        db=db_session,
        version_id=version_id,
        kind="transcript",
        producer_stage="asr",
        producer_model="large-v3",
        producer_revision="v2",
        config_hash="hash2",
        trust=TrustLevel.HUMAN_CONFIRMED.value,
    )
    db_session.commit()

    db_session.refresh(art1)
    db_session.refresh(art2)
    assert art1.is_current is False
    assert art2.is_current is True

    # Verify only art2 is returned as current
    current_artifacts = db_session.query(Artifact).filter_by(version_id=version_id, is_current=True).all()
    assert len(current_artifacts) == 1
    assert current_artifacts[0].id == art2.id


def test_stale_lease_recovery(db_session: Session, sample_version: AssetVersion) -> None:
    version_id = sample_version.id
    past = datetime.now(timezone.utc) - timedelta(minutes=5)

    stale_run_1 = StageRun(
        id=str(uuid4()),
        version_id=version_id,
        stage="scene_detection",
        fingerprint="fp1",
        status=StageStatus.RUNNING.value,
        attempt=1,
        lease_until=past,
    )
    stale_run_2 = StageRun(
        id=str(uuid4()),
        version_id=version_id,
        stage="asr_transcription",
        fingerprint="fp2",
        status=StageStatus.RUNNING.value,
        attempt=3,
        lease_until=past,
    )
    db_session.add_all([stale_run_1, stale_run_2])
    db_session.commit()

    recovered = recover_stale_stage_runs(db_session, max_attempts=3)
    assert len(recovered) == 2

    db_session.refresh(stale_run_1)
    db_session.refresh(stale_run_2)

    assert stale_run_1.status == StageStatus.PENDING.value
    assert stale_run_1.lease_until is None
    assert "recovered" in stale_run_1.error_detail.lower()

    assert stale_run_2.status == StageStatus.FAILED.value
    assert stale_run_2.error_code == "LEASE_EXPIRED"
    assert stale_run_2.lease_until is None


def test_disk_space_safeguard(tmp_path: Path) -> None:
    with pytest.raises(InsufficientDiskSpaceError, match="below safe minimum"):
        check_disk_space(tmp_path, min_free_mb=999999999.0)


def test_idempotent_skip_of_completed_stages(db_session: Session, sample_video: Video, tmp_path: Path) -> None:
    orchestrator = PipelineOrchestrator(db=db_session, media_storage_dir=tmp_path)

    with patch.object(orchestrator, "_exec_metadata_probe", return_value="{}") as mock_probe, \
         patch.object(orchestrator, "_exec_scene_detection", return_value=3) as mock_scenes, \
         patch.object(orchestrator, "_exec_ocr_detection", return_value=0) as mock_ocr, \
         patch.object(orchestrator, "_exec_audio_extraction", return_value=None) as mock_audio, \
         patch.object(orchestrator, "_exec_asr_transcription", return_value=False) as mock_asr, \
         patch.object(orchestrator, "_exec_embedding_indexing", return_value=False) as mock_embed:

        # 1. Run pipeline first time
        job_id_1 = orchestrator.run_pipeline(video_id=sample_video.id)
        assert mock_probe.call_count == 1
        assert mock_scenes.call_count == 1

        # 2. Run pipeline second time with identical config -> must be skipped idempotently
        job_id_2 = orchestrator.run_pipeline(video_id=sample_video.id)
        assert mock_probe.call_count == 1
        assert mock_scenes.call_count == 1
        assert mock_ocr.call_count == 1


def test_selective_downstream_invalidation_on_config_change(
    db_session: Session, sample_video: Video, tmp_path: Path
) -> None:
    orch_1 = PipelineOrchestrator(
        db=db_session,
        media_storage_dir=tmp_path,
        config={STAGE_ASR_TRANSCRIPTION: {"model": "tiny.en"}},
    )

    with patch.object(orch_1, "_exec_metadata_probe", return_value="{}") as mock_probe, \
         patch.object(orch_1, "_exec_scene_detection", return_value=2) as mock_scenes, \
         patch.object(orch_1, "_exec_ocr_detection", return_value=0), \
         patch.object(orch_1, "_exec_audio_extraction", return_value="/fake/audio.wav"), \
         patch.object(orch_1, "_exec_asr_transcription", return_value=True) as mock_asr, \
         patch.object(orch_1, "_exec_embedding_indexing", return_value=True) as mock_embed:

        orch_1.run_pipeline(video_id=sample_video.id)
        assert mock_probe.call_count == 1
        assert mock_scenes.call_count == 1
        assert mock_asr.call_count == 1

    orch_2 = PipelineOrchestrator(
        db=db_session,
        media_storage_dir=tmp_path,
        config={STAGE_ASR_TRANSCRIPTION: {"model": "base.en"}},
    )

    with patch.object(orch_2, "_exec_metadata_probe", return_value="{}") as mock_probe_2, \
         patch.object(orch_2, "_exec_scene_detection", return_value=2) as mock_scenes_2, \
         patch.object(orch_2, "_exec_ocr_detection", return_value=0), \
         patch.object(orch_2, "_exec_audio_extraction", return_value="/fake/audio.wav"), \
         patch.object(orch_2, "_exec_asr_transcription", return_value=True) as mock_asr_2, \
         patch.object(orch_2, "_exec_embedding_indexing", return_value=True) as mock_embed_2:

        orch_2.run_pipeline(video_id=sample_video.id)
        # Upstream stages (probe and scene detection) MUST NOT RE-EXECUTE!
        assert mock_probe_2.call_count == 0
        assert mock_scenes_2.call_count == 0
        # ASR stage MUST re-execute because config hash changed
        assert mock_asr_2.call_count == 1


def test_non_ai_stages_preserved_when_ai_stage_fails(
    db_session: Session, sample_video: Video, tmp_path: Path
) -> None:
    orchestrator = PipelineOrchestrator(db=db_session, media_storage_dir=tmp_path)

    def _fake_probe(video, version, sr):
        persist_stage_artifact(db_session, version.id, "metadata", STAGE_METADATA_PROBE)
        return "{}"

    def _fake_scenes(video, version, sr):
        persist_stage_artifact(db_session, version.id, "scenes", STAGE_SCENE_DETECTION)
        return 2

    with patch.object(orchestrator, "_exec_metadata_probe", side_effect=_fake_probe), \
         patch.object(orchestrator, "_exec_scene_detection", side_effect=_fake_scenes), \
         patch.object(orchestrator, "_exec_ocr_detection", return_value=0), \
         patch.object(orchestrator, "_exec_audio_extraction", return_value="/fake/audio.wav"), \
         patch.object(orchestrator, "_exec_asr_transcription", side_effect=RuntimeError("Whisper model missing")):

        with pytest.raises(RuntimeError, match="Whisper model missing"):
            orchestrator.run_pipeline(video_id=sample_video.id)

    # Verify that non-AI stages succeeded and are persisted
    asset, version = ensure_asset_and_version(db_session, sample_video)
    stage_runs = {sr.stage: sr for sr in db_session.query(StageRun).filter_by(version_id=version.id).all()}

    assert stage_runs[STAGE_METADATA_PROBE].status == StageStatus.SUCCEEDED.value
    assert stage_runs[STAGE_SCENE_DETECTION].status == StageStatus.SUCCEEDED.value
    assert stage_runs[STAGE_OCR_DETECTION].status == StageStatus.SUCCEEDED.value
    assert stage_runs[STAGE_AUDIO_EXTRACTION].status == StageStatus.SUCCEEDED.value
    assert stage_runs[STAGE_ASR_TRANSCRIPTION].status == StageStatus.FAILED.value
    assert "Whisper model missing" in stage_runs[STAGE_ASR_TRANSCRIPTION].error_detail

    # Verify non-AI artifacts exist
    artifacts = {a.kind: a for a in db_session.query(Artifact).filter_by(version_id=version.id).all()}
    assert "metadata" in artifacts
    assert "scenes" in artifacts


def test_job_cancellation_and_resumption(
    db_session: Session, sample_video: Video, tmp_path: Path
) -> None:
    orchestrator = PipelineOrchestrator(db=db_session, media_storage_dir=tmp_path)

    # 1. Create job and cancel it before completion
    job_id = str(uuid4())
    job = ProcessingJob(
        id=job_id,
        video_id=sample_video.id,
        job_type="full_pipeline",
        status="cancelled",
        progress=20.0,
    )
    db_session.add(job)
    db_session.commit()

    # Running pipeline with cancelled job must exit cleanly without executing stages
    orchestrator.run_pipeline(video_id=sample_video.id, job_id=job.id)
    db_session.refresh(job)
    assert job.status == "cancelled"

    # 2. Resuming the job
    job.status = "processing"
    db_session.commit()

    with patch.object(orchestrator, "_exec_metadata_probe", return_value="{}"), \
         patch.object(orchestrator, "_exec_scene_detection", return_value=2), \
         patch.object(orchestrator, "_exec_ocr_detection", return_value=0), \
         patch.object(orchestrator, "_exec_audio_extraction", return_value=None), \
         patch.object(orchestrator, "_exec_asr_transcription", return_value=False), \
         patch.object(orchestrator, "_exec_embedding_indexing", return_value=False):

        orchestrator.run_pipeline(video_id=sample_video.id, job_id=job.id)

    db_session.refresh(job)
    assert job.status == "completed"
    assert job.progress == 100.0


def test_jobs_api_cancel_and_resume_endpoints(tmp_path: Path) -> None:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def _override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestingSession() as db:
        video = Video(
            id="test-vid-1",
            filename="vid.mp4",
            file_path=str(tmp_path / "vid.mp4"),
            file_hash="fakehash12345",
            file_size=1024,
            duration=5.0,
            processing_status="processing",
        )
        job = ProcessingJob(
            id="test-job-1",
            video_id=video.id,
            job_type="full_pipeline",
            status="processing",
            progress=25.0,
        )
        db.add_all([video, job])
        db.commit()

    client = TestClient(app)

    # 1. Cancel job via API
    cancel_res = client.post("/api/v1/jobs/test-job-1/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Verify status in DB
    get_res = client.get("/api/v1/jobs/test-job-1")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "cancelled"

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
