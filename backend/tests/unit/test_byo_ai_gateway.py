"""Comprehensive tests for BYO-AI Provider Gateway, Consent Boundaries, and Provider Adapters."""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch
import urllib.error

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import (
    AICapability,
    AIResponse,
    ExecutionLocation,
    compute_prompt_hash,
    mask_secret,
)
from app.ai.providers.gateway import AIProviderGateway, get_ai_gateway
from app.ai.providers.gemini import GoogleGeminiProvider
from app.ai.providers.local import LocalExtractiveProvider
from app.ai.providers.openai_provider import OpenAICompatibleProvider, is_local_endpoint
from app.core.config import settings
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import AIConsent, AIRun, Transcript, TranscriptSegment, Video
from app.models.enums import ExecutionProfile, RootPolicy
from app.services.summary_service import answer_video_question, generate_video_summary


@pytest.fixture()
def db_session() -> Session:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()

    video = Video(
        filename="gateway_test.mp4",
        file_path="/tmp/gateway_test.mp4",
        file_hash="hash_gw_123",
        duration=120.0,
    )
    session.add(video)
    session.commit()

    transcript = Transcript(
        video_id=video.id,
        language="en",
        model_name="whisper-base",
        full_text="Artificial intelligence architecture requires clean abstractions and local-first privacy.",
    )
    session.add(transcript)
    session.commit()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        video_id=video.id,
        start_time=0.0,
        end_time=30.0,
        text="Artificial intelligence architecture requires clean abstractions and local-first privacy.",
        confidence=0.98,
    )
    session.add(seg)
    session.commit()

    from app.ai.providers.embeddings import index_video_chunks
    index_video_chunks(session, video.id)

    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# =========================================================================
# 1. Base Utilities & Secret Masking Tests
# =========================================================================

def test_mask_secret_masks_properly() -> None:
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    assert mask_secret("short") == "[REDACTED_SECRET]"
    assert mask_secret("sk-1234567890abcdef") == "sk-...cdef"
    assert "1234567890" not in mask_secret("sk-1234567890abcdef")


def test_compute_prompt_hash_is_deterministic() -> None:
    h1 = compute_prompt_hash("What is media intelligence?")
    h2 = compute_prompt_hash("What is media intelligence?")
    assert len(h1) == 64
    assert h1 == h2
    assert h1 != compute_prompt_hash("Different query")


# =========================================================================
# 2. Local Extractive Provider Tests
# =========================================================================

def test_local_provider_capabilities() -> None:
    local_prov = LocalExtractiveProvider()
    assert local_prov.is_available() is True
    assert local_prov.is_available(AICapability.LLM_QA) is True
    assert local_prov.is_available(AICapability.SUMMARIZATION) is True
    assert local_prov.execution_location == ExecutionLocation.LOCAL

    models = local_prov.list_models()
    assert len(models) >= 2
    model_ids = [m.model_id for m in models]
    assert "grounded-extractive-local" in model_ids
    assert "extractive-grounded-local" in model_ids

    # Text generation
    resp = local_prov.generate_text("Test prompt")
    assert resp.text == "Test prompt"
    assert resp.remote_egress is False
    assert resp.execution_location == ExecutionLocation.LOCAL

    # Structured JSON generation
    parsed, resp_json = local_prov.generate_structured_json(
        prompt="First sentence about technology. Second sentence about engineering. Third sentence about software."
    )
    assert "summary" in parsed
    assert "topics" in parsed
    assert "chapters" in parsed
    assert resp_json.remote_egress is False


# =========================================================================
# 3. Provider Adapters Endpoint & Credential Checks
# =========================================================================

def test_is_local_endpoint_detection() -> None:
    assert is_local_endpoint("http://localhost:11434/v1") is True
    assert is_local_endpoint("http://127.0.0.1:8000/v1") is True
    assert is_local_endpoint("https://api.openai.com/v1") is False
    assert is_local_endpoint("https://my-custom-server.internal:8080/v1") is False


def test_openai_provider_credential_validation() -> None:
    prov = OpenAICompatibleProvider()
    # Missing key for remote endpoint
    is_valid, err = prov.validate_credentials(api_key="", base_url="https://api.openai.com/v1")
    assert is_valid is False
    assert "API key is required" in str(err)

    # Mock successful remote validation
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        is_valid, err = prov.validate_credentials(api_key="sk-test-valid", base_url="https://api.openai.com/v1")
        assert is_valid is True
        assert err is None


