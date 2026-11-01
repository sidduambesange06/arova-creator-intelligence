import json
from pathlib import Path
import pytest

from app.cli.demo import run_demo_cli, run_demo_workflow, synthesize_synthetic_clip
from app.cli.main import main


def test_synthesize_synthetic_clip(tmp_path: Path) -> None:
    target = tmp_path / "synthetic_test.mp4"
    result = synthesize_synthetic_clip(target, duration=1.0)
    assert result.is_file()
    assert result.stat().st_size > 0


def test_run_demo_workflow_execution(tmp_path: Path) -> None:
    report = run_demo_workflow(duration=1.5, query="speech", clean_after=True)
    assert report["status"] == "SUCCESS"
    assert "video_id" in report
    assert report["total_elapsed_sec"] < 15.0  # Must complete rapidly
    assert "pipeline_sec" in report["timings"]
    assert "search_sec" in report["timings"]
    assert "qa_sec" in report["timings"]
    assert len(report["citations"]) >= 0


def test_run_demo_cli_text_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    # Text output test
    exit_text = run_demo_cli(duration=1.0, query="video", as_json=False, keep_demo=False)
    assert exit_text == 0
    text_out = capsys.readouterr().out
    assert "5-MINUTE FIRST-USE DEMO" in text_out
    assert "Verification: First-use workflow is 100% operational" in text_out

    # JSON output test
    exit_json = run_demo_cli(duration=1.0, query="video", as_json=True, keep_demo=False)
    assert exit_json == 0
    json_out = capsys.readouterr().out
    parsed = json.loads(json_out)
    assert parsed["status"] == "SUCCESS"
    assert "total_elapsed_sec" in parsed


def test_main_cli_dispatcher_demo(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["demo", "--duration", "1.0", "--clean", "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed["status"] == "SUCCESS"
