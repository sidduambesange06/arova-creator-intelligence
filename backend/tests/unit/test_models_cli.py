"""Unit tests for Arova models CLI and registry boundary."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.ai.models_registry import (
    DEFAULT_MODELS,
    ModelMetadata,
    compute_file_sha256,
    get_model_preflight,
    get_models_home,
    load_registry,
    remove_installed_model,
    save_registry,
)
from app.cli.main import main


def test_models_list_cli(capsys):
    ret = main(["models", "list"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "faster-whisper-small" in captured.out
    assert "MODEL ID" in captured.out


def test_models_catalog_cli(capsys):
    ret = main(["models", "catalog"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Arova Speech-to-Text Model Catalog" in captured.out
    assert "faster-whisper-small" in captured.out
    assert "Apache-2.0" in captured.out


def test_models_catalog_json(capsys):
    ret = main(["models", "catalog", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "faster-whisper-small" in data
    assert data["faster-whisper-small"]["license"] == "Apache-2.0"


def test_preflight_budget_and_rejection():
    # Unknown model should raise ValueError
    with pytest.raises(ValueError, match="Unknown model ID"):
        get_model_preflight("nonexistent-model-xyz")

    preflight = get_model_preflight("faster-whisper-small")
    assert preflight["model_id"] == "faster-whisper-small"
    assert preflight["budget_cap_bytes"] == 15 * 1024 * 1024 * 1024
    assert preflight["free_floor_bytes"] == 5 * 1024 * 1024 * 1024
    assert "can_install" in preflight


def test_models_remove_security_boundary(tmp_path):
    # Security check: attempt to remove a model with path traversal or outside models_home
    ok, msg = remove_installed_model("../outside", models_home=tmp_path)
    assert ok is False
    assert "Security violation" in msg or "Unknown model" in msg


def test_compute_file_sha256(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("arova test content", encoding="utf-8")
    sha = compute_file_sha256(test_file)
    assert len(sha) == 64
    assert sha == compute_file_sha256(test_file)

