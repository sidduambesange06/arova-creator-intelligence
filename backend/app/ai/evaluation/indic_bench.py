"""Arova Indic Creator Bench — Dataset Contracts, Manifest Validator & Provenance.

Implements M2 (V12 Phase 1) benchmark contracts:
- Versioned dataset descriptor, sample manifest, and provenance schema validation.
- Strict path-traversal and symlink-escape containment for local audio assets.
- Byte-level SHA-256 and audio header integrity verification.
- Unicode-safe Indic normalization (preserving matras, viramas, nukta, ZWJ/ZWNJ).
- Deterministic, secret-safe ASR run and batch provenance contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct
import sys
from typing import Any
import unicodedata

from jsonschema import Draft202012Validator

from app.core.security import compute_sha256

DATASET_SCHEMA_VERSION = "1.0.0"
SAMPLE_SCHEMA_VERSION = "1.0.0"
PROVENANCE_SCHEMA_VERSION = "1.0.0"
BATCH_SCHEMA_VERSION = "1.0.0"
NORMALIZATION_POLICY_VERSION = "v2_indic_unicode_safe_nfc"

SUPPORTED_AUDIO_FORMATS = {"wav", "flac", "ogg"}
REDISTRIBUTION_STATUSES = {"redistributable", "local_eval_only", "restricted"}
REFERENCE_STATUSES = {"verified", "unverified", "missing", "invalid"}

# Structured validation failure taxonomy (M2 Gate G3)
ERR_INVALID_MANIFEST = "INVALID_MANIFEST"
ERR_UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
ERR_DUPLICATE_SAMPLE = "DUPLICATE_SAMPLE"
ERR_MISSING_ASSET = "MISSING_ASSET"
ERR_PATH_ESCAPE = "PATH_ESCAPE"
ERR_SYMLINK_ESCAPE = "SYMLINK_ESCAPE"
ERR_CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
ERR_UNSUPPORTED_AUDIO_FORMAT = "UNSUPPORTED_AUDIO_FORMAT"
ERR_MISSING_REFERENCE = "MISSING_REFERENCE"
ERR_INVALID_LANGUAGE_METADATA = "INVALID_LANGUAGE_METADATA"

# Supported language -> expected script metadata & Unicode codepoint range
LANGUAGE_REGISTRY: dict[str, dict[str, Any]] = {
    "hi_in": {
        "language_name": "Hindi",
        "script_code": "Deva",
        "script_name": "Devanagari",
        "ranges": ((0x0900, 0x097F),),
    },
    "kn_in": {
        "language_name": "Kannada",
        "script_code": "Knda",
        "script_name": "Kannada",
        "ranges": ((0x0C80, 0x0CFF),),
    },
    "ta_in": {
        "language_name": "Tamil",
        "script_code": "Taml",
        "script_name": "Tamil",
        "ranges": ((0x0B80, 0x0BFF),),
    },
    "te_in": {
        "language_name": "Telugu",
        "script_code": "Telu",
        "script_name": "Telugu",
        "ranges": ((0x0C00, 0x0C7F),),
    },
    "en_us": {
        "language_name": "English (US)",
        "script_code": "Latn",
        "script_name": "Latin",
        "ranges": ((0x0041, 0x005A), (0x0061, 0x007A)),
    },
}

_SCHEMAS_DIR = (
    Path(__file__).resolve().parents[4] / "sample_data" / "indic_creator_bench" / "schemas"
)

_SECRET_KEY_TOKENS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "passwd",
    "authorization",
    "auth_header",
    "bearer",
    "credential",
    "private_key",
    "access_key",
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{12,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{16,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{12,}"),
)


def _load_schema(filename: str) -> dict[str, Any]:
    schema_path = _SCHEMAS_DIR / filename
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validate_against_schema(payload: dict[str, Any], schema_filename: str) -> list[str]:
    validator = Draft202012Validator(_load_schema(schema_filename))
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    formatted: list[str] = []
    for err in errors:
        path = ".".join(str(p) for p in err.path) or "<root>"
        formatted.append(f"{path}: {err.message}")
    return formatted


class ManifestPathSecurityError(ValueError):
    """Raised when a manifest path violates relative-path or symlink containment."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_safe_dataset_child(dataset_root: Path, relpath: str) -> Path:
    """Resolve a dataset-relative path safely within dataset_root.

    Rejects empty paths, absolute paths, drive letters, UNC paths, '..' segments,
    symlinks along any segment, and canonical paths escaping dataset_root.
    """
    if not isinstance(relpath, str) or not relpath.strip():
        raise ManifestPathSecurityError(ERR_PATH_ESCAPE, "Relative path must be a non-empty string.")

    cleaned = relpath.strip()
    # Check Windows drive letters, leading slashes, UNC prefixes, and NUL bytes
    if (
        "\x00" in cleaned
        or cleaned.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:", cleaned)
        or Path(cleaned).is_absolute()
    ):
        raise ManifestPathSecurityError(
            ERR_PATH_ESCAPE,
            f"Absolute or rooted path rejected: '{relpath}'.",
        )

    parts = [p for p in re.split(r"[\\/]+", cleaned) if p and p != "."]
    if not parts or any(part == ".." for part in parts):
        raise ManifestPathSecurityError(
            ERR_PATH_ESCAPE,
            f"Path traversal segment rejected: '{relpath}'.",
        )

    root_resolved = dataset_root.resolve()
    current = dataset_root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ManifestPathSecurityError(
                ERR_SYMLINK_ESCAPE,
                f"Symlink segment rejected inside dataset root: '{current}'.",
            )

    resolved = current.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ManifestPathSecurityError(
            ERR_PATH_ESCAPE,
            f"Resolved path '{resolved}' escapes dataset root '{root_resolved}'.",
        )
    return resolved


