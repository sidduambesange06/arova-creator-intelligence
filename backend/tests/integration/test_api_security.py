from collections.abc import Generator
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.embeddings import index_video_chunks
from app.core.config import Settings, settings
from app.core.security import require_api_auth, validate_server_binding_and_security
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import Transcript, TranscriptSegment, Video, VideoSummary


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
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

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestingSession() as db:
        video = Video(
            filename="security_test.mp4",
            file_path=str(tmp_path / "security_test.mp4"),
            file_hash="hash_sec_999",
            duration=60.0,
        )
        db.add(video)
        db.commit()

        transcript = Transcript(
            video_id=video.id,
            language="en",
            model_name="whisper-base",
            full_text="Security test transcript for privacy and egress verification.",
        )
        db.add(transcript)
        db.commit()

        seg = TranscriptSegment(
            transcript_id=transcript.id,
            video_id=video.id,
            start_time=0.0,
            end_time=60.0,
            text="Security test transcript for privacy and egress verification.",
            confidence=0.98,
        )
        db.add(seg)
        db.commit()

        video2 = Video(
            filename="security_test_2.mp4",
            file_path=str(tmp_path / "security_test_2.mp4"),
            file_hash="hash_sec_999_2",
            duration=60.0,
        )
        db.add(video2)
        db.commit()

        transcript2 = Transcript(
            video_id=video2.id,
            language="en",
            model_name="whisper-base",
            full_text="Secondary test transcript for remote consent verification.",
        )
        db.add(transcript2)
        db.commit()

        seg2 = TranscriptSegment(
            transcript_id=transcript2.id,
            video_id=video2.id,
            start_time=0.0,
            end_time=60.0,
            text="Secondary test transcript for remote consent verification.",
            confidence=0.98,
        )
        db.add(seg2)
        db.commit()

        index_video_chunks(db, video.id, storage_dir=tmp_path / "vectors")
        index_video_chunks(db, video2.id, storage_dir=tmp_path / "vectors")

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_api_auth_disabled_by_default(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    res = client.get("/api/v1/videos")
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_api_auth_enforced_when_token_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "super-secret-token-12345")

    # 1. Unauthenticated request rejected
    res_no_auth = client.get("/api/v1/videos")
    assert res_no_auth.status_code == 401
    assert "WWW-Authenticate" in res_no_auth.headers
    assert "Invalid or missing API authentication token" in res_no_auth.json()["detail"]

    # 2. Invalid bearer token rejected
    res_wrong_bearer = client.get(
        "/api/v1/videos",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert res_wrong_bearer.status_code == 401

    # 3. Valid Bearer token accepted
    res_valid_bearer = client.get(
        "/api/v1/videos",
        headers={"Authorization": "Bearer super-secret-token-12345"},
    )
    assert res_valid_bearer.status_code == 200

    # 4. Valid X-API-Key header accepted
    res_valid_apikey = client.get(
        "/api/v1/videos",
        headers={"X-API-Key": "super-secret-token-12345"},
    )
    assert res_valid_apikey.status_code == 200

    # 5. Public health endpoint remains accessible without auth
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"


def test_host_header_validation_blocks_dns_rebinding(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")

    # Valid hosts (testserver, localhost, 127.0.0.1)
    res_valid = client.get("/api/v1/health", headers={"Host": "localhost:8000"})
    assert res_valid.status_code == 200

    res_testserver = client.get("/api/v1/health", headers={"Host": "testserver"})
    assert res_testserver.status_code == 200

    # Malicious host header (e.g. DNS rebinding domain)
    res_evil = client.get("/api/v1/health", headers={"Host": "attacker-rebinding.evil.com"})
    assert res_evil.status_code == 400
    assert "Invalid Host header" in res_evil.text


def test_origin_header_validation_guards_state_changing_requests(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")

    # Non-browser client request (no Origin header) on state-changing route is permitted
    res_cli = client.post("/api/v1/search/clips", json={"query": "test"})
    assert res_cli.status_code == 200

    # Browser request from allowed origin is permitted
    res_allowed_origin = client.post(
        "/api/v1/search/clips",
        json={"query": "test"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert res_allowed_origin.status_code == 200

    # Browser request from untrusted external origin is rejected with 403 Forbidden
    res_evil_origin = client.post(
        "/api/v1/search/clips",
        json={"query": "test"},
        headers={"Origin": "http://evil-tracker.example.com"},
    )
    assert res_evil_origin.status_code == 403
    assert "Untrusted Origin header" in res_evil_origin.text

    # Safe GET request from any origin is not blocked by origin middleware
    res_get_evil_origin = client.get(
        "/api/v1/health",
        headers={"Origin": "http://evil-tracker.example.com"},
    )
    assert res_get_evil_origin.status_code == 200


def test_ai_egress_consent_enforcement_for_summarization(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)

    # Fetch seeded video IDs
    videos = client.get("/api/v1/videos").json()
    video_id_1 = videos[0]["id"]
    video_id_2 = videos[1]["id"]

    mock_genai = MagicMock()
    mock_client_cls = MagicMock()
    mock_genai.Client = mock_client_cls
    mock_google = MagicMock()
    mock_google.genai = mock_genai

    monkeypatch.setitem(sys.modules, "google", mock_google)
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)

    # 1. Without consent, even if API key is provided, Gemini is NOT called and local extractive summary is returned
    res_no_consent = client.post(
        "/api/v1/ai/summarize",
        json={
            "video_id": video_id_1,
            "api_key": "dummy-gemini-key",
            "consent_remote_ai": False,
        },
    )
    assert res_no_consent.status_code == 200
    data = res_no_consent.json()
    assert data["model_name"] == "extractive-grounded-local"
    mock_client_cls.assert_not_called()

    # 2. With explicit user consent, Gemini client is constructed
    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = MagicMock(
        text='{"summary": "Remote AI summary", "topics": ["test"], "chapters": []}'
    )
    mock_client_cls.return_value = mock_instance

    res_with_consent = client.post(
        "/api/v1/ai/summarize",
        json={
            "video_id": video_id_2,
            "api_key": "dummy-gemini-key",
            "consent_remote_ai": True,
        },
    )
    assert res_with_consent.status_code == 200
    data = res_with_consent.json()
    assert data["model_name"] == "gemini-2.5-flash"
    mock_client_cls.assert_called_once()


def test_ai_egress_consent_enforcement_for_qa(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)

    # Fetch seeded video ID
    videos = client.get("/api/v1/videos").json()
    video_id = videos[0]["id"]

    mock_genai = MagicMock()
    mock_client_cls = MagicMock()
    mock_genai.Client = mock_client_cls
    mock_google = MagicMock()
    mock_google.genai = mock_genai

    monkeypatch.setitem(sys.modules, "google", mock_google)
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)

    # 1. Without consent, Q&A runs in local extractive mode with remote_egress=False
    res = client.post(
        "/api/v1/ai/ask",
        json={
            "video_id": video_id,
            "query": "privacy and egress verification",
            "api_key": "dummy-gemini-key",
            "consent_remote_ai": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["remote_egress"] is False
    assert data["model_name"] == "grounded-extractive-local"
    mock_client_cls.assert_not_called()

    # 2. With consent, remote egress is allowed and declared
    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = MagicMock(
        text='{"answer": "Remote answer", "citations": [{"segment_id": 1, "start_time": 0.0, "end_time": 60.0, "quote": "test"}]}'
    )
    mock_client_cls.return_value = mock_instance

    res = client.post(
        "/api/v1/ai/ask",
        json={
            "video_id": video_id,
            "query": "privacy and egress verification",
            "api_key": "dummy-gemini-key",
            "consent_remote_ai": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["remote_egress"] is True
    assert data["model_name"] == "gemini-2.5-flash"
    assert data["provider"] == "google-gemini"
    assert data["consent_source"] == "request"
    assert "query" in data["egress_data_categories"]
    mock_client_cls.assert_called_once()


def test_default_server_binding_is_loopback() -> None:
    assert settings.API_HOST in ("127.0.0.1", "localhost", "::1")
    # Verify validation does not raise on standard loopback configuration
    validate_server_binding_and_security(host="127.0.0.1", auth_token=None)


def test_unsafe_network_binding_fails_startup() -> None:
    with pytest.raises(RuntimeError, match="Unsafe network binding"):
        validate_server_binding_and_security(host="0.0.0.0", auth_token=None)

    with pytest.raises(RuntimeError, match="Unsafe network binding"):
        validate_server_binding_and_security(host="192.168.1.100", auth_token="   ")

    with pytest.raises((RuntimeError, Exception)):
        Settings(API_HOST="0.0.0.0", API_AUTH_TOKEN="")


def test_safe_network_binding_with_auth_token_succeeds() -> None:
    validate_server_binding_and_security(host="0.0.0.0", auth_token="secure_token_123")
    cfg = Settings(API_HOST="0.0.0.0", API_AUTH_TOKEN="secure_token_123")
    assert cfg.API_HOST == "0.0.0.0"
    assert cfg.API_AUTH_TOKEN == "secure_token_123"


def test_constant_time_token_comparison_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "valid-secret-token")
    from fastapi.security import HTTPAuthorizationCredentials
    import secrets

    called_secrets = []
    real_compare = secrets.compare_digest

    def recording_compare(a, b):
        called_secrets.append((a, b))
        return real_compare(a, b)

    monkeypatch.setattr(secrets, "compare_digest", recording_compare)

    # Valid token
    require_api_auth(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-secret-token"),
        x_api_key=None,
    )
    assert len(called_secrets) == 1
    assert called_secrets[0] == ("valid-secret-token", "valid-secret-token")

    # Invalid token
    with pytest.raises(Exception):
        require_api_auth(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token"),
            x_api_key=None,
        )
    assert len(called_secrets) == 2


def test_ai_egress_consent_disclosure_and_revocation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)

    videos = client.get("/api/v1/videos").json()
    video_id = videos[0]["id"]

    mock_genai = MagicMock()
    mock_client_cls = MagicMock()
    mock_genai.Client = mock_client_cls
    mock_google = MagicMock()
    mock_google.genai = mock_genai

    monkeypatch.setitem(sys.modules, "google", mock_google)
    monkeypatch.setitem(sys.modules, "google.genai", mock_genai)

    mock_instance = MagicMock()
    mock_instance.models.generate_content.return_value = MagicMock(
        text='{"answer": "Remote answer", "citations": []}'
    )
    mock_client_cls.return_value = mock_instance

    # 1. First call with request consent -> remote egress permitted and disclosed
    res1 = client.post(
        "/api/v1/ai/ask",
        json={
            "video_id": video_id,
            "query": "privacy and egress verification",
            "api_key": "dummy-key",
            "consent_remote_ai": True,
        },
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["remote_egress"] is True
    assert d1["provider"] == "google-gemini"
    assert d1["consent_source"] == "request"
    assert "query" in d1["egress_data_categories"]

    # 2. Second call with revoked consent -> remote egress immediately blocked
    res2 = client.post(
        "/api/v1/ai/ask",
        json={
            "video_id": video_id,
            "query": "privacy and egress verification",
            "api_key": "dummy-key",
            "consent_remote_ai": False,
        },
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["remote_egress"] is False
    assert d2["provider"] == "local"
    assert d2["consent_source"] is None
    assert d2["egress_data_categories"] == []

    # 3. Third call with administrator persistent opt-in -> remote egress permitted with admin_setting source
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", True)
    res3 = client.post(
        "/api/v1/ai/ask",
        json={
            "video_id": video_id,
            "query": "privacy and egress verification",
            "api_key": "dummy-key",
            "consent_remote_ai": False,
        },
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert d3["remote_egress"] is True
    assert d3["provider"] == "google-gemini"
    assert d3["consent_source"] == "admin_setting"

    # 4. Fourth call with administrator opt-in revoked -> remote egress immediately blocked
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)
    res4 = client.post(
        "/api/v1/ai/ask",
        json={
            "video_id": video_id,
            "query": "privacy and egress verification",
            "api_key": "dummy-key",
            "consent_remote_ai": False,
        },
    )
    assert res4.status_code == 200
    d4 = res4.json()
    assert d4["remote_egress"] is False
    assert d4["provider"] == "local"
    assert d4["consent_source"] is None
