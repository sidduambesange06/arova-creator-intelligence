"""Provider-neutral abstractions and capability contracts for BYO-AI Gateway.

Defines standardized interfaces, capability enums, data contracts, and security boundaries
for local and remote AI providers (Google Gemini, OpenAI-compatible, Anthropic, Local).
Strictly enforces credential masking, zero plaintext secrets, and data provenance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from typing import Any, Protocol


class AICapability(str, Enum):
    """Core capabilities supported across AI providers."""

    ASR = "asr"
    EMBEDDINGS = "embeddings"
    RERANKING = "reranking"
    LLM_QA = "llm_qa"
    SUMMARIZATION = "summarization"


class ExecutionLocation(str, Enum):
    """Execution boundary classification for privacy and egress gating."""

    LOCAL = "local"
    REMOTE = "remote"


def mask_secret(secret: str | None, visible_prefix: int = 3, visible_suffix: int = 4) -> str:
    """Mask sensitive tokens or API keys for safe logging and UI display.
    
    Never logs or displays the full secret.
    """
    if not secret:
        return ""
    stripped = secret.strip()
    if len(stripped) <= (visible_prefix + visible_suffix + 2):
        return "[REDACTED_SECRET]"
    return f"{stripped[:visible_prefix]}...{stripped[-visible_suffix:]}"


def compute_prompt_hash(prompt: str) -> str:
    """Compute deterministic SHA-256 digest of prompt for audit trails without saving prompt content."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AIModelInfo:
    """Metadata describing a model available through a provider."""

    model_id: str
    provider_id: str
    capabilities: list[AICapability]
    execution_location: ExecutionLocation
    description: str
    context_window: int | None = None
    is_default: bool = False


@dataclass
class AIResponse:
    """Standardized output response across all LLM providers."""

    text: str
    provider: str
    model_name: str
    execution_location: ExecutionLocation
    remote_egress: bool
    data_categories_egressed: list[str] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class BaseAIProvider(ABC):
    """Abstract base class for all AI providers in the gateway."""

    provider_id: str
    provider_name: str
    supported_capabilities: set[AICapability]
    execution_location: ExecutionLocation

    @abstractmethod
    def is_available(self, capability: AICapability | None = None) -> bool:
        """Check if provider and capability are ready for execution."""
        ...

    @abstractmethod
    def validate_credentials(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str | None]:
        """Validate credentials non-destructively.
        
        Returns (is_valid, error_message_or_none).
        """
        ...

    @abstractmethod
    def list_models(self) -> list[AIModelInfo]:
        """List supported models for this provider."""
        ...


class LLMCapableProvider(BaseAIProvider):
    """Interface for providers supporting natural language generation, Q&A, and summarization."""

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AIResponse:
        """Generate text completion from prompt."""
        ...

    @abstractmethod
    def generate_structured_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        schema: dict[str, Any] | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], AIResponse]:
        """Generate structured JSON response parsed into a dict."""
        ...

