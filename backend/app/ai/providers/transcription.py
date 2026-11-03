"""Faster-Whisper CTranslate2 ASR Provider for Arova Creator Intelligence.

Implements pluggable, local-only speech-to-text inference with genuine provenance,
serialized execution, process-level model caching, and strict offline containment.
Zero fake transcripts, zero mock confidence values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Protocol

from app.core.config import settings
from app.models.enums import CapabilityReason

# Process-level model cache to avoid per-request model loading overhead
_LOADED_MODELS_CACHE: dict[str, Any] = {}
_ASR_LOCK = threading.Lock()


@dataclass(frozen=True)
class SegmentResult:
    """Individual transcribed speech segment with acoustic metadata and provenance."""

    start_time: float
    end_time: float
    text: str
    confidence: float  # Mapped to raw avg_logprob for backwards compatibility (never a fake 0.95)
    avg_logprob: float | None = None
    no_speech_prob: float | None = None
    compression_ratio: float | None = None
    temperature: float | None = None
    forced_language: str | None = None
    detected_language: str | None = None
    language_probability: float | None = None
    words: list[dict[str, Any]] | None = None
    trust_level: str = "asr"


@dataclass(frozen=True)
class TranscriptionResult:
    """Complete speech transcription result containing full text, segments, and execution provenance."""

    language: str
    model_name: str
    full_text: str
    segments: list[SegmentResult]
    model_id: str | None = None
    model_revision: str | None = None
    device: str = "cpu"
    compute_type: str = "int8"
    parameter_hash: str | None = None
    trust_level: str = "asr"


class TranscriptionProvider(Protocol):
    """Protocol defining standard ASR provider interface."""

    def is_available(self) -> bool: ...

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        vad_filter: bool = False,
        word_timestamps: bool = True,
    ) -> TranscriptionResult: ...


class FasterWhisperProvider:
    """ASR provider using faster-whisper CTranslate2 runtime.

    Enforces genuine local inference only. Never fabricates acoustic windows, fake speech
    segments, or synthetic confidence scores.
    """

    def __init__(
        self,
        model_size_or_path: str | None = None,
        compute_type: str | None = None,
        device: str = "cpu",
        model_id: str | None = None,
        model_revision: str | None = None,
    ) -> None:
        self.model_target = model_size_or_path or model_id or settings.WHISPER_MODEL_SIZE or "small"
        self.compute_type = compute_type or settings.WHISPER_COMPUTE_TYPE or "int8"
        self.device = device
        self.model_id = model_id or f"faster-whisper-{self.model_target}"
        self.model_revision = model_revision or "local_pinned"

    def _get_cache_key(self) -> str:
        return f"{self.model_target}:{self.device}:{self.compute_type}"

    def _resolve_model_path(self) -> str | None:
        target_path = Path(self.model_target)
        if target_path.exists() and (target_path / "model.bin").is_file():
            return str(target_path)

        candidates = [self.model_target]
        if not self.model_target.startswith("faster-whisper-"):
            candidates.append(f"faster-whisper-{self.model_target}")

        try:
            from app.ai.models_registry import get_models_home, load_registry
            models_home = get_models_home()
            for cand_name in candidates:
                cand_path = models_home / cand_name
                if cand_path.exists() and (cand_path / "model.bin").is_file():
                    return str(cand_path)
            registry = load_registry()
            for cand_name in candidates:
                if cand_name in registry and registry[cand_name].installed_path:
                    p = Path(str(registry[cand_name].installed_path))
                    if p.exists() and (p / "model.bin").is_file():
                        return str(p)
        except Exception:
            pass

        models_home_env = os.environ.get("AROVA_MODELS_HOME")
        if models_home_env:
            for cand_name in candidates:
                cand = Path(models_home_env) / cand_name
                if cand.exists() and (cand / "model.bin").is_file():
                    return str(cand)

        return None

    def is_available(self) -> bool:
        """Check whether faster-whisper and model weights are installed and loadable."""
        try:
            import faster_whisper  # noqa
        except ImportError:
            return False

        return self._resolve_model_path() is not None

    def _get_or_load_model(self) -> Any:
        cache_key = self._get_cache_key()
        if cache_key in _LOADED_MODELS_CACHE:
            return _LOADED_MODELS_CACHE[cache_key]

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                f"faster-whisper package is not installed: {exc}. "
                f"CapabilityReason: {CapabilityReason.DEPENDENCY_MISSING.value}"
            ) from exc

        # Strict offline local loading
        os.environ["HF_HUB_OFFLINE"] = "1"

        resolved_path = self._resolve_model_path()
        if not resolved_path:
            raise RuntimeError(
                f"Model weights for '{self.model_target}' not found locally. "
                f"CapabilityReason: {CapabilityReason.MODEL_NOT_INSTALLED.value}"
            )

        try:
            model = WhisperModel(
                model_size_or_path=resolved_path,
                device=self.device,
                compute_type=self.compute_type,
                local_files_only=True,
            )
            _LOADED_MODELS_CACHE[cache_key] = model
            return model
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load local faster-whisper model from '{resolved_path}': {exc}"
            ) from exc

    def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
        vad_filter: bool = False,
        word_timestamps: bool = True,
        beam_size: int = 5,
        min_silence_duration_ms: int = 500,
        condition_on_previous_text: bool = False,
    ) -> TranscriptionResult:
        path = Path(audio_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Audio file not found: {path}")

        # Compute deterministic parameter hash
        param_dict = {
            "model_target": str(self.model_target),
            "device": self.device,
            "compute_type": self.compute_type,
            "language": language,
            "vad_filter": vad_filter,
            "word_timestamps": word_timestamps,
            "beam_size": beam_size,
            "min_silence_duration_ms": min_silence_duration_ms,
            "condition_on_previous_text": condition_on_previous_text,
        }
        param_hash = hashlib.sha256(json.dumps(param_dict, sort_keys=True).encode()).hexdigest()[:16]

        # Serialized execution
        with _ASR_LOCK:
            model = self._get_or_load_model()
            try:
                vad_params = {"min_silence_duration_ms": min_silence_duration_ms} if vad_filter else None
                segments_raw, info = model.transcribe(
                    str(path),
                    language=language,
                    beam_size=beam_size,
                    vad_filter=vad_filter,
                    vad_parameters=vad_params,
                    word_timestamps=word_timestamps,
                    condition_on_previous_text=condition_on_previous_text,
                )

                detected_lang = getattr(info, "language", language or "en")
                lang_prob = round(float(getattr(info, "language_probability", 1.0)), 4) if getattr(info, "language_probability", None) is not None else None

                segments: list[SegmentResult] = []
                for s in segments_raw:
                    t_text = (s.text or "").strip()
                    if t_text and s.end > s.start:
                        # Extract word timestamps if present
                        words_data = None
                        if getattr(s, "words", None):
                            words_data = [
                                {
                                    "word": w.word,
                                    "start": round(float(w.start), 3),
                                    "end": round(float(w.end), 3),
                                    "probability": round(float(w.probability), 4) if getattr(w, "probability", None) is not None else None,
                                }
                                for w in s.words
                            ]

                        raw_avg_logprob = round(float(s.avg_logprob), 4) if getattr(s, "avg_logprob", None) is not None else None
                        raw_no_speech = round(float(s.no_speech_prob), 4) if getattr(s, "no_speech_prob", None) is not None else None
                        raw_comp_ratio = round(float(s.compression_ratio), 4) if getattr(s, "compression_ratio", None) is not None else None
                        raw_temp = round(float(s.temperature), 4) if getattr(s, "temperature", None) is not None else None

                        segments.append(
                            SegmentResult(
                                start_time=round(float(s.start), 3),
                                end_time=round(float(s.end), 3),
                                text=t_text,
                                confidence=raw_avg_logprob if raw_avg_logprob is not None else 0.0,
                                avg_logprob=raw_avg_logprob,
                                no_speech_prob=raw_no_speech,
                                compression_ratio=raw_comp_ratio,
                                temperature=raw_temp,
                                forced_language=language,
                                detected_language=detected_lang,
                                language_probability=lang_prob,
                                words=words_data,
                                trust_level="asr",
                            )
                        )

                full_text = " ".join(s.text for s in segments)
                return TranscriptionResult(
                    language=detected_lang,
                    model_name=f"faster-whisper-{Path(self.model_target).name}",
                    full_text=full_text,
                    segments=segments,
                    model_id=self.model_id,
                    model_revision=self.model_revision,
                    device=self.device,
                    compute_type=self.compute_type,
                    parameter_hash=param_hash,
                    trust_level="asr",
                )
            except Exception as exc:
                raise RuntimeError(f"faster-whisper inference failed: {exc}") from exc
