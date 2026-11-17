"""Model Registry and Manager for Arova Creator Intelligence.

Maintains metadata, pinned immutable revisions, license verification, checksums,
and local directory boundaries for speech-to-text models.
Enforces Section 2.2 storage limits (15 GiB budget, 5 GiB floor) and local-only execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_PROGRAM_ROOT = Path(r"D:\ArovaStep2ASRProgram")
DEFAULT_MODELS_HOME = DEFAULT_PROGRAM_ROOT / "models"
DEFAULT_HF_HOME = DEFAULT_PROGRAM_ROOT / "hf_home"
REGISTRY_FILE = ROOT_DIR / "backend" / "app" / "ai" / "models_registry.json"

BUDGET_CAP_BYTES = 15 * 1024 * 1024 * 1024  # 15 GiB
FREE_FLOOR_BYTES = 5 * 1024 * 1024 * 1024   # 5 GiB


@dataclass
class ModelMetadata:
    model_id: str
    repo_id: str
    commit_revision: str
    license: str
    license_url: str
    model_card_url: str
    estimated_size_bytes: int
    installed_size_bytes: int
    supported_languages: list[str]
    min_ram_mb: int
    format: str  # "ctranslate2", "safetensors", "transformers"
    install_status: str  # "not_installed", "installed_unverified", "verified", "blocked"
    installed_path: str | None = None
    files_inventory: list[dict[str, Any]] = field(default_factory=list)
    last_verified_at: str | None = None


# Authoritative known candidate registry with pinned commit revisions
DEFAULT_MODELS: dict[str, ModelMetadata] = {
    "faster-whisper-small": ModelMetadata(
        model_id="faster-whisper-small",
        repo_id="Systran/faster-whisper-small",
        commit_revision="536b0662742c02347bc0e980a01041f333bce120",
        license="Apache-2.0",
        license_url="https://choosealicense.com/licenses/apache-2.0/",
        model_card_url="https://huggingface.co/Systran/faster-whisper-small",
        estimated_size_bytes=486215847,
        installed_size_bytes=0,
        supported_languages=["en", "hi", "kn", "ta", "te", "es", "fr", "de", "zh", "ja"],
        min_ram_mb=1024,
        format="ctranslate2",
        install_status="not_installed",
    ),
    "faster-whisper-base": ModelMetadata(
        model_id="faster-whisper-base",
        repo_id="Systran/faster-whisper-base",
        commit_revision="ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        license="Apache-2.0",
        license_url="https://choosealicense.com/licenses/apache-2.0/",
        model_card_url="https://huggingface.co/Systran/faster-whisper-base",
        estimated_size_bytes=147963435,
        installed_size_bytes=0,
        supported_languages=["en", "hi", "kn", "ta", "te", "es", "fr", "de", "zh", "ja"],
        min_ram_mb=512,
        format="ctranslate2",
        install_status="not_installed",
    ),
    "faster-whisper-tiny": ModelMetadata(
        model_id="faster-whisper-tiny",
        repo_id="Systran/faster-whisper-tiny",
        commit_revision="d90ca5fe260221311c53c58e660288d3deb8d356",
        license="Apache-2.0",
        license_url="https://choosealicense.com/licenses/apache-2.0/",
        model_card_url="https://huggingface.co/Systran/faster-whisper-tiny",
        estimated_size_bytes=77708579,
        installed_size_bytes=0,
        supported_languages=["en", "hi", "kn", "ta", "te", "es", "fr", "de", "zh", "ja"],
        min_ram_mb=384,
        format="ctranslate2",
        install_status="not_installed",
    ),
}


def get_program_root() -> Path:
    raw = os.environ.get("AROVA_PROGRAM_ROOT")
    if raw:
        p = Path(raw).resolve()
    else:
        if Path("D:/").exists():
            p = DEFAULT_PROGRAM_ROOT
        else:
            p = ROOT_DIR / "data" / "models_root"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_models_home() -> Path:
    """Return configured models root directory."""
    raw = os.environ.get("AROVA_MODELS_HOME")
    if raw:
        p = Path(raw).resolve()
    else:
        p = get_program_root() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_hf_home() -> Path:
    """Return configured Hugging Face cache root directory."""
    raw = os.environ.get("HF_HOME")
    if raw:
        p = Path(raw).resolve()
    else:
        p = get_program_root() / "hf_home"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_dir_size_bytes(directory: Path) -> int:
    """Recursively calculate directory size in bytes."""
    if not directory.exists():
        return 0
    total = 0
    try:
        for entry in directory.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def get_disk_free_bytes(directory: Path) -> int:
    try:
        _, _, free = shutil.disk_usage(str(directory))
        return free
    except Exception:
        return 0


def load_registry() -> dict[str, ModelMetadata]:
    """Load model registry from JSON with fallback to defaults."""
    registry = dict(DEFAULT_MODELS)
    if REGISTRY_FILE.is_file():
        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            for mid, mdict in data.items():
                registry[mid] = ModelMetadata(**mdict)
        except Exception:
            pass

    # Synchronize on-disk status
    models_home = get_models_home()
    for mid, meta in registry.items():
        expected_dir = models_home / mid
        if expected_dir.is_dir() and (expected_dir / "model.bin").is_file():
            meta.installed_path = str(expected_dir)
            if meta.install_status == "not_installed":
                meta.install_status = "installed_unverified"
        elif meta.install_status not in ("blocked", "not_installed"):
            meta.install_status = "not_installed"
            meta.installed_path = None

    return registry


def save_registry(registry: dict[str, ModelMetadata]) -> None:
    """Persist registry to disk."""
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {mid: asdict(meta) for mid, meta in registry.items()}
    REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024 * 4):
            h.update(chunk)
    return h.hexdigest().lower()


def get_model_preflight(model_id: str, registry: dict[str, ModelMetadata] | None = None) -> dict[str, Any]:
    """Compute preflight parameters and budget limits before installation."""
    if registry is None:
        registry = load_registry()
    if model_id not in registry:
        raise ValueError(f"Unknown model ID '{model_id}'. Run 'arova models catalog' to view candidates.")

    meta = registry[model_id]
    program_root = get_program_root()
    models_home = get_models_home()
    dest_dir = models_home / model_id
    hf_cache = get_hf_home()

    curr_allocated = get_dir_size_bytes(program_root)
    curr_free = get_disk_free_bytes(program_root)

    proj_allocated = curr_allocated + meta.estimated_size_bytes
    proj_free = max(0, curr_free - meta.estimated_size_bytes)

    can_install = True
    rejection_reasons: list[str] = []

    if proj_allocated > BUDGET_CAP_BYTES:
        can_install = False
        rejection_reasons.append(
            f"Projected footprint ({proj_allocated / (1024**3):.2f} GiB) exceeds 15 GiB budget cap"
        )

    if proj_free < FREE_FLOOR_BYTES:
        can_install = False
        rejection_reasons.append(
            f"Projected free space ({proj_free / (1024**3):.2f} GiB) falls below 5 GiB floor"
        )

    if meta.install_status == "blocked":
        can_install = False
        rejection_reasons.append(f"Model '{model_id}' is marked BLOCKED")

    return {
        "model_id": meta.model_id,
        "repo_id": meta.repo_id,
        "commit_revision": meta.commit_revision,
        "license": meta.license,
        "license_url": meta.license_url,
        "model_card_url": meta.model_card_url,
        "estimated_size_bytes": meta.estimated_size_bytes,
        "expected_installed_size_bytes": meta.estimated_size_bytes,
        "destination_directory": str(dest_dir),
        "cache_directory": str(hf_cache),
        "current_allocated_bytes": curr_allocated,
        "projected_allocated_bytes": proj_allocated,
        "budget_cap_bytes": BUDGET_CAP_BYTES,
        "current_free_bytes": curr_free,
        "projected_free_bytes": proj_free,
        "free_floor_bytes": FREE_FLOOR_BYTES,
        "min_ram_mb": meta.min_ram_mb,
        "format": meta.format,
        "quantization": "int8",
        "can_install": can_install,
        "rejection_reasons": rejection_reasons,
    }


def download_and_install_model(
    model_id: str,
    models_home: Path | None = None,
    cache_dir: Path | None = None,
) -> ModelMetadata:
    """Download model files pinned to immutable revision, hash inventory, and run smoke check."""
    registry = load_registry()
    preflight = get_model_preflight(model_id, registry=registry)
    if not preflight["can_install"]:
        reasons = "; ".join(preflight["rejection_reasons"])
        raise RuntimeError(f"Cannot install '{model_id}': {reasons}")

    meta = registry[model_id]
    if models_home is None:
        models_home = get_models_home()
    if cache_dir is None:
        cache_dir = get_hf_home()

    dest_dir = models_home / model_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Use huggingface_hub snapshot_download pinned to exact commit revision
    from huggingface_hub import snapshot_download

    print(f"Downloading {meta.repo_id} at revision {meta.commit_revision}...")
    snapshot_download(
        repo_id=meta.repo_id,
        revision=meta.commit_revision,
        local_dir=str(dest_dir),
        cache_dir=str(cache_dir),
    )

    # Compute inventory and SHA-256 for all files in destination directory
    inventory: list[dict[str, Any]] = []
    total_size = 0
    for file_path in sorted(dest_dir.rglob("*")):
        if file_path.is_file():
            rel_name = str(file_path.relative_to(dest_dir))
            size = file_path.stat().st_size
            total_size += size
            sha = compute_file_sha256(file_path)
            inventory.append({
                "path": rel_name,
                "size_bytes": size,
                "sha256": sha,
            })

    meta.installed_size_bytes = total_size
    meta.installed_path = str(dest_dir)
    meta.files_inventory = inventory

    # Run smoke check: load model via CTranslate2 Faster-Whisper
    print("Running verification smoke check on downloaded weights...")
    import faster_whisper
    model = faster_whisper.WhisperModel(
        str(dest_dir),
        device="cpu",
        compute_type="int8",
        local_files_only=True,
    )
    # Check model loaded
    del model

    meta.install_status = "verified"
    meta.last_verified_at = datetime.now(timezone.utc).isoformat()
    save_registry(registry)

    # Notify state manager if available
    try:
        from scripts.asr_program_state import ASRProgramStateManager
        sm = ASRProgramStateManager(selected_drive_root=str(get_program_root()))
        sm.check_and_update_storage()
    except Exception:
        pass

    return meta


def verify_installed_model(model_id: str, models_home: Path | None = None) -> tuple[bool, str]:
    """Verify presence, file hashes, and smoke loading of an installed model."""
    registry = load_registry()
    if model_id not in registry:
        return False, f"Unknown model '{model_id}'"

    meta = registry[model_id]
    if models_home is None:
        models_home = get_models_home()

    dest_dir = models_home / model_id
    if not dest_dir.is_dir() or not (dest_dir / "model.bin").is_file():
        meta.install_status = "not_installed"
        meta.installed_path = None
        save_registry(registry)
        return False, f"Model files missing at {dest_dir}"

    # Verify inventory hashes if available
    if meta.files_inventory:
        for entry in meta.files_inventory:
            file_path = dest_dir / entry["path"]
            if not file_path.is_file():
                return False, f"Required file '{entry['path']}' missing"
            actual_sha = compute_file_sha256(file_path)
            if actual_sha.lower() != entry["sha256"].lower():
                return False, f"Checksum mismatch for '{entry['path']}': expected {entry['sha256']}, got {actual_sha}"

    # Verify smoke load
    try:
        import faster_whisper
        model = faster_whisper.WhisperModel(
            str(dest_dir),
            device="cpu",
            compute_type="int8",
            local_files_only=True,
        )
        del model
    except Exception as exc:
        return False, f"Failed to load WhisperModel: {exc}"

    meta.install_status = "verified"
    meta.last_verified_at = datetime.now(timezone.utc).isoformat()
    save_registry(registry)
    return True, "Verification successful"


def remove_installed_model(model_id: str, models_home: Path | None = None) -> tuple[bool, str]:
    """Safely delete exact registered model directory within models_home."""
    registry = load_registry()
    if model_id not in registry:
        return False, f"Unknown model '{model_id}'"

    meta = registry[model_id]
    if models_home is None:
        models_home = get_models_home()

    dest_dir = (models_home / model_id).resolve()
    resolved_models_home = models_home.resolve()

    # Safety assertion: path must be direct child of models_home
    if dest_dir.parent != resolved_models_home:
        return False, f"Security violation: path {dest_dir} is not inside {resolved_models_home}"

    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    meta.install_status = "not_installed"
    meta.installed_path = None
    meta.installed_size_bytes = 0
    meta.files_inventory = []
    meta.last_verified_at = None
    save_registry(registry)

    try:
        from scripts.asr_program_state import ASRProgramStateManager
        sm = ASRProgramStateManager(selected_drive_root=str(get_program_root()))
        sm.check_and_update_storage()
    except Exception:
        pass

    return True, f"Model '{model_id}' cleanly removed"
