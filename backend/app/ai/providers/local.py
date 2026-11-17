"""Local-first fallback AI provider for Arova Creator Intelligence.

Operates 100% offline with zero network egress, zero token costs, and deterministic output.
Provides extractive grounded Q&A and transcript summarization.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.providers.base import (
    AICapability,
    AIModelInfo,
    AIResponse,
    ExecutionLocation,
    LLMCapableProvider,
)


class LocalExtractiveProvider(LLMCapableProvider):
    """Local, offline, zero-network provider using deterministic extractive logic."""

    provider_id = "local"
    provider_name = "Local Extractive Engine"
    supported_capabilities = {
        AICapability.LLM_QA,
        AICapability.SUMMARIZATION,
    }
    execution_location = ExecutionLocation.LOCAL

    def is_available(self, capability: AICapability | None = None) -> bool:
        if capability is None:
            return True
        return capability in self.supported_capabilities

    def validate_credentials(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str | None]:
        # Local provider requires zero credentials and is always valid
        return True, None

    def list_models(self) -> list[AIModelInfo]:
        return [
            AIModelInfo(
                model_id="grounded-extractive-local",
                provider_id=self.provider_id,
                capabilities=[AICapability.LLM_QA],
                execution_location=self.execution_location,
                description="Deterministic local extractive Q&A based on top-ranked retrieval windows.",
                is_default=True,
            ),
            AIModelInfo(
                model_id="extractive-grounded-local",
                provider_id=self.provider_id,
                capabilities=[AICapability.SUMMARIZATION],
                execution_location=self.execution_location,
                description="Deterministic local transcript summarizer with word-frequency topic extraction.",
                is_default=True,
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
        # For general text prompts, return clean trimmed text
        return AIResponse(
            text=prompt.strip(),
            provider=self.provider_id,
            model_name=model or "grounded-extractive-local",
            execution_location=self.execution_location,
            remote_egress=False,
            data_categories_egressed=[],
        )

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
        # Deterministic summarization structured JSON
        # Expects prompt to contain the transcript or text to summarize
        full_text = prompt.strip()
        segments = kwargs.get("segments", [])
        
        summary_text, topics, chapters = self._extractive_summary(segments, full_text)
        result = {
            "summary": summary_text,
            "topics": topics,
            "chapters": chapters,
        }
        response = AIResponse(
            text=json.dumps(result),
            provider=self.provider_id,
            model_name=model or "extractive-grounded-local",
            execution_location=self.execution_location,
            remote_egress=False,
            data_categories_egressed=[],
        )
        return result, response

    @staticmethod
    def _extractive_summary(segments: list[Any], full_text: str) -> tuple[str, list[str], list[dict[str, Any]]]:
        """Generate extractive summary, topics, and chapters from segments and text."""
        words = re.findall(r"\b[a-zA-Z]{4,}\b", full_text.lower())
        stop_words = {
            "this", "that", "with", "from", "have", "video", "about", "which", "will",
            "there", "their", "would", "could", "should", "what", "where", "when", "then",
            "just", "more", "some", "like", "other", "into", "over", "these", "those",
        }
        meaningful_words = [w for w in words if w not in stop_words]
        counts: dict[str, int] = {}
        for w in meaningful_words:
            counts[w] = counts.get(w, 0) + 1
        top_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
        topics = [w.capitalize() for w, _ in top_words] if top_words else ["General Overview"]

        # 3-part chapter markers
        chapters: list[dict[str, Any]] = []
        if segments:
            n = len(segments)
            indices = [0, n // 3, (2 * n) // 3] if n >= 3 else [0]
            labels = ["Introduction & Context", "Key Discussion & Details", "Conclusion & Next Steps"]
            seen_times: set[float] = set()
            for idx, label in zip(indices, labels):
                seg = segments[idx]
                st = round(getattr(seg, "start_time", 0.0), 2)
                if st not in seen_times:
                    seen_times.add(st)
                    chapters.append({"start_time": st, "title": label})
        if not chapters:
            chapters = [{"start_time": 0.0, "title": "Introduction"}]

        # Extractive summary text: first 3 distinct sentences
        sentences = [s.strip() for s in re.split(r"[.!?]+", full_text) if len(s.strip()) > 15]
        summary_text = ". ".join(sentences[:3]) + "." if sentences else full_text[:200]
        return summary_text, topics, chapters