def test_anthropic_provider_credential_validation() -> None:
    prov = AnthropicProvider()
    is_valid, err = prov.validate_credentials(api_key="")
    assert is_valid is False
    assert "API key is required" in str(err)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        is_valid, err = prov.validate_credentials(api_key="sk-ant-test-12345")
        assert is_valid is True
        assert err is None


def test_gemini_provider_credential_validation() -> None:
    prov = GoogleGeminiProvider()
    is_valid, err = prov.validate_credentials(api_key="")
    assert is_valid is False
    assert "API key is required" in str(err)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        is_valid, err = prov.validate_credentials(api_key="AIzaSyTestKey12345")
        assert is_valid is True
        assert err is None


# =========================================================================
# 4. Consent Evaluation Decision Matrix Tests
# =========================================================================

def test_consent_evaluation_rules(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = get_ai_gateway()
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)

    # 1. Local provider is always permitted
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="local",
        consent_remote_ai=False,
    )
    assert permitted is True
    assert source == "local_execution"

    # 2. Remote provider without consent is denied
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="google-gemini",
        consent_remote_ai=False,
    )
    assert permitted is False
    assert "No active consent" in str(source)

    # 3. Blocked by ExecutionProfile FULLY_OFFLINE_NO_AI
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="google-gemini",
        consent_remote_ai=True,
        execution_profile=ExecutionProfile.FULLY_OFFLINE_NO_AI,
    )
    assert permitted is False
    assert "Blocked by ExecutionProfile" in str(source)

    # 4. Blocked by ExecutionProfile LOCAL_AI
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=True,
        execution_profile=ExecutionProfile.LOCAL_AI,
    )
    assert permitted is False
    assert "Blocked by ExecutionProfile" in str(source)

    # 5. Blocked by RootPolicy LOCAL_ONLY
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=True,
        root_policy=RootPolicy.LOCAL_ONLY,
    )
    assert permitted is False
    assert "Blocked by RootPolicy" in str(source)

    # 6. Permitted by explicit request consent
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="google-gemini",
        consent_remote_ai=True,
    )
    assert permitted is True
    assert source == "request"

    # 7. Permitted by system admin setting
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", True)
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="anthropic",
        consent_remote_ai=False,
    )
    assert permitted is True
    assert source == "admin_setting"
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)

    # 8. Permitted by active database consent
    consent = AIConsent(
        scope_type="library",
        scope_id="lib_123",
        provider="openai",
        endpoint_host="api.openai.com",
        data_categories='["query"]',
        capabilities='["llm_qa", "summarization"]',
        granted_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(consent)
    db_session.commit()

    permitted, source, consent_rec = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=False,
        scope_id="lib_123",
    )
    assert permitted is True
    assert source == "db_consent"
    assert consent_rec.id == consent.id

    # 9. Denied if database consent is revoked
    consent.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=False,
        scope_id="lib_123",
    )
    assert permitted is False


# =========================================================================
# 5. Remote Provider Generation & Fallback Execution
# =========================================================================

def test_remote_generation_with_mock_openai(db_session: Session) -> None:
    gateway = get_ai_gateway()

    mock_resp_payload = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "OpenAI answer citing [00:10 - 00:20]."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        resp, consent_src = gateway.generate_llm_response(
            prompt="Analyze the video",
            capability=AICapability.LLM_QA,
            preferred_provider="openai",
            api_key="sk-test-openai-12345",
            consent_remote_ai=True,
            db=db_session,
            input_refs=["video:gw_123"],
        )
        assert resp.text == "OpenAI answer citing [00:10 - 00:20]."
        assert resp.provider == "openai"
        assert resp.remote_egress is True
        assert resp.prompt_tokens == 50
        assert resp.total_tokens == 65
        assert consent_src == "request"

        # Verify AIRun recorded in database
        run = db_session.query(AIRun).filter_by(provider="openai").first()
        assert run is not None
        assert run.model == "gpt-4o-mini"
        assert run.execution_location == "remote"
        assert len(run.prompt_hash) == 64


