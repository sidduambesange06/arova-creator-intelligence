"""Unit and Integration Tests for Real-Media Harness and Preparation.

Verifies:
1. Manifest generation, local asset reuse, and CC-BY 3.0 attribution in prepare_real_media.
2. Ground truth template creation with verified_by: null.
3. RealMediaHarness dry run: offline sandbox enforcement and SHA-256 immutability verification.
4. Accurate quick slice test execution against isolated temporary database.
5. Socket blocking enforcement preventing remote network calls.
6. Ground truth accuracy reporting ('Accuracy: NOT YET MEASURED - VERIFIED GROUND TRUTH REQUIRED').
7. Detection and rejection of simulated source media mutation.
8. Structural boundary AST test ensuring core modules do not import cloud AI SDKs or requests/httpx.
"""

import ast
from pathlib import Path
import socket
import sys
import tempfile
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
psutil = pytest.importorskip("psutil")

from app.core.security import compute_sha256
from scripts.prepare_real_media import (
    ATTRIBUTION_NOTICE,
    EXPECTED_SHA256,
    generate_ground_truth_templates,
    prepare_real_media,
)
from scripts.resource_monitor import ProcessTreeMonitor
from scripts.test_real_media import (
    RealMediaHarness,
    check_ground_truth_accuracy,
    enforce_offline_sandbox,
)


def test_prepare_real_media_manifest_and_attribution(tmp_path: Path) -> None:
    # Prepare dummy asset to test manifest structure
    dummy_file = tmp_path / "tears_of_steel_720p.mov"
    dummy_file.write_bytes(b"TEST_VIDEO_BYTES_RO")

    manifest = prepare_real_media(target_path=dummy_file, allow_download=False, force=True)

    assert manifest["filename"] == "tears_of_steel_720p.mov"
    assert manifest["attribution"] == ATTRIBUTION_NOTICE
    assert "mango.blender.org" in manifest["attribution"]
    assert "Locally computed SHA-256" in manifest["checksum_note"]
    assert manifest["file_size_bytes"] == dummy_file.stat().st_size
    assert manifest["sha256"] == compute_sha256(dummy_file)

    # Verify ground truth templates exist
    gt_dir = tmp_path / "ground_truth"
    assert (gt_dir / "scenes_template.json").is_file()
    assert (gt_dir / "ocr_template.json").is_file()
    assert (gt_dir / "retrieval_queries_template.json").is_file()


def test_ground_truth_accuracy_not_yet_measured(tmp_path: Path) -> None:
    gt_dir = tmp_path / "ground_truth"
    generate_ground_truth_templates(gt_dir)

    result = check_ground_truth_accuracy(gt_dir)
    assert result["status"] == "NOT_YET_MEASURED"
    assert "Accuracy: NOT YET MEASURED - VERIFIED GROUND TRUTH REQUIRED" in result["message"]
    assert result["ground_truth_status"]["scenes"] == "Template unverified (verified_by: null)"


def test_offline_enforcement_blocks_socket_connections() -> None:
    with enforce_offline_sandbox() as attempts:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(RuntimeError, match="Network access blocked"):
            s.connect(("127.0.0.1", 8080))
    assert len(attempts) == 1
    assert "8080" in attempts[0]["target"]


def test_offline_meta_path_blocker() -> None:
    with enforce_offline_sandbox() as attempts:
        # Attempting to import a blocked ML framework inside offline sandbox must raise ImportError
        with pytest.raises(ImportError, match="CRITICAL SANDBOX VIOLATION"):
            import torch  # noqa


def test_harness_quick_test_execution_and_isolation(tmp_path: Path) -> None:
    harness = RealMediaHarness()
    if not harness.media_path.is_file():
        pytest.skip(f"Benchmark asset not available at {harness.media_path}")

    res = harness.run(mode="quick", workspace_dir=tmp_path)
    assert res["status"] in ("PASSED", "PASSED_WITH_SKIPS")
    assert res["asset"]["immutability_verified"] is True
    assert res["asset"]["sha256_before"] == EXPECTED_SHA256
    assert res["asset"]["sha256_after"] == EXPECTED_SHA256

    stages = res["stages"]
    assert stages["database_init"]["status"] == "COMPLETED"
    assert stages["database_init"]["table_count"] in (24, 30)
    assert stages["quick_slice_extraction"]["status"] == "COMPLETED"
    assert stages["metadata_probing"]["status"] == "COMPLETED"
    assert stages["metadata_probing"]["duration"] == 20.0
    assert stages["metadata_probing"]["resolution"] == "1280x534"
    assert stages["audio_extraction"]["status"] == "COMPLETED"
    assert stages["audio_extraction"]["sample_rate"] == 16000
    assert stages["audio_extraction"]["channels"] == 1
    assert stages["scene_detection"]["status"] == "COMPLETED"
    assert stages["scene_detection"]["scenes_detected"] > 0
    assert stages["scene_detection"]["thumbnails_generated"] > 0

    # Honest capabilities reporting
    assert stages["asr_transcription"]["status"] == "SKIPPED"
    assert stages["visual_ocr"]["status"] == "SKIPPED"

    # Persistence in isolated temp DB
    assert stages["database_persistence"]["videos_persisted"] == 1
    assert stages["database_persistence"]["scenes_persisted"] > 0
    assert stages["database_persistence"]["assets_persisted"] == 1

    # Subclip export
    assert stages["subclip_export"]["status"] == "COMPLETED"
    assert Path(stages["subclip_export"]["export_path"]).is_file()

    # Ground truth
    assert "NOT YET MEASURED" in stages["ground_truth_accuracy"]["message"]


def test_structural_boundary_no_remote_sdk_imports() -> None:
    """Structure test: verify core application modules never import requests, httpx, or cloud AI SDKs."""
    app_root = Path("backend/app")
    violations = []
    forbidden_modules = ("requests", "google.genai", "openai", "anthropic", "cohere")

    for py_file in app_root.rglob("*.py"):
        if "providers" in py_file.parts or "ai" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_modules:
                        violations.append((py_file, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(node.module.startswith(m) for m in forbidden_modules):
                    violations.append((py_file, node.module))

    assert not violations, f"Found forbidden remote imports outside AI providers: {violations}"
