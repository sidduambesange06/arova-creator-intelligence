"""REST API routes for BYO-AI Gateway and Consent Management.

Exposes provider discovery, credential validation, model cataloging,
and scoped AI consent grants/revocations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.providers.gateway import get_ai_gateway
from app.database.session import get_db
from app.models.entities import AIConsent, AIRun

router = APIRouter(prefix="/api/v1/ai", tags=["ai-gateway"])


class VerifyProviderRequest(BaseModel):
    provider: str = Field(..., description="Provider identifier: google-gemini, openai, anthropic, local")
    api_key: str | None = Field(default=None, description="API key to test (optional if already configured)")
    base_url: str | None = Field(default=None, description="Custom base URL for OpenAI-compatible endpoints")


class CreateConsentRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=64)
    scope_type: str = Field(default="library", max_length=32)
    scope_id: str = Field(..., min_length=1, max_length=36)
    endpoint_host: str = Field(..., min_length=1, max_length=255)
    data_categories: list[str] = Field(default_factory=lambda: ["query", "transcript_snippets"])
    capabilities: list[str] = Field(default_factory=lambda: ["llm_qa", "summarization"])
    budget_limit: float | None = None
    expires_in_hours: int | None = None


class ConsentOut(BaseModel):
    id: str
    scope_type: str
    scope_id: str
    provider: str
    endpoint_host: str
    data_categories: list[str]
    capabilities: list[str]
    budget_limit: float | None
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    is_active: bool


class AIRunOut(BaseModel):
    id: str
    provider: str
    model: str
    execution_location: str
    data_categories: list[str]
    prompt_hash: str
    input_refs: list[str]
    consent_id: str | None


@router.get("/providers")
def list_ai_providers() -> dict[str, Any]:
    """List all registered AI providers, their capabilities, and available models."""
    gateway = get_ai_gateway()
    return {
        "providers": gateway.list_providers(),
        "models": [
            {
                "model_id": m.model_id,
                "provider_id": m.provider_id,
                "capabilities": [c.value for c in m.capabilities],
                "execution_location": m.execution_location.value,
                "description": m.description,
                "context_window": m.context_window,
                "is_default": m.is_default,
            }
            for m in gateway.list_models()
        ],
    }


@router.post("/providers/verify")
def verify_provider_credentials(payload: VerifyProviderRequest) -> dict[str, Any]:
    """Test credentials or connectivity for a given provider without executing pipeline jobs."""
    gateway = get_ai_gateway()
    try:
        provider = gateway.get_provider(payload.provider)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{payload.provider}' not recognized.",
        )

    is_valid, err = provider.validate_credentials(
        api_key=payload.api_key,
        base_url=payload.base_url,
    )
    return {
        "provider": payload.provider,
        "is_valid": is_valid,
        "error": err,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/consents", response_model=list[ConsentOut])
def list_ai_consents(
    provider: str | None = Query(default=None),
    scope_id: str | None = Query(default=None),
    include_revoked: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ConsentOut]:
    """List recorded AI consent grants."""
    query = db.query(AIConsent)
    if provider:
        query = query.filter(AIConsent.provider == provider)
    if scope_id:
        query = query.filter(AIConsent.scope_id == scope_id)
    if not include_revoked:
        query = query.filter(AIConsent.revoked_at.is_(None))

    now = datetime.now(timezone.utc)
    results = []
    for c in query.order_by(AIConsent.granted_at.desc()).all():
        exp = c.expires_at if (c.expires_at is None or c.expires_at.tzinfo) else c.expires_at.replace(tzinfo=timezone.utc)
        active = (c.revoked_at is None) and (exp is None or exp > now)

        try:
            data_cats = json.loads(c.data_categories)
        except Exception:
            data_cats = []
        try:
            caps = json.loads(c.capabilities)
        except Exception:
            caps = []

        results.append(
            ConsentOut(
                id=c.id,
                scope_type=c.scope_type,
                scope_id=c.scope_id,
                provider=c.provider,
                endpoint_host=c.endpoint_host,
                data_categories=data_cats,
                capabilities=caps,
                budget_limit=c.budget_limit,
                granted_at=c.granted_at,
                expires_at=c.expires_at,
                revoked_at=c.revoked_at,
                is_active=active,
            )
        )
    return results


@router.post("/consents", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
def grant_ai_consent(
    payload: CreateConsentRequest,
    db: Session = Depends(get_db),
) -> ConsentOut:
    """Grant an explicit, scoped AI consent record."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=payload.expires_in_hours) if payload.expires_in_hours else None

    consent = AIConsent(
        id=str(uuid.uuid4()),
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        provider=payload.provider,
        endpoint_host=payload.endpoint_host,
        data_categories=json.dumps(payload.data_categories),
        capabilities=json.dumps(payload.capabilities),
        budget_limit=payload.budget_limit,
        granted_at=now,
        expires_at=expires,
        revoked_at=None,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    return ConsentOut(
        id=consent.id,
        scope_type=consent.scope_type,
        scope_id=consent.scope_id,
        provider=consent.provider,
        endpoint_host=consent.endpoint_host,
        data_categories=payload.data_categories,
        capabilities=payload.capabilities,
        budget_limit=consent.budget_limit,
        granted_at=consent.granted_at,
        expires_at=consent.expires_at,
        revoked_at=None,
        is_active=True,
    )


@router.delete("/consents/{consent_id}")
def revoke_ai_consent(
    consent_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Revoke an existing AI consent grant immediately."""
    consent = db.query(AIConsent).filter_by(id=consent_id).first()
    if not consent:
        raise HTTPException(status_code=404, detail=f"Consent '{consent_id}' not found.")

    consent.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "revoked", "consent_id": consent_id, "revoked_at": consent.revoked_at.isoformat()}


@router.get("/runs", response_model=list[AIRunOut])
def list_ai_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AIRunOut]:
    """List recent AI run audit records with prompt hashes and data categories."""
    runs = db.query(AIRun).order_by(AIRun.id.desc()).limit(limit).all()
    results = []
    for r in runs:
        try:
            cats = json.loads(r.data_categories)
        except Exception:
            cats = []
        try:
            refs = json.loads(r.input_refs)
        except Exception:
            refs = []

        results.append(
            AIRunOut(
                id=r.id,
                provider=r.provider,
                model=r.model,
                execution_location=r.execution_location,
                data_categories=cats,
                prompt_hash=r.prompt_hash,
                input_refs=refs,
                consent_id=r.consent_id,
            )
        )
    return results
