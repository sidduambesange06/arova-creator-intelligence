import json
from pathlib import Path
import pytest

from app.cli.doctor import (
    check_disk_space_and_permissions,
    check_ffmpeg,
    check_mcp_server_readiness,
    check_model_cache_readiness,
    check_python_runtime,
    check_sqlite_fts5,
    format_doctor_report,
    run_doctor_checks,
    run_doctor_cli,
)
from app.cli.main import main


def test_check_python_runtime() -> None:
    res = check_python_runtime()
    assert res["name"] == "Python Runtime"
    assert res["status"] in ("PASS", "FAIL")
    assert "Python 3." in res["details"]
    assert res["compatible"] is True


def test_check_ffmpeg() -> None:
    res = check_ffmpeg()
    assert res["name"] == "FFmpeg & ffprobe"
    assert res["status"] in ("PASS", "WARN")
    assert "ffmpeg" in res["details"].lower()


def test_check_sqlite_fts5() -> None:
    res = check_sqlite_fts5()
    assert res["name"] == "SQLite FTS5 Full-Text Search"
    assert res["status"] == "PASS"
    assert "FTS5" in res["details"]


def test_check_disk_space_and_permissions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.DATA_DIR", str(tmp_path))
    res = check_disk_space_and_permissions()
    assert res["name"] == "Storage & Permissions"
    assert res["status"] in ("PASS", "WARN")
    assert res["free_gb"] > 0
    # Probe file must be removed cleanly
    assert not (tmp_path / ".arova_doctor_write_probe").exists()


def test_check_model_cache_readiness() -> None:
    res = check_model_cache_readiness()
    assert res["name"] == "Model Cache Readiness"
    assert res["status"] in ("PASS", "INFO")
    assert "HuggingFace cache:" in res["details"]
    assert "faster-whisper cache:" in res["details"]


def test_check_mcp_server_readiness() -> None:
    res = check_mcp_server_readiness()
    assert res["name"] == "Model Context Protocol (MCP)"
    assert res["status"] == "PASS"
    assert res["tool_count"] == 8
    assert "8 read-only tools verified" in res["details"]


def test_run_doctor_checks_structure() -> None:
    report = run_doctor_checks()
    assert "overall_status" in report
    assert report["overall_status"] in ("HEALTHY", "WARNING", "CRITICAL")
    assert "is_healthy" in report
    assert isinstance(report["checks"], list)
    assert len(report["checks"]) == 6

    formatted = format_doctor_report(report)
    assert "AROVA CREATOR INTELLIGENCE — SYSTEM DIAGNOSTIC (DOCTOR)" in formatted
    assert report["overall_status"] in formatted


def test_doctor_cli_text_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    # Test text output
    exit_code_text = run_doctor_cli(as_json=False)
    assert exit_code_text == 0
    captured_text = capsys.readouterr().out
    assert "AROVA CREATOR INTELLIGENCE" in captured_text
    assert "[OK]" in captured_text or "[WARN]" in captured_text

    # Test json output
    exit_code_json = run_doctor_cli(as_json=True)
    assert exit_code_json == 0
    captured_json = capsys.readouterr().out
    parsed = json.loads(captured_json)
    assert parsed["is_healthy"] is True
    assert len(parsed["checks"]) == 6


def test_main_cli_dispatcher_doctor(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["doctor", "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert "overall_status" in parsed


def test_doctor_is_strictly_non_destructive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Place a sample file in data dir and verify it remains untouched
    test_data = tmp_path / "data"
    test_data.mkdir()
    sample_file = test_data / "source_sample.mp4"
    sample_file.write_bytes(b"pseudo_video_data_12345")
    initial_stat = sample_file.stat()

    monkeypatch.setattr("app.core.config.settings.DATA_DIR", str(test_data))

    report = run_doctor_checks()
    assert report["is_healthy"] is True

    # Confirm sample file was untouched
    after_stat = sample_file.stat()
    assert sample_file.read_bytes() == b"pseudo_video_data_12345"
    assert initial_stat.st_size == after_stat.st_size