@dataclass(frozen=True)
class ValidationFailure:
    code: str
    message: str
    utterance_id: str | None = None
    line_number: int | None = None


@dataclass
class SampleValidationResult:
    utterance_id: str
    line_number: int
    valid: bool
    language_code: str | None = None
    script_code: str | None = None
    reference_status: str | None = None
    failures: list[ValidationFailure] = field(default_factory=list)


@dataclass
class ManifestValidationReport:
    status: str  # VALID | PARTIAL | INVALID
    dataset_root: str
    dataset_id: str | None
    dataset_version: str | None
    dataset_schema_version: str | None
    total_samples: int
    valid_samples: int
    invalid_samples: int
    require_audio: bool
    language_counts: dict[str, int] = field(default_factory=dict)
    script_counts: dict[str, int] = field(default_factory=dict)
    reference_status_counts: dict[str, int] = field(default_factory=dict)
    failures: list[ValidationFailure] = field(default_factory=list)
    sample_results: list[SampleValidationResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text_matches_script(text: str, language_code: str) -> bool:
    info = LANGUAGE_REGISTRY.get(language_code)
    if info is None or not text:
        return False
    ranges = info["ranges"]
    for ch in text:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in ranges):
            return True
    return False


@dataclass(frozen=True)
class AudioStreamInfo:
    format: str
    samplerate: int
    channels: int
    duration: float


def _inspect_audio_stream(audio_path: Path) -> AudioStreamInfo:
    """Inspect audio header format, sample rate, channels, and duration.

    Parses WAV headers natively using pure Python standard library struct parsing,
    supporting both PCM (tag 1) and IEEE Float (tag 3) formats without external dependencies.
    Falls back to soundfile (if installed) or media metadata probing.
    """
    try:
        import soundfile as sf  # type: ignore

        info = sf.info(str(audio_path))
        return AudioStreamInfo(
            format=(info.format or "").lower(),
            samplerate=int(info.samplerate),
            channels=int(info.channels),
            duration=float(info.duration),
        )
    except Exception:
        pass

    suffix = audio_path.suffix.lower().lstrip(".")
    if suffix == "wav":
        try:
            with open(audio_path, "rb") as f:
                header = f.read(12)
                if len(header) == 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
                    fmt_tag = channels = samplerate = bits = data_bytes = 0
                    while True:
                        chunk_hdr = f.read(8)
                        if len(chunk_hdr) < 8:
                            break
                        chunk_id, chunk_size = struct.unpack("<4sI", chunk_hdr)
                        if chunk_id == b"fmt ":
                            chunk_data = f.read(chunk_size)
                            if len(chunk_data) >= 16:
                                fmt_tag, channels, samplerate, _, _, bits = struct.unpack("<HHIIHH", chunk_data[:16])
                        elif chunk_id == b"data":
                            data_bytes = chunk_size
                            f.seek(chunk_size, os.SEEK_CUR)
                        else:
                            f.seek(chunk_size, os.SEEK_CUR)
                    bytes_per_sample = bits // 8
                    if channels > 0 and samplerate > 0 and bytes_per_sample > 0 and data_bytes > 0:
                        duration = data_bytes / (samplerate * channels * bytes_per_sample)
                        return AudioStreamInfo(
                            format="wav",
                            samplerate=samplerate,
                            channels=channels,
                            duration=duration,
                        )
        except Exception:
            pass

    try:
        from app.processing.metadata import probe_video_metadata

        meta = probe_video_metadata(audio_path)
        return AudioStreamInfo(
            format=(meta.format or suffix).lower(),
            samplerate=16000,
            channels=1 if meta.has_audio else 0,
            duration=float(meta.duration),
        )
    except Exception:
        pass

    raise ValueError(f"Unsupported or corrupt audio file: {audio_path.name}")


