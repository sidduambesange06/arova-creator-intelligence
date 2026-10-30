import hashlib
from pathlib import Path

from app.core.config import settings

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def get_allowed_roots(roots_config: str | None = None) -> list[Path]:
    raw = roots_config if roots_config is not None else settings.ALLOWED_MEDIA_ROOTS
    roots = [Path(p.strip()).resolve() for p in raw.split(",") if p.strip()]
    return roots or [Path.cwd().resolve()]


def validate_media_path(target_path: str | Path, allowed_roots: list[Path] | None = None) -> Path:
    resolved = Path(target_path).expanduser().resolve()
    roots = allowed_roots if allowed_roots is not None else get_allowed_roots()
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError(f"Path '{resolved}' is outside allowed media roots.")
    if not resolved.exists():
        raise FileNotFoundError(f"Media path does not exist: '{resolved}'")
    return resolved


def discover_video_files(target_path: str | Path, allowed_roots: list[Path] | None = None) -> list[Path]:
    resolved = validate_media_path(target_path, allowed_roots=allowed_roots)
    if resolved.is_file():
        if resolved.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            raise ValueError(f"Unsupported video extension '{resolved.suffix}'.")
        return [resolved]
    files = sorted(
        p.resolve()
        for p in resolved.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    )
    return files


def compute_sha256(file_path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()

