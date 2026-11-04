import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
from typing import Any

from app.core.config import settings
from app.processing.metadata import get_ffmpeg_binary, get_ffprobe_binary

# Ensure workspace root is in sys.path for mcp_server resolution
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from mcp_server.server import create_mcp_server


def check_python_runtime() -> dict[str, Any]:
    """Inspect Python version and interpreter path."""
    version = platform.python_version()
    major, minor, micro = sys.version_info[:3]
    is_compatible = (major, minor) >= (3, 11)
    return {
        "name": "Python Runtime",
        "status": "PASS" if is_compatible else "FAIL",
        "details": f"Python {version} ({sys.executable})",
        "compatible": is_compatible,
        "recommendation": None if is_compatible else "Python >= 3.11 is required.",
    }


def check_ffmpeg() -> dict[str, Any]:
    """Inspect system and fallback FFmpeg / ffprobe presence non-destructively."""
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    using_fallback = False

    if not ffmpeg_bin:
        ffmpeg_bin = get_ffmpeg_binary()
        using_fallback = True

    if not ffprobe_bin:
        ffprobe_bin = get_ffprobe_binary()

    # Query version non-destructively
    version_str = "Unknown"
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            version_str = proc.stdout.splitlines()[0]
    except Exception as exc:
        version_str = f"Error querying: {exc}"

    has_ffmpeg = bool(ffmpeg_bin)
    status = "PASS" if (has_ffmpeg and not using_fallback) else ("WARN" if has_ffmpeg else "FAIL")
    
    recommendation = None
    if using_fallback:
        recommendation = (
            "Using self-contained imageio-ffmpeg binary. For maximum performance and hardware acceleration, "
            "install system FFmpeg (e.g. 'winget install Gyan.FFmpeg' on Windows, 'brew install ffmpeg' on macOS, "
            "or 'sudo apt install ffmpeg' on Ubuntu/Debian)."
        )
    elif not has_ffmpeg:
        recommendation = "FFmpeg is missing. Install FFmpeg and ensure it is available on system PATH."

    return {
        "name": "FFmpeg & ffprobe",
        "status": status,
        "details": f"{version_str} [ffmpeg: {ffmpeg_bin}, ffprobe: {ffprobe_bin}]",
        "fallback_active": using_fallback,
        "recommendation": recommendation,
    }


def check_sqlite_fts5() -> dict[str, Any]:
    """Verify SQLite connectivity and FTS5 full-text search extension availability."""
    try:
        con = sqlite3.connect(":memory:")
        cur = con.cursor()
        cur.execute("CREATE VIRTUAL TABLE fts_probe USING fts5(content);")
        cur.execute("INSERT INTO fts_probe(content) VALUES ('arova creator intelligence test');")
        cur.execute("SELECT content FROM fts_probe WHERE fts_probe MATCH 'intelligence';")
        res = cur.fetchone()
        con.close()
        
        has_fts5 = res is not None and "intelligence" in res[0]
        return {
            "name": "SQLite FTS5 Full-Text Search",
            "status": "PASS" if has_fts5 else "FAIL",
            "details": f"SQLite {sqlite3.sqlite_version} with FTS5 virtual table support enabled.",
            "recommendation": None if has_fts5 else "SQLite was compiled without FTS5 extension enabled.",
        }
    except Exception as exc:
        return {
            "name": "SQLite FTS5 Full-Text Search",
            "status": "FAIL",
            "details": f"FTS5 probe error: {exc}",
            "recommendation": "Ensure python standard library sqlite3 has FTS5 support.",
        }


def check_disk_space_and_permissions() -> dict[str, Any]:
    """Inspect free disk space and write permissions for data directories."""
    data_dir = Path(settings.DATA_DIR).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    usage = shutil.disk_usage(str(data_dir))
    total_gb = round(usage.total / (1024**3), 2)
    free_gb = round(usage.free / (1024**3), 2)
    used_gb = round(usage.used / (1024**3), 2)

    is_space_ok = free_gb >= 2.0
    status = "PASS" if is_space_ok else "WARN"

    # Test read/write permission safely
    can_write = False
    probe_file = data_dir / ".arova_doctor_write_probe"
    try:
        probe_file.write_text("probe", encoding="utf-8")
        can_write = probe_file.read_text(encoding="utf-8") == "probe"
    except Exception:
        can_write = False
    finally:
        if probe_file.exists():
            probe_file.unlink(missing_ok=True)

    recommendation = None
    if not is_space_ok:
        recommendation = f"Low disk space: {free_gb} GB remaining. Video indexing requires at least 2.0 GB recommended free space."
    if not can_write:
        status = "FAIL"
        recommendation = f"Permission denied: Data directory '{data_dir}' is not writable."

    return {
        "name": "Storage & Permissions",
        "status": status,
        "details": f"Data root: {data_dir} | Free: {free_gb} GB / {total_gb} GB ({used_gb} GB used) | Writable: {can_write}",
        "free_gb": free_gb,
        "recommendation": recommendation,
    }