def _validate_sample_record(
    raw_obj: dict[str, Any],
    line_number: int,
    dataset_root: Path,
    descriptor: dict[str, Any],
    seen_ids: set[str],
    require_audio: bool,
) -> SampleValidationResult:
    failures: list[ValidationFailure] = []
    uid = raw_obj.get("utterance_id") if isinstance(raw_obj.get("utterance_id"), str) else None
    lang = raw_obj.get("language_code") if isinstance(raw_obj.get("language_code"), str) else None
    script = raw_obj.get("script_code") if isinstance(raw_obj.get("script_code"), str) else None
    ref_status = raw_obj.get("reference_status") if isinstance(raw_obj.get("reference_status"), str) else None

    # Schema version check before detailed schema error formatting
    sample_ver = raw_obj.get("sample_schema_version")
    if sample_ver != SAMPLE_SCHEMA_VERSION:
        failures.append(
            ValidationFailure(
                ERR_UNSUPPORTED_SCHEMA,
                f"Unsupported sample_schema_version '{sample_ver}'; expected '{SAMPLE_SCHEMA_VERSION}'.",
                utterance_id=uid,
                line_number=line_number,
            )
        )

    schema_errs = _validate_against_schema(raw_obj, "sample_record_v1.schema.json")
    for err in schema_errs:
        # Avoid double-reporting version mismatch as generic invalid manifest
        if err.startswith("sample_schema_version:") and sample_ver != SAMPLE_SCHEMA_VERSION:
            continue
        failures.append(
            ValidationFailure(
                ERR_INVALID_MANIFEST,
                f"Sample schema error: {err}",
                utterance_id=uid,
                line_number=line_number,
            )
        )

    if uid:
        if uid in seen_ids:
            failures.append(
                ValidationFailure(
                    ERR_DUPLICATE_SAMPLE,
                    f"Duplicate utterance_id '{uid}'.",
                    utterance_id=uid,
                    line_number=line_number,
                )
            )
        seen_ids.add(uid)

    # Descriptor consistency checks
    if raw_obj.get("dataset_id") != descriptor.get("dataset_id"):
        failures.append(
            ValidationFailure(
                ERR_INVALID_MANIFEST,
                f"Sample dataset_id '{raw_obj.get('dataset_id')}' does not match descriptor '{descriptor.get('dataset_id')}'.",
                utterance_id=uid,
                line_number=line_number,
            )
        )

    # Language & script checks
    if lang not in LANGUAGE_REGISTRY:
        failures.append(
            ValidationFailure(
                ERR_INVALID_LANGUAGE_METADATA,
                f"Unsupported language_code '{lang}'.",
                utterance_id=uid,
                line_number=line_number,
            )
        )
    else:
        expected_lang = LANGUAGE_REGISTRY[lang]
        if raw_obj.get("language_name") != expected_lang["language_name"]:
            failures.append(
                ValidationFailure(
                    ERR_INVALID_LANGUAGE_METADATA,
                    f"language_name '{raw_obj.get('language_name')}' mismatches expected '{expected_lang['language_name']}' for '{lang}'.",
                    utterance_id=uid,
                    line_number=line_number,
                )
            )
        if script != expected_lang["script_code"] or raw_obj.get("script_name") != expected_lang["script_name"]:
            failures.append(
                ValidationFailure(
                    ERR_INVALID_LANGUAGE_METADATA,
                    f"Script ({script}, {raw_obj.get('script_name')}) mismatches expected ({expected_lang['script_code']}, {expected_lang['script_name']}) for '{lang}'.",
                    utterance_id=uid,
                    line_number=line_number,
                )
            )

    # Reference transcript verification
    ref_text = raw_obj.get("reference_transcript", "")
    raw_ref = raw_obj.get("raw_transcription", "")
    if ref_status == "verified":
        if not isinstance(ref_text, str) or not ref_text.strip() or not isinstance(raw_ref, str) or not raw_ref.strip():
            failures.append(
                ValidationFailure(
                    ERR_MISSING_REFERENCE,
                    "Verified sample must have non-empty reference_transcript and raw_transcription.",
                    utterance_id=uid,
                    line_number=line_number,
                )
            )
        elif lang in LANGUAGE_REGISTRY and not _text_matches_script(ref_text, lang):
            failures.append(
                ValidationFailure(
                    ERR_INVALID_LANGUAGE_METADATA,
                    f"Verified reference_transcript does not contain expected script characters for '{lang}'.",
                    utterance_id=uid,
                    line_number=line_number,
                )
            )

    # Audio path & integrity verification
    relpath = raw_obj.get("audio_relpath")
    resolved_audio: Path | None = None
    if isinstance(relpath, str):
        try:
            resolved_audio = resolve_safe_dataset_child(dataset_root, relpath)
        except ManifestPathSecurityError as exc:
            failures.append(
                ValidationFailure(
                    exc.code,
                    str(exc),
                    utterance_id=uid,
                    line_number=line_number,
                )
            )

    if require_audio and resolved_audio is not None:
        if not resolved_audio.exists() or not resolved_audio.is_file():
            failures.append(
                ValidationFailure(
                    ERR_MISSING_ASSET,
                    f"Audio file missing or not a regular file: '{relpath}'.",
                    utterance_id=uid,
                    line_number=line_number,
                )
            )
        else:
            actual_sha = compute_sha256(resolved_audio)
            if actual_sha != raw_obj.get("audio_sha256"):
                failures.append(
                    ValidationFailure(
                        ERR_CHECKSUM_MISMATCH,
                        f"Audio SHA-256 mismatch for '{relpath}': expected {raw_obj.get('audio_sha256')}, got {actual_sha}.",
                        utterance_id=uid,
                        line_number=line_number,
                    )
                )

            try:
                info = _inspect_audio_stream(resolved_audio)
                fmt_lower = (info.format or "").lower()
                if fmt_lower not in SUPPORTED_AUDIO_FORMATS or fmt_lower != raw_obj.get("audio_format"):
                    failures.append(
                        ValidationFailure(
                            ERR_UNSUPPORTED_AUDIO_FORMAT,
                            f"Audio format '{fmt_lower}' invalid or mismatches declared '{raw_obj.get('audio_format')}'.",
                            utterance_id=uid,
                            line_number=line_number,
                        )
                    )
                if info.samplerate != raw_obj.get("sample_rate_hz") or info.channels != raw_obj.get("channels"):
                    failures.append(
                        ValidationFailure(
                            ERR_UNSUPPORTED_AUDIO_FORMAT,
                            f"Audio stream mismatch: actual {info.samplerate}Hz/{info.channels}ch vs declared {raw_obj.get('sample_rate_hz')}Hz/{raw_obj.get('channels')}ch.",
                            utterance_id=uid,
                            line_number=line_number,
                        )
                    )
                declared_dur = float(raw_obj.get("duration_sec", 0.0))
                if info.duration <= 0 or abs(info.duration - declared_dur) > 0.05:
                    failures.append(
                        ValidationFailure(
                            ERR_UNSUPPORTED_AUDIO_FORMAT,
                            f"Audio duration mismatch: actual {info.duration:.3f}s vs declared {declared_dur:.3f}s.",
                            utterance_id=uid,
                            line_number=line_number,
                        )
                    )
            except Exception as exc:
                failures.append(
                    ValidationFailure(
                        ERR_UNSUPPORTED_AUDIO_FORMAT,
                        f"Failed to read audio header for '{relpath}': {exc}",
                        utterance_id=uid,
                        line_number=line_number,
                    )
                )

    return SampleValidationResult(
        utterance_id=uid or f"<line-{line_number}>",
        line_number=line_number,
        valid=len(failures) == 0,
        language_code=lang,
        script_code=script,
        reference_status=ref_status,
        failures=failures,
    )


