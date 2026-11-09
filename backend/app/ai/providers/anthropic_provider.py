"""Anthropic Claude provider adapter for BYO-AI Gateway.

Supports standard Anthropic Messages REST API (https://api.anthropic.com/v1/messages)
for Claude 3.5 Sonnet and Haiku models.
Enforces strict consent checks, remote egress tagging, and credential masking.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
import urllib.error
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

DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMCapableProvider):
    """Anthropic Claude Messages API adapter."""

    provider_id = "anthropic"
    provider_name = "Anthropic (Claude)"
    supported_capabilities = {
        AICapability.LLM_QA,
        AICapability.SUMMARIZATION,
    }
    execution_location = ExecutionLocation.REMOTE

    def is_available(self, capability: AICapability | None = None) -> bool:
        if capability is not None and capability not in self.supported_capabilities:
            return False
        key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.getenv("ANTHROPIC_API_KEY")
        return bool(key and key.strip())

    def _resolve_api_key(self, api_key: str | None = None) -> str:
        key = (
            api_key
            or getattr(settings, "ANTHROPIC_API_KEY", None)
            or os.getenv("ANTHROPIC_API_KEY")
            or ""
        ).strip()
        return key

    def validate_credentials(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str | None]:
        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            return False, "Anthropic API key is required"

        try:
            # Send a minimal 1-token message probe
            req_payload = {
                "model": DEFAULT_ANTHROPIC_MODEL,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
            headers = {
                "x-api-key": resolved_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            }
            payload_bytes = json.dumps(req_payload).encode("utf-8")
            req = urllib.request.Request(
                ANTHROPIC_MESSAGES_URL,
                data=payload_bytes,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, None
                return False, f"HTTP status {resp.status}"
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            safe_err = err_body.replace(resolved_key, mask_secret(resolved_key))
            return False, f"HTTP {exc.code}: {safe_err[:200]}"
        except Exception as exc:
            return False, f"Connection error: {str(exc)}"

    def list_models(self) -> list[AIModelInfo]:
        return [
            AIModelInfo(
                model_id="claude-3-5-haiku-20241022",
                provider_id=self.provider_id,
                capabilities=[AICapability.LLM_QA, AICapability.SUMMARIZATION],
                execution_location=self.execution_location,
                description="Fast and intelligent lightweight Claude model for video reasoning.",
                context_window=200000,
                is_default=True,
            ),
            AIModelInfo(
                model_id="claude-3-5-sonnet-20241022",
                provider_id=self.provider_id,
                capabilities=[AICapability.LLM_QA, AICapability.SUMMARIZATION],
                execution_location=self.execution_location,
                description="Anthropic's frontier reasoning model for complex media analysis.",
                context_window=200000,
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
        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            raise ValueError("Anthropic API key not provided")

        chosen_model = model or DEFAULT_ANTHROPIC_MODEL
        req_payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens or 1024,
            "temperature": temperature,
        }
        if system_instruction:
            req_payload["system"] = system_instruction

        headers: dict[str, str] = {
            "x-api-key": resolved_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
            "user-agent": "Arova-Creator-Intelligence/0.1.0",
        }

        payload_bytes = json.dumps(req_payload).encode("utf-8")
        req = urllib.request.Request(
            ANTHROPIC_MESSAGES_URL,
            data=payload_bytes,
            headers=headers,
            method="POST",
        )

        categories = kwargs.get("data_categories_egressed", ["query", "video_transcript_snippets"])

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                content_blocks = resp_data.get("content", [])
                text_out = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text").strip()

                usage = resp_data.get("usage", {})
                return AIResponse(
                    text=text_out,
                    provider=self.provider_id,
                    model_name=chosen_model,
                    execution_location=self.execution_location,
                    remote_egress=True,
                    data_categories_egressed=categories,
                    prompt_tokens=usage.get("input_tokens"),
                    completion_tokens=usage.get("output_tokens"),
                    total_tokens=(usage.get("input_tokens", 0) + usage.get("output_tokens", 0)),
                    finish_reason=resp_data.get("stop_reason"),
                    raw_metadata=resp_data,
                )
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            safe_err = err_body.replace(resolved_key, mask_secret(resolved_key))
            raise RuntimeError(f"Anthropic API error (HTTP {exc.code}): {safe_err}") from exc

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
        json_sys = (system_instruction or "") + "\nRespond strictly in valid raw JSON without any markdown formatting."
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