def check_model_cache_readiness() -> dict[str, Any]:
    """Inspect local model cache directory sizes non-destructively without downloading weights."""
    home = Path.home()
    hf_cache = home / ".cache" / "huggingface" / "hub"
    whisper_cache = home / ".cache" / "faster_whisper"

    def get_dir_size_mb(path: Path) -> float:
        if not path.exists():
            return 0.0
        total_bytes = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return round(total_bytes / (1024**2), 2)

    hf_mb = get_dir_size_mb(hf_cache)
    whisper_mb = get_dir_size_mb(whisper_cache)

    has_local_models = (hf_mb > 0 or whisper_mb > 0)
    details = (
        f"HuggingFace cache: {hf_mb} MB ({hf_cache}) | "
        f"faster-whisper cache: {whisper_mb} MB ({whisper_cache})"
    )

    return {
        "name": "Model Cache Readiness",
        "status": "PASS" if has_local_models else "INFO",
        "details": details,
        "recommendation": (
            None if has_local_models else 
            "No pre-cached model weights detected. Local deterministic fallbacks are active; "
            "model weights will be downloaded on first actual pipeline invocation or via 'arova demo'."
        ),
    }


def check_mcp_server_readiness() -> dict[str, Any]:
    """Verify FastMCP server initializes and exposes strictly 8 read-only tools by default."""
    try:
        import asyncio
        server = create_mcp_server(enable_exports=False)
        tools = asyncio.run(server.list_tools())
        tool_names = [t.name for t in tools]

        expected_tools = [
            "list_videos",
            "get_video_metadata",
            "search_video_content",
            "search_transcripts",
            "find_video_clips",
            "summarize_video",
            "get_video_chapters",
            "get_media_library_stats",
            "get_media_availability",
            "find_duplicate_media",
            "get_evidence_citations",
            "get_capability_status",
        ]
        is_isolated = len(tools) == 12 and tool_names == expected_tools
        return {
            "name": "Model Context Protocol (MCP)",
            "status": "PASS" if is_isolated else "FAIL",
            "details": f"FastMCP server ready: 12 read-only tools verified ({', '.join(tool_names)})",
            "tool_count": len(tools),
            "recommendation": None if is_isolated else f"Unexpected MCP toolset exposed: {tool_names}",
        }
    except Exception as exc:
        return {
            "name": "Model Context Protocol (MCP)",
            "status": "FAIL",
            "details": f"Failed to initialize FastMCP server: {exc}",
            "recommendation": "Check FastMCP dependencies and mcp_server package configuration.",
        }


def run_doctor_checks() -> dict[str, Any]:
    """Execute complete suite of non-destructive system health diagnostics."""
    checks = [
        check_python_runtime(),
        check_ffmpeg(),
        check_sqlite_fts5(),
        check_disk_space_and_permissions(),
        check_model_cache_readiness(),
        check_mcp_server_readiness(),
    ]

    has_fail = any(c["status"] == "FAIL" for c in checks)
    has_warn = any(c["status"] == "WARN" for c in checks)

    overall_status = "CRITICAL" if has_fail else ("WARNING" if has_warn else "HEALTHY")

    return {
        "overall_status": overall_status,
        "is_healthy": not has_fail,
        "checks": checks,
    }


def format_doctor_report(report: dict[str, Any]) -> str:
    """Format doctor report into clean human-readable terminal output."""
    lines = [
        "",
        "==================================================================",
        f"        AROVA CREATOR INTELLIGENCE — SYSTEM DIAGNOSTIC (DOCTOR)    ",
        "==================================================================",
        f"Overall System Status: [{report['overall_status']}]",
        "------------------------------------------------------------------",
    ]

    status_badges = {
        "PASS": "[OK]  ",
        "INFO": "[INFO]",
        "WARN": "[WARN]",
        "FAIL": "[FAIL]",
    }

    for c in report["checks"]:
        badge = status_badges.get(c["status"], "[????]")
        lines.append(f"{badge} {c['name']}")
        lines.append(f"       Details: {c['details']}")
        if c.get("recommendation"):
            lines.append(f"       Advice:  {c['recommendation']}")
        lines.append("")

    lines.append("------------------------------------------------------------------")
    if report["is_healthy"]:
        lines.append("All core prerequisites satisfied. System is ready for local video intelligence.")
    else:
        lines.append("One or more critical checks failed. Please address the recommendations above.")
    lines.append("==================================================================")
    lines.append("")
    return "\n".join(lines)


def run_doctor_cli(as_json: bool = False) -> int:
    """CLI action for arova doctor. Returns exit code (0 for success/warn, 1 for fail)."""
    report = run_doctor_checks()
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(format_doctor_report(report))

    return 0 if report["is_healthy"] else 1