def test_remote_generation_fallback_on_network_failure(db_session: Session) -> None:
    gateway = get_ai_gateway()

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        resp, consent_src = gateway.generate_llm_response(
            prompt="Analyze the video text",
            capability=AICapability.LLM_QA,
            preferred_provider="openai",
            api_key="sk-test-fail-12345",
            consent_remote_ai=True,
            db=db_session,
        )
        # Should gracefully fallback to local provider
        assert resp.provider == "local"
        assert resp.remote_egress is False
        assert resp.execution_location == ExecutionLocation.LOCAL


# =========================================================================
# 6. REST API Endpoints Verification
# =========================================================================

def test_api_list_providers(client: TestClient) -> None:
    res = client.get("/api/v1/ai/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert "models" in data
    prov_ids = [p["provider_id"] for p in data["providers"]]
    assert "local" in prov_ids
    assert "google-gemini" in prov_ids
    assert "openai" in prov_ids
    assert "anthropic" in prov_ids


def test_api_verify_provider_endpoint(client: TestClient) -> None:
    # Verify local
    res = client.post("/api/v1/ai/providers/verify", json={"provider": "local"})
    assert res.status_code == 200
    assert res.json()["is_valid"] is True

    # Verify invalid provider
    res_bad = client.post("/api/v1/ai/providers/verify", json={"provider": "non-existent"})
    assert res_bad.status_code == 404

    # Verify remote without key
    res_nokey = client.post("/api/v1/ai/providers/verify", json={"provider": "openai", "api_key": ""})
    assert res_nokey.status_code == 200
    assert res_nokey.json()["is_valid"] is False


def test_api_consent_crud_lifecycle(client: TestClient) -> None:
    # 1. Grant consent
    create_payload = {
        "provider": "google-gemini",
        "scope_type": "library",
        "scope_id": "lib_test_001",
        "endpoint_host": "generativelanguage.googleapis.com",
        "data_categories": ["query", "transcript_snippets"],
        "capabilities": ["llm_qa"],
        "budget_limit": 5.0,
        "expires_in_hours": 24,
    }
    grant_res = client.post("/api/v1/ai/consents", json=create_payload)
    assert grant_res.status_code == 201
    consent_id = grant_res.json()["id"]
    assert grant_res.json()["is_active"] is True

    # 2. List consents
    list_res = client.get("/api/v1/ai/consents?provider=google-gemini")
    assert list_res.status_code == 200
    consents = list_res.json()
    assert len(consents) >= 1
    assert any(c["id"] == consent_id for c in consents)

    # 3. Revoke consent
    revoke_res = client.delete(f"/api/v1/ai/consents/{consent_id}")
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    # 4. List without revoked
    active_res = client.get("/api/v1/ai/consents?include_revoked=false")
    assert not any(c["id"] == consent_id for c in active_res.json())


# =========================================================================
# 7. Backward Compatibility Integration with summary_service
# =========================================================================

def test_summary_service_backward_compatibility(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)
    vid = db_session.query(Video).first()

    # answer_video_question offline local
    ans = answer_video_question(
        db=db_session,
        query="What is local-first privacy?",
        video_id=vid.id,
        consent_remote_ai=False,
    )
    assert ans["remote_egress"] is False
    assert ans["provider"] == "local"
    assert ans["model_name"] == "grounded-extractive-local"
    assert len(ans["citations"]) >= 1

    # generate_video_summary offline local
    summary = generate_video_summary(
        db=db_session,
        video_id=vid.id,
        consent_remote_ai=False,
    )
    assert summary.video_id == vid.id
    assert "extractive" in summary.model_name
    assert json.loads(summary.topics_json)
    assert json.loads(summary.chapters_json)


# =========================================================================
# 8. M1.1 Consent-Source & 5-Gate Enforcement Regression Tests
# =========================================================================


def _link_video_to_policy_root(
    db: Session,
    video: Video,
    execution_profile: ExecutionProfile,
    root_policy: RootPolicy,
    suffix: str,
) -> tuple[str, str]:
    from app.models.entities import Asset, AssetLocation, AssetVersion, Library, LibraryRoot
    from app.models.enums import IdentityState, LocationAvailability, RootType

    lib = Library(
        id=f"lib_{suffix}",
        label=f"Library {suffix}",
        execution_profile=execution_profile.value,
    )
    root = LibraryRoot(
        id=f"root_{suffix}",
        library_id=lib.id,
        label=f"Root {suffix}",
        root_type=RootType.LOCAL_FIXED.value,
        policy=root_policy.value,
        status="active",
    )
    asset = Asset(id=f"asset_{suffix}")
    version = AssetVersion(
        id=f"ver_{suffix}",
        asset_id=asset.id,
        sha256=None,
        size_bytes=1024,
        identity_state=IdentityState.IDENTITY_UNVERIFIED.value,
    )
    loc = AssetLocation(
        id=f"loc_{suffix}",
        version_id=version.id,
        root_id=root.id,
        rel_path=video.filename,
        rel_path_norm=video.filename.lower(),
        availability=LocationAvailability.AVAILABLE.value,
    )
    db.add_all([lib, root, asset, version, loc])
    db.flush()
    asset.current_version_id = version.id
    video.asset_id = asset.id
    video.version_id = version.id
    db.commit()
    return lib.id, root.id


def _create_extra_video(db: Session, suffix: str) -> Video:
    from app.ai.providers.embeddings import index_video_chunks

    vid = Video(
        filename=f"consent_{suffix}.mp4",
        file_path=f"/tmp/consent_{suffix}.mp4",
        file_hash=f"hash_consent_{suffix}",
        duration=60.0,
    )
    db.add(vid)
    db.commit()

    tr = Transcript(
        video_id=vid.id,
        language="en",
        model_name="whisper-base",
        full_text="Privacy boundaries ensure remote AI never runs without valid explicit consent.",
    )
    db.add(tr)
    db.commit()

    seg = TranscriptSegment(
        transcript_id=tr.id,
        video_id=vid.id,
        start_time=0.0,
        end_time=30.0,
        text="Privacy boundaries ensure remote AI never runs without valid explicit consent.",
        confidence=0.98,
    )
    db.add(seg)
    db.commit()
    index_video_chunks(db, vid.id)
    return vid


def test_m1_summarize_and_ask_consent_source_all_scenarios(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy-gemini-env-key")

    mock_gemini_resp = (
        {
            "summary": "Grounded remote summary text.",
            "topics": ["Privacy", "Consent"],
            "chapters": [{"start_time": 0.0, "title": "Intro"}],
        },
        AIResponse(
            text='{"summary": "Grounded remote summary text."}',
            provider="google-gemini",
            model_name="gemini-2.5-flash",
            execution_location=ExecutionLocation.REMOTE,
            remote_egress=True,
            data_categories_egressed=["transcript", "video_metadata"],
        ),
    )

    with (
        patch("app.ai.providers.gemini.GoogleGeminiProvider.generate_structured_json", return_value=mock_gemini_resp),
        patch(
            "app.ai.providers.gemini.GoogleGeminiProvider.generate_text",
            return_value=AIResponse(
                text="Remote grounded answer [0:00 - 0:30].",
                provider="google-gemini",
                model_name="gemini-2.5-flash",
                execution_location=ExecutionLocation.REMOTE,
                remote_egress=True,
                data_categories_egressed=["query", "video_transcript_snippets"],
            ),
        ),
    ):
        # 1. No consent record -> local fallback, consent_source=None
        vid1 = _create_extra_video(db_session, "no_consent")
        res1 = client.post("/api/v1/ai/summarize", json={"video_id": vid1.id, "consent_remote_ai": False})
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["remote_egress"] is False
        assert d1["provider"] == "local"
        assert d1["consent_source"] is None
        assert d1["egress_data_categories"] == []

        # 2. Active valid DB AIConsent -> remote execution with consent_source='db_consent'
        vid2 = _create_extra_video(db_session, "active_db")
        active_grant = AIConsent(
            scope_type="video",
            scope_id=vid2.id,
            provider="google-gemini",
            endpoint_host="generativelanguage.googleapis.com",
            data_categories=json.dumps(["transcript", "video_metadata", "query", "video_transcript_snippets"]),
            capabilities=json.dumps(["summarization", "llm_qa"]),
            granted_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db_session.add(active_grant)
        db_session.commit()

        res2_sum = client.post("/api/v1/ai/summarize", json={"video_id": vid2.id, "consent_remote_ai": False})
        assert res2_sum.status_code == 200
        d2_sum = res2_sum.json()
        assert d2_sum["remote_egress"] is True
        assert d2_sum["provider"] == "google-gemini"
        assert d2_sum["consent_source"] == "db_consent"
        assert d2_sum["egress_data_categories"]

        # Re-invoking summarize on the same cached remote video WITHOUT consent must NOT claim egress on this call
        db_session.delete(active_grant)
        db_session.commit()
        res2_cached_denied = client.post("/api/v1/ai/summarize", json={"video_id": vid2.id, "consent_remote_ai": False})
        assert res2_cached_denied.status_code == 200
        d2_cached = res2_cached_denied.json()
        assert d2_cached["remote_egress"] is False
        assert d2_cached["provider"] == "local"
        assert d2_cached["consent_source"] is None

        # Restore active grant for ask verification
        active_grant_ask = AIConsent(
            scope_type="video",
            scope_id=vid2.id,
            provider="google-gemini",
            endpoint_host="generativelanguage.googleapis.com",
            data_categories=json.dumps(["query", "video_transcript_snippets"]),
            capabilities=json.dumps(["summarization", "llm_qa"]),
            granted_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db_session.add(active_grant_ask)
        db_session.commit()
        res2_ask = client.post(
            "/api/v1/ai/ask",
            json={"video_id": vid2.id, "query": "privacy boundaries", "consent_remote_ai": False},
        )
        assert res2_ask.status_code == 200
        assert res2_ask.json()["remote_egress"] is True
        assert res2_ask.json()["consent_source"] == "db_consent"

        # 3. Expired DB AIConsent -> denied, falls back to local
        vid3 = _create_extra_video(db_session, "expired_db")
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid3.id,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["transcript"]),
                capabilities=json.dumps(["summarization", "llm_qa"]),
                granted_at=datetime.now(timezone.utc) - timedelta(days=2),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        db_session.commit()
        res3 = client.post("/api/v1/ai/summarize", json={"video_id": vid3.id, "consent_remote_ai": False})
        assert res3.status_code == 200
        assert res3.json()["remote_egress"] is False
        assert res3.json()["consent_source"] is None

        # 4. Revoked DB AIConsent -> denied, falls back to local
        vid4 = _create_extra_video(db_session, "revoked_db")
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid4.id,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["transcript"]),
                capabilities=json.dumps(["summarization", "llm_qa"]),
                granted_at=datetime.now(timezone.utc) - timedelta(hours=2),
                revoked_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        )
        db_session.commit()
        res4 = client.post("/api/v1/ai/summarize", json={"video_id": vid4.id, "consent_remote_ai": False})
        assert res4.status_code == 200
        assert res4.json()["remote_egress"] is False
        assert res4.json()["consent_source"] is None

        # 5. Wrong provider or wrong scope -> denied for target video
        vid5 = _create_extra_video(db_session, "wrong_scope")
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id="non-matching-video-id",
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["transcript"]),
                capabilities=json.dumps(["summarization", "llm_qa"]),
                granted_at=datetime.now(timezone.utc),
            )
        )
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid5.id,
                provider="openai",
                endpoint_host="api.openai.com",
                data_categories=json.dumps(["transcript"]),
                capabilities=json.dumps(["summarization", "llm_qa"]),
                granted_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        res5 = client.post(
            "/api/v1/ai/summarize",
            json={"video_id": vid5.id, "provider": "google-gemini", "consent_remote_ai": False},
        )
        assert res5.status_code == 200
        assert res5.json()["remote_egress"] is False
        assert res5.json()["consent_source"] is None

        # 6. Conflicting grants (one revoked + one active valid) -> active valid succeeds with db_consent
        vid6 = _create_extra_video(db_session, "conflicting")
        db_session.add_all(
            [
                AIConsent(
                    scope_type="video",
                    scope_id=vid6.id,
                    provider="google-gemini",
                    endpoint_host="generativelanguage.googleapis.com",
                    data_categories=json.dumps(["transcript"]),
                    capabilities=json.dumps(["summarization"]),
                    granted_at=datetime.now(timezone.utc) - timedelta(hours=3),
                    revoked_at=datetime.now(timezone.utc) - timedelta(hours=1),
                ),
                AIConsent(
                    scope_type="video",
                    scope_id=vid6.id,
                    provider="google-gemini",
                    endpoint_host="generativelanguage.googleapis.com",
                    data_categories=json.dumps(["transcript"]),
                    capabilities=json.dumps(["summarization"]),
                    granted_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
                ),
            ]
        )
        db_session.commit()
        res6 = client.post("/api/v1/ai/summarize", json={"video_id": vid6.id, "consent_remote_ai": False})
        assert res6.status_code == 200
        assert res6.json()["remote_egress"] is True
        assert res6.json()["consent_source"] == "db_consent"

        # 7. ExecutionProfile local-only blocks remote egress even with consent_remote_ai=True
        vid7 = _create_extra_video(db_session, "offline_profile")
        _link_video_to_policy_root(
            db_session,
            vid7,
            ExecutionProfile.FULLY_OFFLINE_NO_AI,
            RootPolicy.ALLOW_REMOTE,
            "offline_prof",
        )
        res7 = client.post(
            "/api/v1/ai/summarize",
            json={"video_id": vid7.id, "api_key": "secret-gemini-key", "consent_remote_ai": True},
        )
        assert res7.status_code == 200
        assert res7.json()["remote_egress"] is False
        assert res7.json()["provider"] == "local"
        assert res7.json()["consent_source"] is None

        res7_ask = client.post(
            "/api/v1/ai/ask",
            json={
                "video_id": vid7.id,
                "query": "privacy boundaries",
                "api_key": "secret-gemini-key",
                "consent_remote_ai": True,
            },
        )
        assert res7_ask.status_code == 200
        assert res7_ask.json()["remote_egress"] is False
        assert res7_ask.json()["consent_source"] is None

        # 8. RootPolicy.LOCAL_ONLY blocks remote egress even with BYOK_REMOTE_AI + consent_remote_ai=True
        vid8 = _create_extra_video(db_session, "local_root")
        _link_video_to_policy_root(
            db_session,
            vid8,
            ExecutionProfile.BYOK_REMOTE_AI,
            RootPolicy.LOCAL_ONLY,
            "local_root_pol",
        )
        res8 = client.post(
            "/api/v1/ai/summarize",
            json={"video_id": vid8.id, "api_key": "secret-gemini-key", "consent_remote_ai": True},
        )
        assert res8.status_code == 200
        assert res8.json()["remote_egress"] is False
        assert res8.json()["provider"] == "local"
        assert res8.json()["consent_source"] is None

        # 10. Authorized remote execution with request consent + zero API key leakage in audit log
        vid10 = _create_extra_video(db_session, "req_auth")
        _link_video_to_policy_root(
            db_session,
            vid10,
            ExecutionProfile.BYOK_REMOTE_AI,
            RootPolicy.ALLOW_REMOTE,
            "allow_all_pol",
        )
        res10 = client.post(
            "/api/v1/ai/summarize",
            json={"video_id": vid10.id, "api_key": "super-secret-leak-check-key", "consent_remote_ai": True},
        )
        assert res10.status_code == 200
        d10 = res10.json()
        assert d10["remote_egress"] is True
        assert d10["provider"] == "google-gemini"
        assert d10["consent_source"] == "request"
        assert "super-secret-leak-check-key" not in res10.text
        runs = db_session.query(AIRun).all()
        assert all("super-secret-leak-check-key" not in (r.input_refs or "") for r in runs)


