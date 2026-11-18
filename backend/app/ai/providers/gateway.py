"""BYO-AI Provider Gateway and Capability Router for Arova Creator Intelligence.

Coordinates local and remote AI providers (Local, Google Gemini, OpenAI-compatible, Anthropic).
Enforces:
1. Strict local-first offline priority.
2. Non-bypassable consent gates (ExecutionProfile, RootPolicy, AIConsent, AI_REMOTE_CONSENT).
3. Secure credential management and masking (zero plaintext keys logged or stored).
4. Durable provenance and audit trail recording via AIRun.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import (
    AICapability,
    AIModelInfo,
    AIResponse,
    BaseAIProvider,
    ExecutionLocation,
    LLMCapableProvider,
    compute_prompt_hash,
    mask_secret,
)
from app.ai.providers.gemini import GoogleGeminiProvider
from app.ai.providers.local import LocalExtractiveProvider
from app.ai.providers.openai_provider import OpenAICompatibleProvider
from app.core.config import settings
from app.models.entities import AIConsent, AIRun
from app.models.enums import ExecutionProfile, RootPolicy

logger = logging.getLogger(__name__)


class ConsentDeniedError(PermissionError):
    """Raised when an operation requiring remote AI lacks valid user consent or is blocked by policy."""
    pass


class AIProviderGateway:
    """Central gateway and coordinator for all AI operations."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseAIProvider] = {}
        # Register default providers
        self.register_provider(LocalExtractiveProvider())
        self.register_provider(GoogleGeminiProvider())
        self.register_provider(OpenAICompatibleProvider())
        self.register_provider(AnthropicProvider())

    def register_provider(self, provider: BaseAIProvider) -> None:
        """Register or override an AI provider."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> BaseAIProvider:
        """Retrieve provider by ID."""
        if provider_id not in self._providers:
            raise KeyError(f"AI provider '{provider_id}' is not registered")
        return self._providers[provider_id]

    def list_providers(self) -> list[dict[str, Any]]:
        """List all registered providers with capability status."""
        result = []
        for pid, prov in self._providers.items():
            result.append(
                {
                    "provider_id": pid,
                    "provider_name": prov.provider_name,
                    "execution_location": prov.execution_location.value,
                    "is_available": prov.is_available(),
                    "capabilities": [c.value for c in prov.supported_capabilities],
                    "models": [m.model_id for m in prov.list_models()],
                }
            )
        return result

    def list_models(self) -> list[AIModelInfo]:
        """List all models across all registered providers."""
        models: list[AIModelInfo] = []
        for prov in self._providers.values():
            models.extend(prov.list_models())
        return models

    def evaluate_consent(
        self,
        db: Session | None,
        capability: AICapability,
        provider_id: str,
        consent_remote_ai: bool = False,
        execution_profile: ExecutionProfile | str | None = None,
        root_policy: RootPolicy | str | None = None,
        scope_id: str | set[str] | list[str] | tuple[str, ...] | None = None,
        data_categories: list[str] | None = None,
    ) -> tuple[bool, str | None, AIConsent | None]:
        """Evaluate whether execution is permitted according to the 5-gate precedence rule.

        Returns: (is_permitted, consent_source_or_rejection_reason, matched_consent_record_or_none)
        """
        provider_id = (provider_id or "").strip().lower()
        prov = self._providers.get(provider_id)
        if prov is None:
            return False, f"Provider '{provider_id}' is not registered", None
        if capability not in getattr(prov, "supported_capabilities", set()):
            return False, f"Provider '{provider_id}' does not support capability '{capability.value}'", None

        # Gate 1 / Rule 1: Local provider is always permitted (zero remote egress)
        if provider_id == "local":
            return True, "local_execution", None

        # Rule 2: Execution profile check
        if execution_profile:
            ep = ExecutionProfile(execution_profile) if isinstance(execution_profile, str) else execution_profile
            if ep in (ExecutionProfile.FULLY_OFFLINE_NO_AI, ExecutionProfile.LOCAL_AI):
                return False, f"Blocked by ExecutionProfile '{ep.value}' (local-only)", None

        # Rule 3: Root policy check
        if root_policy:
            rp = RootPolicy(root_policy) if isinstance(root_policy, str) else root_policy
            if rp == RootPolicy.LOCAL_ONLY:
                return False, "Blocked by RootPolicy 'local_only'", None

        # Rule 4: Explicit request-level consent
        if consent_remote_ai:
            return True, "request", None

        # Rule 5: System-wide admin setting
        if settings.AI_REMOTE_CONSENT:
            return True, "admin_setting", None

        # Rule 6: Database AIConsent records
        if db is not None:
            now = datetime.now(timezone.utc)
            query = db.query(AIConsent).filter(
                AIConsent.provider == provider_id,
                AIConsent.revoked_at.is_(None),
            )
            allowed_scopes: set[str] | None = None
            if isinstance(scope_id, str):
                allowed_scopes = {scope_id, "*", "global"}
            elif scope_id is not None:
                allowed_scopes = {str(s) for s in scope_id if s} | {"*", "global"}

            for record in query.order_by(AIConsent.granted_at.desc()).all():
                if record.expires_at:
                    exp = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
                    if exp <= now:
                        continue  # Expired
                if allowed_scopes is not None and record.scope_type != "global" and record.scope_id not in allowed_scopes:
                    continue
                if record.budget_limit is not None and record.budget_limit <= 0:
                    continue

                try:
                    caps = json.loads(record.capabilities)
                except Exception:
                    continue
                if capability.value not in caps and "*" not in caps:
                    continue

                if data_categories:
                    try:
                        rec_cats = set(json.loads(record.data_categories or "[]"))
                    except Exception:
                        continue
                    if not rec_cats:
                        continue
                    transcript_aliases = {"transcript", "video_transcript_snippets", "transcript_snippets"}
                    if rec_cats & transcript_aliases:
                        rec_cats = rec_cats | transcript_aliases
                    if "*" not in rec_cats and not all(c in rec_cats for c in data_categories):
                        continue

                return True, "db_consent", record

        return False, "No active consent granted for remote AI egress", None

    def record_run(
        self,
        db: Session | None,
        provider_id: str,
        model_name: str,
        execution_location: ExecutionLocation,
        data_categories: list[str],
        prompt: str,
        input_refs: list[str] | None = None,
        consent_id: str | None = None,
    ) -> AIRun | None:
        """Record an immutable AIRun audit record with SHA-256 prompt hash and zero plaintext credentials."""
        if db is None:
            return None

        try:
            run_record = AIRun(
                id=str(uuid.uuid4()),
                provider=provider_id,
                model=model_name,
                execution_location=execution_location.value,
                data_categories=json.dumps(data_categories),
                prompt_hash=compute_prompt_hash(prompt),
                input_refs=json.dumps(input_refs or []),
                consent_id=consent_id,
            )
            db.add(run_record)
            db.commit()
            return run_record
        except Exception as exc:
            logger.warning("Failed to record AIRun audit log: %s", exc)
            return None

    def generate_llm_response(
        self,
        prompt: str,
        system_instruction: str | None = None,
        capability: AICapability = AICapability.LLM_QA,
        preferred_provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        consent_remote_ai: bool = False,
        execution_profile: ExecutionProfile | str | None = None,
        root_policy: RootPolicy | str | None = None,
        scope_id: str | set[str] | list[str] | tuple[str, ...] | None = None,
        data_categories: list[str] | None = None,
        db: Session | None = None,
        input_refs: list[str] | None = None,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> tuple[AIResponse, str | None]:
        """Execute an LLM generation with consent evaluation, fallback routing, and audit logging.

        Returns: (AIResponse, consent_source)
        """
        # Determine candidate provider
        target_provider_id = (preferred_provider or getattr(settings, "DEFAULT_LLM_PROVIDER", "local") or "local").strip().lower()
        if target_provider_id not in self._providers:
            target_provider_id = "local"

        is_permitted, consent_source, consent_rec = self.evaluate_consent(
            db=db,
            capability=capability,
            provider_id=target_provider_id,
            consent_remote_ai=consent_remote_ai,
            execution_profile=execution_profile,
            root_policy=root_policy,
            scope_id=scope_id,
            data_categories=data_categories,
        )

        # If remote was explicitly requested with key but lacks consent, raise or fallback
        if not is_permitted:
            if preferred_provider and preferred_provider != "local":
                # Strict check: caller specifically requested a remote provider
                logger.info("Remote provider '%s' requested but consent denied (%s). Falling back to local.", preferred_provider, consent_source)
            target_provider_id = "local"
            consent_source = None

        provider = self.get_provider(target_provider_id)
        if not isinstance(provider, LLMCapableProvider):
            provider = self.get_provider("local")
            assert isinstance(provider, LLMCapableProvider)

        # Attempt execution
        try:
            response = provider.generate_text(
                prompt=prompt,
                system_instruction=system_instruction,
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                **kwargs,
            )
        except Exception as exc:
            if target_provider_id != "local":
                logger.warning(
                    "Remote AI provider '%s' failed (%s). Gracefully falling back to local provider.",
                    target_provider_id,
                    exc,
                )
                local_provider = self.get_provider("local")
                assert isinstance(local_provider, LLMCapableProvider)
                response = local_provider.generate_text(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model=model,
                    **kwargs,
                )
                consent_source = None
            else:
                raise

        if not response.remote_egress:
            consent_source = None

        # Record audit run
        consent_id = consent_rec.id if (consent_rec and response.remote_egress) else None
        self.record_run(
            db=db,
            provider_id=response.provider,
            model_name=response.model_name,
            execution_location=response.execution_location,
            data_categories=response.data_categories_egressed,
            prompt=prompt,
            input_refs=input_refs,
            consent_id=consent_id,
        )

        return response, consent_source

    def generate_structured_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        capability: AICapability = AICapability.SUMMARIZATION,
        preferred_provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        consent_remote_ai: bool = False,
        execution_profile: ExecutionProfile | str | None = None,
        root_policy: RootPolicy | str | None = None,
        scope_id: str | set[str] | list[str] | tuple[str, ...] | None = None,
        data_categories: list[str] | None = None,
        db: Session | None = None,
        input_refs: list[str] | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], AIResponse, str | None]:
        """Execute a structured JSON generation with fallback routing and audit logging."""
        target_provider_id = (preferred_provider or getattr(settings, "DEFAULT_LLM_PROVIDER", "local") or "local").strip().lower()
        if target_provider_id not in self._providers:
            target_provider_id = "local"

        is_permitted, consent_source, consent_rec = self.evaluate_consent(
            db=db,
            capability=capability,
            provider_id=target_provider_id,
            consent_remote_ai=consent_remote_ai,
            execution_profile=execution_profile,
            root_policy=root_policy,
            scope_id=scope_id,
            data_categories=data_categories,
        )

        if not is_permitted:
            target_provider_id = "local"
            consent_source = None

        provider = self.get_provider(target_provider_id)
        if not isinstance(provider, LLMCapableProvider):
            provider = self.get_provider("local")
            assert isinstance(provider, LLMCapableProvider)

        try:
            parsed_json, response = provider.generate_structured_json(
                prompt=prompt,
                system_instruction=system_instruction,
                model=model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                **kwargs,
            )
        except Exception as exc:
            if target_provider_id != "local":
                logger.warning(
                    "Remote structured JSON provider '%s' failed (%s). Gracefully falling back to local provider.",
                    target_provider_id,
                    exc,
                )
                local_provider = self.get_provider("local")
                assert isinstance(local_provider, LLMCapableProvider)
                parsed_json, response = local_provider.generate_structured_json(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    model=model,
                    **kwargs,
                )
                consent_source = None
            else:
                raise

        if not response.remote_egress:
            consent_source = None

        # Record audit run
        consent_id = consent_rec.id if (consent_rec and response.remote_egress) else None
        self.record_run(
            db=db,
            provider_id=response.provider,
            model_name=response.model_name,
            execution_location=response.execution_location,
            data_categories=response.data_categories_egressed,
            prompt=prompt,
            input_refs=input_refs,
            consent_id=consent_id,
        )

        return parsed_json, response, consent_source


# Global Gateway Singleton
_GATEWAY_INSTANCE: AIProviderGateway | None = None


def get_ai_gateway() -> AIProviderGateway:
    """Access the global AIProviderGateway singleton."""
    global _GATEWAY_INSTANCE
    if _GATEWAY_INSTANCE is None:
        _GATEWAY_INSTANCE = AIProviderGateway()
    return _GATEWAY_INSTANCE