def validate_indic_bench_dataset(
    dataset_root: str | Path,
    descriptor_filename: str = "dataset.json",
    require_audio: bool = True,
) -> tuple[ManifestValidationReport, list[dict[str, Any]]]:
    """Validate an Indic Creator Bench dataset descriptor and sample manifest.

    Returns (ManifestValidationReport, parsed_sample_records).
    """
    root = Path(dataset_root)
    descriptor_path = root / descriptor_filename
    failures: list[ValidationFailure] = []

    if not descriptor_path.is_file():
        failures.append(
            ValidationFailure(
                ERR_MISSING_ASSET,
                f"Dataset descriptor file missing: '{descriptor_path}'.",
            )
        )
        return (
            ManifestValidationReport(
                status="INVALID",
                dataset_root=str(root),
                dataset_id=None,
                dataset_version=None,
                dataset_schema_version=None,
                total_samples=0,
                valid_samples=0,
                invalid_samples=0,
                require_audio=require_audio,
                failures=failures,
            ),
            [],
        )

    try:
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    except Exception as exc:
        failures.append(ValidationFailure(ERR_INVALID_MANIFEST, f"Invalid JSON in descriptor: {exc}"))
        return (
            ManifestValidationReport(
                status="INVALID",
                dataset_root=str(root),
                dataset_id=None,
                dataset_version=None,
                dataset_schema_version=None,
                total_samples=0,
                valid_samples=0,
                invalid_samples=0,
                require_audio=require_audio,
                failures=failures,
            ),
            [],
        )

    if not isinstance(descriptor, dict):
        failures.append(ValidationFailure(ERR_INVALID_MANIFEST, "Descriptor JSON root must be an object."))
        return (
            ManifestValidationReport(
                status="INVALID",
                dataset_root=str(root),
                dataset_id=None,
                dataset_version=None,
                dataset_schema_version=None,
                total_samples=0,
                valid_samples=0,
                invalid_samples=0,
                require_audio=require_audio,
                failures=failures,
            ),
            [],
        )

    ds_ver = descriptor.get("dataset_schema_version")
    if ds_ver != DATASET_SCHEMA_VERSION:
        failures.append(
            ValidationFailure(
                ERR_UNSUPPORTED_SCHEMA,
                f"Unsupported dataset_schema_version '{ds_ver}'; expected '{DATASET_SCHEMA_VERSION}'.",
            )
        )

    for err in _validate_against_schema(descriptor, "dataset_descriptor_v1.schema.json"):
        if err.startswith("dataset_schema_version:") and ds_ver != DATASET_SCHEMA_VERSION:
            continue
        failures.append(ValidationFailure(ERR_INVALID_MANIFEST, f"Descriptor schema error: {err}"))

    manifest_path: Path | None = None
    manifest_relpath = descriptor.get("manifest_relpath")
    if isinstance(manifest_relpath, str):
        try:
            manifest_path = resolve_safe_dataset_child(root, manifest_relpath)
        except ManifestPathSecurityError as exc:
            failures.append(ValidationFailure(exc.code, str(exc)))

    if manifest_path is not None and not manifest_path.is_file():
        failures.append(ValidationFailure(ERR_MISSING_ASSET, f"Manifest file missing: '{manifest_relpath}'."))
        manifest_path = None

    if manifest_path is not None:
        actual_manifest_sha = compute_sha256(manifest_path)
        expected_manifest_sha = descriptor.get("manifest_sha256")
        if actual_manifest_sha != expected_manifest_sha:
            failures.append(
                ValidationFailure(
                    ERR_CHECKSUM_MISMATCH,
                    f"Manifest SHA-256 mismatch: expected {expected_manifest_sha}, got {actual_manifest_sha}.",
                )
            )

    samples: list[dict[str, Any]] = []
    sample_results: list[SampleValidationResult] = []
    seen_ids: set[str] = set()
    lang_counts: dict[str, int] = {}
    script_counts: dict[str, int] = {}
    ref_counts: dict[str, int] = {}

    if manifest_path is not None:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
        for line_no, raw_line in enumerate(lines, start=1):
            if not raw_line.strip():
                failures.append(
                    ValidationFailure(
                        ERR_INVALID_MANIFEST,
                        f"Empty blank line at manifest line {line_no}.",
                        line_number=line_no,
                    )
                )
                continue
            try:
                obj = json.loads(raw_line)
            except Exception as exc:
                res = SampleValidationResult(
                    utterance_id=f"<line-{line_no}>",
                    line_number=line_no,
                    valid=False,
                    failures=[
                        ValidationFailure(
                            ERR_INVALID_MANIFEST,
                            f"Invalid JSON on manifest line {line_no}: {exc}",
                            line_number=line_no,
                        )
                    ],
                )
                sample_results.append(res)
                failures.extend(res.failures)
                continue

            if not isinstance(obj, dict):
                res = SampleValidationResult(
                    utterance_id=f"<line-{line_no}>",
                    line_number=line_no,
                    valid=False,
                    failures=[
                        ValidationFailure(
                            ERR_INVALID_MANIFEST,
                            f"Manifest line {line_no} is not a JSON object.",
                            line_number=line_no,
                        )
                    ],
                )
                sample_results.append(res)
                failures.extend(res.failures)
                continue

            samples.append(obj)
            res = _validate_sample_record(
                obj,
                line_number=line_no,
                dataset_root=root,
                descriptor=descriptor,
                seen_ids=seen_ids,
                require_audio=require_audio,
            )
            sample_results.append(res)
            failures.extend(res.failures)
            if res.language_code:
                lang_counts[res.language_code] = lang_counts.get(res.language_code, 0) + 1
            if res.script_code:
                script_counts[res.script_code] = script_counts.get(res.script_code, 0) + 1
            if res.reference_status:
                ref_counts[res.reference_status] = ref_counts.get(res.reference_status, 0) + 1

    # Check declared sample_count
    declared_count = descriptor.get("sample_count")
    if isinstance(declared_count, int) and len(sample_results) != declared_count:
        failures.append(
            ValidationFailure(
                ERR_INVALID_MANIFEST,
                f"Descriptor sample_count={declared_count} mismatches manifest records={len(sample_results)}.",
            )
        )

    valid_count = sum(1 for r in sample_results if r.valid)
    invalid_count = len(sample_results) - valid_count
    descriptor_level_failures = [f for f in failures if f.utterance_id is None]

    if not failures and valid_count > 0:
        status = "VALID"
    elif valid_count > 0 and not descriptor_level_failures and invalid_count > 0:
        status = "PARTIAL"
    else:
        status = "INVALID"

    report = ManifestValidationReport(
        status=status,
        dataset_root=str(root),
        dataset_id=descriptor.get("dataset_id"),
        dataset_version=descriptor.get("dataset_version"),
        dataset_schema_version=ds_ver if isinstance(ds_ver, str) else None,
        total_samples=len(sample_results),
        valid_samples=valid_count,
        invalid_samples=invalid_count,
        require_audio=require_audio,
        language_counts=dict(sorted(lang_counts.items())),
        script_counts=dict(sorted(script_counts.items())),
        reference_status_counts=dict(sorted(ref_counts.items())),
        failures=failures,
        sample_results=sample_results,
    )
    return report, samples