def test_m1_provider_missing_capability_and_loopback_consent_source(db_session: Session) -> None:
    gateway = get_ai_gateway()

    # 9. Provider execution blocked by missing capability
    permitted, reason, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.ASR,
        provider_id="google-gemini",
        consent_remote_ai=True,
    )
    assert permitted is False
    assert "does not support capability" in str(reason)

    # Localhost OpenAI-compatible provider has remote_egress=False -> consent_source must be None
    mock_local_resp = {
        "choices": [{"message": {"role": "assistant", "content": "Ollama local answer."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_local_resp).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        resp, consent_src = gateway.generate_llm_response(
            prompt="Summarize locally",
            capability=AICapability.LLM_QA,
            preferred_provider="openai",
            base_url="http://localhost:11434/v1",
            consent_remote_ai=True,
            db=db_session,
        )
        assert resp.remote_egress is False
        assert consent_src is None


def _create_video_with_text(db: Session, suffix: str, text: str) -> Video:
    from app.ai.providers.embeddings import index_video_chunks

    vid = Video(
        filename=f"extra_{suffix}.mp4",
        file_path=f"/tmp/extra_{suffix}.mp4",
        file_hash=f"hash_extra_{suffix}",
        duration=60.0,
    )
    db.add(vid)
    db.commit()

    tr = Transcript(
        video_id=vid.id,
        language="en",
        model_name="whisper-base",
        full_text=text,
    )
    db.add(tr)
    db.commit()

    seg = TranscriptSegment(
        transcript_id=tr.id,
        video_id=vid.id,
        start_time=0.0,
        end_time=30.0,
        text=text,
        confidence=0.98,
    )
    db.add(seg)
    db.commit()
    index_video_chunks(db, vid.id)
    return vid


def test_m1_consent_scopes_budget_categories_and_multivideo_policy(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "dummy-gemini-env-key")

    mock_sum = (
        {
            "summary": "Scoped remote summary.",
            "topics": ["Scope"],
            "chapters": [{"start_time": 0.0, "title": "Start"}],
        },
        AIResponse(
            text='{"summary": "Scoped remote summary."}',
            provider="google-gemini",
            model_name="gemini-2.5-flash",
            execution_location=ExecutionLocation.REMOTE,
            remote_egress=True,
            data_categories_egressed=["transcript", "video_metadata"],
        ),
    )
    mock_ask = AIResponse(
        text="Scoped remote answer [0:00 - 0:30].",
        provider="google-gemini",
        model_name="gemini-2.5-flash",
        execution_location=ExecutionLocation.REMOTE,
        remote_egress=True,
        data_categories_egressed=["query", "video_transcript_snippets"],
    )

    with (
        patch("app.ai.providers.gemini.GoogleGeminiProvider.generate_structured_json", return_value=mock_sum),
        patch("app.ai.providers.gemini.GoogleGeminiProvider.generate_text", return_value=mock_ask),
    ):
        # 1. Asset, version, root, library, and global consent scopes
        for scope_type in ("asset", "version", "root", "library", "global"):
            vid = _create_extra_video(db_session, f"scope_{scope_type}")
            lib_id, root_id = _link_video_to_policy_root(
                db_session,
                vid,
                ExecutionProfile.BYOK_REMOTE_AI,
                RootPolicy.ALLOW_REMOTE,
                f"scope_{scope_type}",
            )
            scope_target = {
                "asset": vid.asset_id,
                "version": vid.version_id,
                "root": root_id,
                "library": lib_id,
                "global": "*",
            }[scope_type]
            grant = AIConsent(
                scope_type=scope_type,
                scope_id=scope_target,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["transcript", "query", "video_transcript_snippets"]),
                capabilities=json.dumps(["summarization", "llm_qa"]),
                granted_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
            )
            db_session.add(grant)
            db_session.commit()

            r_sum = client.post("/api/v1/ai/summarize", json={"video_id": vid.id, "consent_remote_ai": False})
            assert r_sum.status_code == 200
            assert r_sum.json()["remote_egress"] is True, f"summarize failed for scope_type={scope_type}"
            assert r_sum.json()["consent_source"] == "db_consent"

            r_ask = client.post(
                "/api/v1/ai/ask",
                json={"video_id": vid.id, "query": "privacy boundaries", "consent_remote_ai": False},
            )
            assert r_ask.status_code == 200
            assert r_ask.json()["remote_egress"] is True, f"ask failed for scope_type={scope_type}"
            assert r_ask.json()["consent_source"] == "db_consent"

            # Revoke so a global grant does not spill into later assertions
            grant.revoked_at = datetime.now(timezone.utc)
            db_session.commit()

        # 2. Exhausted budget (budget_limit=0.0) denies remote egress
        vid_budget = _create_extra_video(db_session, "budget_zero")
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid_budget.id,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["transcript", "query", "video_transcript_snippets"]),
                capabilities=json.dumps(["summarization", "llm_qa"]),
                budget_limit=0.0,
                granted_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        r_budget_sum = client.post("/api/v1/ai/summarize", json={"video_id": vid_budget.id, "consent_remote_ai": False})
        assert r_budget_sum.status_code == 200
        assert r_budget_sum.json()["remote_egress"] is False
        assert r_budget_sum.json()["consent_source"] is None

        r_budget_ask = client.post(
            "/api/v1/ai/ask",
            json={"video_id": vid_budget.id, "query": "privacy boundaries", "consent_remote_ai": False},
        )
        assert r_budget_ask.status_code == 200
        assert r_budget_ask.json()["remote_egress"] is False

        # 3. Disallowed data_categories denies remote egress
        vid_cat = _create_extra_video(db_session, "disallowed_cats")
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid_cat.id,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["metadata_only"]),
                capabilities=json.dumps(["summarization", "llm_qa"]),
                granted_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        r_cat_sum = client.post("/api/v1/ai/summarize", json={"video_id": vid_cat.id, "consent_remote_ai": False})
        assert r_cat_sum.status_code == 200
        assert r_cat_sum.json()["remote_egress"] is False

        vid_query_only = _create_extra_video(db_session, "query_only_cat")
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid_query_only.id,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["query"]),
                capabilities=json.dumps(["llm_qa"]),
                granted_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
        r_cat_ask = client.post(
            "/api/v1/ai/ask",
            json={"video_id": vid_query_only.id, "query": "privacy boundaries", "consent_remote_ai": False},
        )
        assert r_cat_ask.status_code == 200
        assert r_cat_ask.json()["remote_egress"] is False

        # 4. Multi-video ask: one ALLOW_REMOTE video + one LOCAL_ONLY video -> blocked
        vid_allow = _create_video_with_text(
            db_session,
            "mv_allow",
            "uniquemultivideotoken allows remote analysis on allowed root.",
        )
        _link_video_to_policy_root(
            db_session,
            vid_allow,
            ExecutionProfile.BYOK_REMOTE_AI,
            RootPolicy.ALLOW_REMOTE,
            "mv_allow",
        )
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid_allow.id,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["query", "video_transcript_snippets"]),
                capabilities=json.dumps(["llm_qa"]),
                granted_at=datetime.now(timezone.utc),
            )
        )
        vid_local = _create_video_with_text(
            db_session,
            "mv_local",
            "uniquemultivideotoken stays local on local_only root.",
        )
        _link_video_to_policy_root(
            db_session,
            vid_local,
            ExecutionProfile.BYOK_REMOTE_AI,
            RootPolicy.LOCAL_ONLY,
            "mv_local",
        )
        db_session.commit()

        r_mv = client.post(
            "/api/v1/ai/ask",
            json={"video_id": None, "query": "uniquemultivideotoken", "consent_remote_ai": True},
        )
        assert r_mv.status_code == 200
        assert r_mv.json()["remote_egress"] is False
        assert r_mv.json()["provider"] == "local"
        assert r_mv.json()["consent_source"] is None

        # 5. Multi-video ask without request consent: vid_allow has video-scope consent,
        # vid_unconsented is in another ALLOW_REMOTE root without consent -> scope intersection blocks egress
        vid_allow_iso = _create_video_with_text(
            db_session,
            "mv_iso_allow",
            "uniquescopeintersecttoken allows video1 only.",
        )
        _link_video_to_policy_root(
            db_session,
            vid_allow_iso,
            ExecutionProfile.BYOK_REMOTE_AI,
            RootPolicy.ALLOW_REMOTE,
            "mv_iso_allow",
        )
        db_session.add(
            AIConsent(
                scope_type="video",
                scope_id=vid_allow_iso.id,
                provider="google-gemini",
                endpoint_host="generativelanguage.googleapis.com",
                data_categories=json.dumps(["query", "video_transcript_snippets"]),
                capabilities=json.dumps(["llm_qa"]),
                granted_at=datetime.now(timezone.utc),
            )
        )
        vid_unconsented = _create_video_with_text(
            db_session,
            "mv_iso_unconsented",
            "uniquescopeintersecttoken has no consent on video2.",
        )
        _link_video_to_policy_root(
            db_session,
            vid_unconsented,
            ExecutionProfile.BYOK_REMOTE_AI,
            RootPolicy.ALLOW_REMOTE,
            "mv_iso_unconsented",
        )
        db_session.commit()

        r_iso = client.post(
            "/api/v1/ai/ask",
            json={"video_id": None, "query": "uniquescopeintersecttoken", "consent_remote_ai": False},
        )
        assert r_iso.status_code == 200
        assert r_iso.json()["remote_egress"] is False
        assert r_iso.json()["consent_source"] is None


def test_m1_ask_loopback_openai_compatible_executes_locally(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "")
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)
    vid = _create_extra_video(db_session, "loopback_ask")

    mock_local_resp = {
        "choices": [{"message": {"role": "assistant", "content": "Ollama local grounded answer."}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_local_resp).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = client.post(
            "/api/v1/ai/ask",
            json={
                "video_id": vid.id,
                "query": "privacy boundaries",
                "provider": "openai",
                "base_url": "http://localhost:11434/v1",
                "consent_remote_ai": True,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == "Ollama local grounded answer."
        assert data["remote_egress"] is False
        assert data["provider"] == "local"
        assert data["consent_source"] is None
        assert data["egress_data_categories"] == []



