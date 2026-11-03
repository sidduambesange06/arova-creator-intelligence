"""Filesystem containment, API security, and local authorization utilities.

Implements deny-by-default media path validation and discovery strictly bounded
by configured ALLOWED_MEDIA_ROOTS, plus local API authentication and path sanitization.

Threat Model & TOCTOU Boundaries:
- Single-user local workstation threat model: filesystem access permissions belong to the local user.
- Path containment guarantees protection against relative directory traversal (../), path manipulation,
  symlink files pointing outside approved roots, and directory symlink escapes during discovery.
- Race condition note (TOCTOU): In Windows and POSIX filesystems, a theoretical microsecond gap exists
  between canonical containment verification and subsequent reading by external subprocesses (FFmpeg).
  Complete elimination of this race condition requires file-descriptor passing (e.g. openat), which is
  unsupported by standard FFmpeg CLI invocations. Under Arova's single-user local threat model, this residual
  race is acknowledged as an acceptable boundary condition.
"""

import hashlib
from pathlib import Path
import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
_bearer_scheme = HTTPBearer(auto_error=False)


def get_allowed_roots(roots_config: str | None = None) -> list[Path]:
    """Parse and resolve configured allowed media roots into canonical paths.

    Defaults to settings.ALLOWED_MEDIA_ROOTS. Returns an empty list if unconfigured,
    enforcing deny-by-default containment.
    """
    raw = roots_config if roots_config is not None else settings.ALLOWED_MEDIA_ROOTS
    if not raw or not raw.strip():
        return []
    return [Path(p.strip()).resolve() for p in raw.split(",") if p.strip()]


def validate_media_path(target_path: str | Path, allowed_roots: list[Path] | None = None) -> Path:
    """Validate that target_path canonicalizes strictly within configured allowed roots.

    Raises:
        ValueError: If canonical path is outside allowed media roots.
        FileNotFoundError: If the path does not exist on disk.
    """
    raw = Path(target_path).expanduser()
    resolved = raw.resolve()
    roots = allowed_roots if allowed_roots is not None else get_allowed_roots()
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError(f"Path '{resolved}' is outside allowed media roots.")
    if not resolved.exists():
        raise FileNotFoundError(f"Media path does not exist: '{resolved}'")
    return resolved


def sanitize_file_path_for_display(file_path: str | Path, allowed_roots: list[Path] | None = None) -> str:
    """Sanitize absolute host filesystem path to prevent sensitive system directory disclosure.

    Returns the path relative to its matching allowed media root, or the base filename.
    """
    path = Path(file_path)
    roots = allowed_roots if allowed_roots is not None else get_allowed_roots()
    try:
        resolved = path.resolve()
        for r in roots:
            if resolved == r:
                return resolved.name
            if r in resolved.parents:
                return str(resolved.relative_to(r).as_posix())
    except Exception:
        pass
    return path.name


def discover_video_files(target_path: str | Path, allowed_roots: list[Path] | None = None) -> list[Path]:
    """Discover video files under target_path, enforcing strict canonical boundary containment.

    - Validates target_path against allowed_roots.
    - If target_path is a single file, verifies extension and returns [canonical_path].
    - If target_path is a directory, scans for supported video extensions, independently
      verifying that every discovered file's canonical target resolves within allowed_roots.
      Symlink files or symlinked directories resolving outside allowed roots are excluded.
    """
    roots = allowed_roots if allowed_roots is not None else get_allowed_roots()
    resolved = validate_media_path(target_path, allowed_roots=roots)
    if resolved.is_file():
        if resolved.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            raise ValueError(f"Unsupported video extension '{resolved.suffix}'.")
        return [resolved]

    if not resolved.is_dir():
        return []

    files: set[Path] = set()
    for p in resolved.rglob("*"):
        try:
            if not p.is_file():
                continue
            if p.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
                continue
            canonical = p.resolve()
            # Reject symlinks pointing outside allowed media roots
            if not any(canonical == root or root in canonical.parents for root in roots):
                continue
            if canonical.is_file():
                files.add(canonical)
        except (OSError, PermissionError):
            continue

    return sorted(files)


def compute_sha256(file_path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def require_api_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Validate incoming request against configured API_AUTH_TOKEN.

    If settings.API_AUTH_TOKEN is unset or empty, access is granted unconditionally
    (standard local single-user desktop mode). When set, valid Bearer or X-API-Key is required.
    """
    expected_token = settings.API_AUTH_TOKEN
    if not expected_token or not expected_token.strip():
        return

    supplied_token = None
    if credentials and credentials.credentials:
        supplied_token = credentials.credentials.strip()
    elif x_api_key and x_api_key.strip():
        supplied_token = x_api_key.strip()

    if not supplied_token or not secrets.compare_digest(supplied_token, expected_token.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


_local_admin_token: str | None = None


def get_admin_token() -> str:
    """Return configured or auto-generated local admin token.

    If ADMIN_AUTH_TOKEN or API_AUTH_TOKEN is configured in settings, that value is used.
    Otherwise, generates and caches an ephemeral local admin bearer token.
    """
    global _local_admin_token
    configured = settings.ADMIN_AUTH_TOKEN or settings.API_AUTH_TOKEN
    if configured and configured.strip():
        return configured.strip()
    if _local_admin_token is None:
        _local_admin_token = secrets.token_urlsafe(32)
    return _local_admin_token


def require_admin_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Enforce mandatory local-admin authentication for administrative endpoints.

    The Database Explorer must never be accessible without a valid admin token,
    even if general API authentication is disabled or omitted. Fails closed
    if expected or supplied token is missing or empty.
    """
    expected_token = get_admin_token()
    if not expected_token or not expected_token.strip():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication is unconfigured or unavailable.",
        )

    supplied_token = None
    if credentials and credentials.credentials:
        supplied_token = credentials.credentials.strip()
    elif x_admin_token and x_admin_token.strip():
        supplied_token = x_admin_token.strip()

    if not supplied_token or not secrets.compare_digest(supplied_token, expected_token.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def validate_server_binding_and_security(
    host: str | None = None,
    auth_token: str | None = None,
) -> None:
    """Verify that network-exposed instances require authentication.

    If host is not a local loopback interface (127.0.0.1, localhost, ::1),
    API_AUTH_TOKEN must be configured. Fails with RuntimeError if an unsafe
    network configuration is detected.
    """
    bind_host = (host if host is not None else settings.API_HOST).strip().lower()
    token = auth_token if auth_token is not None else settings.API_AUTH_TOKEN
    loopback_hosts = {"127.0.0.1", "localhost", "::1"}
    if bind_host not in loopback_hosts:
        if not token or not token.strip():
            raise RuntimeError(
                f"Unsafe network binding: Server configured to bind to non-loopback host '{bind_host}' "
                "without API_AUTH_TOKEN. Network-exposed instances must require authentication."
            )