def normalize_indic_reference(
    text: str,
    language_code: str,
    policy_version: str = NORMALIZATION_POLICY_VERSION,
) -> str:
    """Normalize text for WER/CER evaluation without mutating original reference strings.

    Under v2_indic_unicode_safe_nfc:
    - Applies Unicode NFC normalization.
    - Preserves Indic combining marks (matras, viramas, nukta) and ZWJ/ZWNJ joiners.
    - Replaces punctuation (category P*) with whitespace while preserving script characters.
    - Lowercases only Latin text (e.g. en_us).
    """
    if policy_version != NORMALIZATION_POLICY_VERSION:
        raise ValueError(f"Unsupported normalization policy version '{policy_version}'.")

    nfc = unicodedata.normalize("NFC", text or "")
    cleaned_chars: list[str] = []
    for ch in nfc:
        cat = unicodedata.category(ch)
        if cat.startswith("P"):
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(ch)
    norm = "".join(cleaned_chars)
    if language_code.startswith("en"):
        norm = norm.lower()
    return " ".join(norm.split()).strip()


def _levenshtein_sdi(ref: list[str] | str, hyp: list[str] | str) -> tuple[int, int, int, int]:
    """Return (edits, substitutions, deletions, insertions) from ref -> hyp."""
    m, n = len(ref), len(hyp)
    if m == 0:
        return (n, 0, 0, n)
    if n == 0:
        return (m, 0, m, 0)
    prev: list[tuple[int, int, int, int]] = [(j, 0, 0, j) for j in range(n + 1)]
    for i, item_r in enumerate(ref, start=1):
        curr: list[tuple[int, int, int, int]] = [(i, 0, i, 0)]
        for j, item_h in enumerate(hyp, start=1):
            sub_cost = 0 if item_r == item_h else 1
            p_diag = prev[j - 1]
            p_up = prev[j]
            c_left = curr[j - 1]
            best = (p_diag[0] + sub_cost, p_diag[1] + sub_cost, p_diag[2], p_diag[3])
            cand_del = (p_up[0] + 1, p_up[1], p_up[2] + 1, p_up[3])
            if cand_del[0] < best[0]:
                best = cand_del
            cand_ins = (c_left[0] + 1, c_left[1], c_left[2], c_left[3] + 1)
            if cand_ins[0] < best[0]:
                best = cand_ins
            curr.append(best)
        prev = curr
    return prev[-1]


