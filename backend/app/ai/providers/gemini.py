"""Google Gemini provider adapter for BYO-AI Gateway.

Supports Google GenAI SDK (google-genai) when installed, with lightweight HTTPS REST fallback.
Provides text generation, grounded Q&A, and structured JSON summarization.
"""

from __future__ import annotations

import json
import logging
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

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GoogleGeminiProvider(LLMCapableProvider):
    """Google Gemini remote provider adapter."""

    provider_id = "google-gemini"
    provider_name = "Google Gemini"
    supported_capabilities = {
        AICapability.LLM_QA,
        AICapability.SUMMARIZATION,
    }
    execution_location = ExecutionLocation.REMOTE

    def is_available(self, capability: AICapability | None = None) -> bool:
        if capability is not None and capability not in self.supported_capabilities:
            return False
        # Available if an API key is configured or can be supplied per-request
        return bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())

    def validate_credentials(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str | None]:
        key = (api_key or settings.GEMINI_API_KEY or "").strip()
        if not key:
            return False, "Gemini API key is required"

        # Try SDK first if available
        try:
            from google import genai  # type: ignore

            client = genai.Client(api_key=key)
            # Lightweight probe call
            client.models.generate_content(
                model=DEFAULT_GEMINI_MODEL,
                contents="ping",
            )
            return True, None
        except ImportError:
            pass
        except Exception as exc:
            return False, f"Gemini SDK validation failed: {str(exc)}"

        # REST fallback validation
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{DEFAULT_GEMINI_MODEL}:generateContent?key={urllib.parse.quote(key)}"
            )
            payload = json.dumps({"contents": [{"parts": [{"text": "ping"}]}]}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return True, None
                return False, f"HTTP status {resp.status}"
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            # Mask key if present in error message
            safe_err = err_body.replace(key, mask_secret(key))
            return False, f"HTTP {exc.code}: {safe_err[:200]}"
        except Exception as exc:
            return False, f"Connection error: {str(exc)}"

    def list_models(self) -> list[AIModelInfo]:
        return [
            AIModelInfo(
                model_id="gemini-2.5-flash",
                provider_id=self.provider_id,
                capabilities=[AICapability.LLM_QA, AICapability.SUMMARIZATION],
                execution_location=self.execution_location,
                description="High-speed, multimodal Gemini 2.5 Flash model for reasoning and summarization.",
                context_window=1048576,
                is_default=True,
            ),
            AIModelInfo(
                model_id="gemini-2.0-flash",
                provider_id=self.provider_id,
                capabilities=[AICapability.LLM_QA, AICapability.SUMMARIZATION],
                execution_location=self.execution_location,
                description="Gemini 2.0 Flash model.",
                context_window=1048576,
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
        key = (api_key or settings.GEMINI_API_KEY or "").strip()
        if not key:
            raise ValueError("Google Gemini API key not provided")

        chosen_model = model or DEFAULT_GEMINI_MODEL
        categories = kwargs.get("data_categories_egressed", ["query", "video_transcript_snippets"])

        # Try official google-genai SDK first
        try:
            from google import genai  # type: ignore

            client = genai.Client(api_key=key)
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{prompt}"

            response = client.models.generate_content(
                model=chosen_model,
                contents=full_prompt,
            )
            text_out = response.text.strip() if response.text else ""
            return AIResponse(
                text=text_out,
                provider=self.provider_id,
                model_name=chosen_model,
                execution_location=self.execution_location,
                remote_egress=True,
                data_categories_egressed=categories,
            )
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("Google GenAI SDK call failed (%s), trying REST fallback", exc)

        # REST API fallback
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{chosen_model}:generateContent?key={urllib.parse.quote(key)}"
        )
        req_data: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }
        if system_instruction:
            req_data["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if max_tokens:
            req_data["generationConfig"]["maxOutputTokens"] = max_tokens

        payload = json.dumps(req_data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                candidates = resp_data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("No candidates returned from Gemini API")
                parts = candidates[0].get("content", {}).get("parts", [])
                text_out = "".join(p.get("text", "") for p in parts).strip()
                return AIResponse(
                    text=text_out,
                    provider=self.provider_id,
                    model_name=chosen_model,
                    execution_location=self.execution_location,
                    remote_egress=True,
                    data_categories_egressed=categories,
                    raw_metadata=resp_data,
                )
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            safe_err = err_body.replace(key, mask_secret(key))
            raise RuntimeError(f"Gemini API error (HTTP {exc.code}): {safe_err}") from exc

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
        json_prompt = (
            f"{prompt}\n\n"
            "Respond ONLY with a valid, raw JSON object. Do not wrap in markdown or backticks."
        )
        ai_resp = self.generate_text(
            prompt=json_prompt,
            system_instruction=system_instruction,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            **kwargs,
        )
        clean_text = ai_resp.text.strip()
        # Strip markdown fences if present: ```json ... ```
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)
        parsed = json.loads(clean_text)
        return parsed, ai_resp

