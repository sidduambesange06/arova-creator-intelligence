"""OpenAI and OpenAI-compatible provider adapter for BYO-AI Gateway.

Supports standard OpenAI Chat Completions REST API (/v1/chat/completions) for official
OpenAI models (gpt-4o, gpt-4o-mini) as well as local OpenAI-compatible runtimes
(Ollama, vLLM, LM Studio, LocalAI).
Dynamically identifies local loopback endpoints (localhost, 127.0.0.1) to preserve offline guarantees.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from app.ai.providers.base import (
    AICapability,
    AIModelInfo,
    AIResponse,
    ExecutionLocation,
    LLMCapableProvider,
    mask_secret,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
OFFICIAL_OPENAI_BASE_URL = "https://api.openai.com/v1"


def is_local_endpoint(url: str) -> bool:
    """Check if URL points to a local loopback interface."""
    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return hostname in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class OpenAICompatibleProvider(LLMCapableProvider):
    """OpenAI and OpenAI-compatible Chat Completions adapter."""

    provider_id = "openai"
    provider_name = "OpenAI & Compatible (Ollama/vLLM)"
    supported_capabilities = {
        AICapability.LLM_QA,
        AICapability.SUMMARIZATION,
    }
    execution_location = ExecutionLocation.REMOTE

    def is_available(self, capability: AICapability | None = None) -> bool:
        if capability is not None and capability not in self.supported_capabilities:
            return False
        # Available if OPENAI_API_KEY is configured in settings or environment, or custom base_url is set
        key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        base_url = getattr(settings, "OPENAI_BASE_URL", None) or os.getenv("OPENAI_BASE_URL")
        return bool((key and key.strip()) or (base_url and base_url.strip()))

    def _resolve_base_url(self, base_url: str | None = None) -> str:
        url = (
            base_url
            or getattr(settings, "OPENAI_BASE_URL", None)
            or os.getenv("OPENAI_BASE_URL")
            or OFFICIAL_OPENAI_BASE_URL
        ).strip().rstrip("/")
        return url

    def _resolve_api_key(self, api_key: str | None = None) -> str:
        key = (
            api_key
            or getattr(settings, "OPENAI_API_KEY", None)
            or os.getenv("OPENAI_API_KEY")
            or ""
        ).strip()
        return key

    def validate_credentials(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str | None]:
        resolved_url = self._resolve_base_url(base_url)
        resolved_key = self._resolve_api_key(api_key)

        is_local = is_local_endpoint(resolved_url)
        # Local endpoints like Ollama don't require an API key; remote OpenAI does
        if not is_local and not resolved_key:
            return False, "OpenAI API key is required for remote endpoints"

        try:
            # Probe models endpoint: GET /v1/models
            models_url = f"{resolved_url}/models"
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if resolved_key:
                headers["Authorization"] = f"Bearer {resolved_key}"

            req = urllib.request.Request(models_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, None
                return False, f"HTTP status {resp.status}"
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            safe_err = err_body.replace(resolved_key, mask_secret(resolved_key)) if resolved_key else err_body
            return False, f"HTTP {exc.code}: {safe_err[:200]}"
        except Exception as exc:
            return False, f"Connection error: {str(exc)}"

    def list_models(self) -> list[AIModelInfo]:
        return [
            AIModelInfo(
                model_id="gpt-4o-mini",
                provider_id=self.provider_id,
                capabilities=[AICapability.LLM_QA, AICapability.SUMMARIZATION],
                execution_location=self.execution_location,
                description="Fast and cost-effective OpenAI model for video Q&A and summarization.",
                context_window=128000,
                is_default=True,
            ),
            AIModelInfo(
                model_id="gpt-4o",
                provider_id=self.provider_id,
                capabilities=[AICapability.LLM_QA, AICapability.SUMMARIZATION],
                execution_location=self.execution_location,
                description="Flagship OpenAI multimodal model.",
                context_window=128000,
                is_default=False,
            ),
        ]

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
        resolved_url = self._resolve_base_url(base_url)
        resolved_key = self._resolve_api_key(api_key)
        is_local = is_local_endpoint(resolved_url)

        if not is_local and not resolved_key:
            raise ValueError("OpenAI API key not provided for remote endpoint")

        chosen_model = model or DEFAULT_OPENAI_MODEL
        endpoint_url = f"{resolved_url}/chat/completions"

        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        req_payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            req_payload["max_tokens"] = max_tokens

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": "Arova-Creator-Intelligence/0.1.0",
        }
        if resolved_key:
            headers["Authorization"] = f"Bearer {resolved_key}"

        payload_bytes = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(endpoint_url, data=payload_bytes, headers=headers, method="POST")

        categories = kwargs.get("data_categories_egressed", ["query", "video_transcript_snippets"])
        exec_loc = ExecutionLocation.LOCAL if is_local else ExecutionLocation.REMOTE
        remote_egress = not is_local

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                choices = resp_data.get("choices", [])
                if not choices:
                    raise RuntimeError("No choices returned from OpenAI chat completion")

                message_obj = choices[0].get("message", {})
                content = message_obj.get("content", "").strip()
                finish_reason = choices[0].get("finish_reason")

                usage = resp_data.get("usage", {})
                return AIResponse(
                    text=content,
                    provider=self.provider_id,
                    model_name=chosen_model,
                    execution_location=exec_loc,
                    remote_egress=remote_egress,
                    data_categories_egressed=categories if remote_egress else [],
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    finish_reason=finish_reason,
                    raw_metadata=resp_data,
                )
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            safe_err = err_body.replace(resolved_key, mask_secret(resolved_key)) if resolved_key else err_body
            raise RuntimeError(f"OpenAI API error (HTTP {exc.code}): {safe_err}") from exc

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
        json_sys = (system_instruction or "") + "\nRespond strictly in valid JSON format."
        ai_resp = self.generate_text(
            prompt=prompt,
            system_instruction=json_sys.strip(),
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            **kwargs,
        )
        clean_text = ai_resp.text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)
        parsed = json.loads(clean_text)
        return parsed, ai_resp