def _levenshtein_distance(seq_a: list[str] | str, seq_b: list[str] | str) -> int:
    return _levenshtein_sdi(seq_a, seq_b)[0]


def compute_safe_utterance_metrics(
    raw_reference: str,
    raw_hypothesis: str,
    language_code: str,
    policy_version: str = NORMALIZATION_POLICY_VERSION,
) -> dict[str, Any]:
    """Compute WER/CER and S/D/I edit metrics while keeping raw_reference untouched."""
    norm_ref = normalize_indic_reference(raw_reference, language_code, policy_version)
    norm_hyp = normalize_indic_reference(raw_hypothesis, language_code, policy_version)

    ref_words = norm_ref.split()
    hyp_words = norm_hyp.split()
    word_edits, word_subs, word_dels, word_ins = _levenshtein_sdi(ref_words, hyp_words)
    char_edits, char_subs, char_dels, char_ins = _levenshtein_sdi(norm_ref, norm_hyp)

    ref_word_count = len(ref_words)
    ref_char_count = len(norm_ref)

    if ref_word_count == 0:
        wer: float | None = 0.0 if len(hyp_words) == 0 else None
    else:
        wer = round(word_edits / float(ref_word_count), 6)

    if ref_char_count == 0:
        cer: float | None = 0.0 if len(norm_hyp) == 0 else None
    else:
        cer = round(char_edits / float(ref_char_count), 6)

    return {
        "raw_reference": raw_reference,
        "normalized_reference": norm_ref,
        "raw_hypothesis": raw_hypothesis,
        "normalized_hypothesis": norm_hyp,
        "normalization_policy_version": policy_version,
        "word_edits": word_edits,
        "word_substitutions": word_subs,
        "word_deletions": word_dels,
        "word_insertions": word_ins,
        "ref_words": ref_word_count,
        "wer": wer,
        "char_edits": char_edits,
        "char_substitutions": char_subs,
        "char_deletions": char_dels,
        "char_insertions": char_ins,
        "ref_chars": ref_char_count,
        "cer": cer,
        "empty_reference": ref_word_count == 0,
        "empty_hypothesis": len(hyp_words) == 0,
    }


def compute_safe_corpus_metrics(utterance_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute micro-aggregated corpus WER/CER and S/D/I counts with safe zero-denominator handling."""
    total_word_edits = sum(int(m["word_edits"]) for m in utterance_metrics)
    total_word_subs = sum(int(m.get("word_substitutions", 0)) for m in utterance_metrics)
    total_word_dels = sum(int(m.get("word_deletions", 0)) for m in utterance_metrics)
    total_word_ins = sum(int(m.get("word_insertions", 0)) for m in utterance_metrics)
    total_ref_words = sum(int(m["ref_words"]) for m in utterance_metrics)
    total_char_edits = sum(int(m["char_edits"]) for m in utterance_metrics)
    total_char_subs = sum(int(m.get("char_substitutions", 0)) for m in utterance_metrics)
    total_char_dels = sum(int(m.get("char_deletions", 0)) for m in utterance_metrics)
    total_char_ins = sum(int(m.get("char_insertions", 0)) for m in utterance_metrics)
    total_ref_chars = sum(int(m["ref_chars"]) for m in utterance_metrics)
    empty_hyp_count = sum(1 for m in utterance_metrics if bool(m.get("empty_hypothesis", False)))

    corpus_wer = round(total_word_edits / float(total_ref_words), 6) if total_ref_words > 0 else None
    corpus_cer = round(total_char_edits / float(total_ref_chars), 6) if total_ref_chars > 0 else None
    empty_hyp_rate = round(empty_hyp_count / float(len(utterance_metrics)), 6) if utterance_metrics else None

    return {
        "utterance_count": len(utterance_metrics),
        "total_word_edits": total_word_edits,
        "total_word_substitutions": total_word_subs,
        "total_word_deletions": total_word_dels,
        "total_word_insertions": total_word_ins,
        "total_ref_words": total_ref_words,
        "corpus_wer": corpus_wer,
        "total_char_edits": total_char_edits,
        "total_char_substitutions": total_char_subs,
        "total_char_deletions": total_char_dels,
        "total_char_insertions": total_char_ins,
        "total_ref_chars": total_ref_chars,
        "corpus_cer": corpus_cer,
        "empty_hypothesis_count": empty_hyp_count,
        "empty_hypothesis_rate": empty_hyp_rate,
    }


def validate_secret_safe(payload: Any, _path: str = "<root>") -> None:
    """Reject dictionaries/values containing API keys, secrets, tokens, or auth headers."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_str = str(key).lower()
            if any(tok in key_str for tok in _SECRET_KEY_TOKENS) and key_str != "secret_safe_verified":
                raise ValueError(f"Secret-bearing key '{key}' prohibited in provenance at '{_path}'.")
            validate_secret_safe(value, _path=f"{_path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for idx, item in enumerate(payload):
            validate_secret_safe(item, _path=f"{_path}[{idx}]")
    elif isinstance(payload, str):
        for pat in _SECRET_VALUE_PATTERNS:
            if pat.search(payload):
                raise ValueError(f"Secret-like credential value prohibited in provenance at '{_path}'.")


def compute_config_fingerprint(config: dict[str, Any]) -> str:
    """Return deterministic SHA-256 hex digest of a secret-validated configuration mapping."""
    validate_secret_safe(config, _path="config")
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_asr_run_provenance(
    *,
    run_id: str,
    dataset_id: str,
    dataset_version: str,
    split: str,
    manifest_sha256: str,
    provider_type: str,
    model_id: str,
    model_revision: str,
    device: str = "cpu",
    compute_type: str = "int8",
    language_mode: str = "forced",
    normalization_policy_version: str = NORMALIZATION_POLICY_VERSION,
    decoding_params: dict[str, Any] | None = None,
    execution_status: str = "NOT_RUN",
    created_at_utc: str | None = None,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct, fingerprint, and schema-validate a secret-safe ASRRunProvenance record."""
    dec_params = dict(decoding_params or {"beam_size": 5, "vad_filter": False, "word_timestamps": False})
    env_info = dict(
        environment
        or {
            "python_version": platform.python_version(),
            "platform": sys.platform,
        }
    )

    config_payload = {
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "split": split,
        "manifest_sha256": manifest_sha256,
        "provider_type": provider_type,
        "model_id": model_id,
        "model_revision": model_revision,
        "device": device,
        "compute_type": compute_type,
        "language_mode": language_mode,
        "normalization_policy_version": normalization_policy_version,
        "decoding_params": dec_params,
    }
    fingerprint = compute_config_fingerprint(config_payload)

    record: dict[str, Any] = {
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "split": split,
        "manifest_sha256": manifest_sha256,
        "provider_type": provider_type,
        "model_id": model_id,
        "model_revision": model_revision,
        "device": device,
        "compute_type": compute_type,
        "language_mode": language_mode,
        "normalization_policy_version": normalization_policy_version,
        "decoding_params": dec_params,
        "config_fingerprint_sha256": fingerprint,
        "execution_status": execution_status,
        "environment": env_info,
        "secret_safe_verified": True,
    }

    validate_secret_safe(record, _path="ASRRunProvenance")
    schema_errs = _validate_against_schema(record, "provenance_v1.schema.json")
    if schema_errs:
        raise ValueError(f"ASRRunProvenance schema error: {'; '.join(schema_errs)}")
    return record


def build_batch_run_provenance(
    *,
    batch_id: str,
    dataset_id: str,
    dataset_version: str,
    split: str,
    manifest_sha256: str,
    total_items: int,
    processed_items: int,
    succeeded_items: int,
    failed_items: int,
    skipped_items: int,
    run_ids: list[str],
    batch_config: dict[str, Any],
    execution_status: str = "NOT_RUN",
    created_at_utc: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Construct, fingerprint, and schema-validate a secret-safe BatchRunProvenance record."""
    fingerprint = compute_config_fingerprint(
        {
            "batch_schema_version": BATCH_SCHEMA_VERSION,
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "split": split,
            "manifest_sha256": manifest_sha256,
            "batch_config": batch_config,
        }
    )
    record: dict[str, Any] = {
        "batch_schema_version": BATCH_SCHEMA_VERSION,
        "batch_id": batch_id,
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "split": split,
        "manifest_sha256": manifest_sha256,
        "total_items": total_items,
        "processed_items": processed_items,
        "succeeded_items": succeeded_items,
        "failed_items": failed_items,
        "skipped_items": skipped_items,
        "run_ids": list(run_ids),
        "config_fingerprint_sha256": fingerprint,
        "execution_status": execution_status,
        "secret_safe_verified": True,
    }
    if notes is not None:
        record["notes"] = notes

    validate_secret_safe(record, _path="BatchRunProvenance")
    schema_errs = _validate_against_schema(record, "provenance_v1.schema.json")
    if schema_errs:
        raise ValueError(f"BatchRunProvenance schema error: {'; '.join(schema_errs)}")
    return record
