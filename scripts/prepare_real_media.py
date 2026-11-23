"""Real-Media Preparation Script for Arova Creator Intelligence.

Prepares the Tears of Steel (720p) benchmark video asset strictly according to
the canonical real-media corpus rules:
1. Reuses existing local files (e.g., C:\\Arova-Benchmark\\media\\tears_of_steel_720p.mov
   or TEARS_OF_STEEL_PATH) without modifying, moving, or overwriting them.
2. Never downloads automatically at startup or during unit tests.
3. Supports explicit --download only when requested and when no local cache exists.
4. Enforces filesystem read-only permissions on the prepared asset.
5. Computes local SHA-256 and writes a complete manifest with CC-BY 3.0 attribution:
   (cc) Blender Foundation | mango.blender.org
6. Generates empty human ground truth templates.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import urllib.request

# Default paths
DEFAULT_BENCHMARK_PATH = Path(r"C:\Arova-Benchmark\media\tears_of_steel_720p.mov")
DEFAULT_TARGET_REL = Path("testdata/real_media/tears_of_steel/tears_of_steel_720p.mov")
OFFICIAL_SOURCE_URL = "https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov"
OFFICIAL_PROJECT_URL = "https://mango.blender.org/about/"
EXPECTED_SHA256 = "efa9062d9cdb7a338e40ad530dfdf234806743f29ae6a1a136b97ece4e588e8f"
ATTRIBUTION_NOTICE = "(cc) Blender Foundation | mango.blender.org"
LICENSE_NOTICE = "Creative Commons Attribution 3.0 Unported (CC BY 3.0)"


def compute_sha256(file_path: Path, chunk_size: int = 1024 * 1024 * 4) -> str:
    """Compute streaming SHA-256 hash of a file."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().lower()


def make_readonly(file_path: Path) -> None:
    """Enforce read-only permissions on filesystem."""
    try:
        os.chmod(file_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except Exception as exc:
        print(f"[WARN] Could not set read-only permissions on {file_path}: {exc}")


def generate_ground_truth_templates(gt_dir: Path) -> None:
    """Create empty human ground truth templates."""
    gt_dir.mkdir(parents=True, exist_ok=True)

    scenes_path = gt_dir / "scenes_template.json"
    if not scenes_path.exists():
        scenes_data = {
            "asset": "tears_of_steel_720p.mov",
            "verified_by": None,
            "verification_date": None,
            "note": "GROUND TRUTH IS HUMAN-SUPPLIED. Fill scene boundaries only with human verification.",
            "scenes": [
                {
                    "scene_index": 0,
                    "start_time_sec": 0.0,
                    "end_time_sec": 0.0,
                    "description": "Example boundary template - replace with human-verified cut",
                }
            ],
        }
        scenes_path.write_text(json.dumps(scenes_data, indent=2), encoding="utf-8")

    ocr_path = gt_dir / "ocr_template.json"
    if not ocr_path.exists():
        ocr_data = {
            "asset": "tears_of_steel_720p.mov",
            "verified_by": None,
            "verification_date": None,
            "note": "GROUND TRUTH IS HUMAN-SUPPLIED. Frame OCR text must be human-verified.",
            "frames": [
                {
                    "timestamp_sec": 0.0,
                    "expected_text": "Example OCR ground truth string",
                    "bounding_boxes": [],
                }
            ],
        }
        ocr_path.write_text(json.dumps(ocr_data, indent=2), encoding="utf-8")

    queries_path = gt_dir / "retrieval_queries_template.json"
    if not queries_path.exists():
        queries_data = {
            "asset": "tears_of_steel_720p.mov",
            "verified_by": None,
            "verification_date": None,
            "note": "GROUND TRUTH IS HUMAN-SUPPLIED. Minimum 30 human-verified labeled queries per language required.",
            "languages": ["en", "hi", "kn"],
            "queries": [],
        }
        queries_path.write_text(json.dumps(queries_data, indent=2), encoding="utf-8")


def prepare_real_media(
    target_path: Path | None = None,
    allow_download: bool = False,
    force: bool = False,
) -> dict[str, any]:
    """Prepare the Tears of Steel asset and return manifest data."""
    root_dir = Path(__file__).resolve().parent.parent

    # Determine target file location
    if target_path is not None:
        target = target_path.resolve()
    else:
        env_override = os.environ.get("TEARS_OF_STEEL_PATH")
        if env_override and Path(env_override).is_file():
            target = Path(env_override).resolve()
        else:
            target = (root_dir / DEFAULT_TARGET_REL).resolve()

    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"

    # If target exists and not forced, verify integrity
    if target.is_file() and not force:
        actual_hash = compute_sha256(target)
        if actual_hash == EXPECTED_SHA256:
            make_readonly(target)
            if not manifest_path.is_file():
                manifest = {
                    "name": "Tears of Steel (720p)",
                    "filename": target.name,
                    "source_url": OFFICIAL_SOURCE_URL,
                    "project_url": OFFICIAL_PROJECT_URL,
                    "file_size_bytes": target.stat().st_size,
                    "sha256": actual_hash,
                    "checksum_note": "Locally computed SHA-256; not an official publisher checksum.",
                    "attribution": ATTRIBUTION_NOTICE,
                    "license": LICENSE_NOTICE,
                    "prepared_at": datetime.now(timezone.utc).isoformat(),
                    "source_origin": "existing_local_target",
                }
                manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            else:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            generate_ground_truth_templates(target_dir / "ground_truth")
            return manifest

    # Find existing local source to reuse
    source_candidate: Path | None = None
    env_path = os.environ.get("TEARS_OF_STEEL_PATH")
    if env_path and Path(env_path).is_file():
        source_candidate = Path(env_path).resolve()
    elif DEFAULT_BENCHMARK_PATH.is_file():
        source_candidate = DEFAULT_BENCHMARK_PATH.resolve()

    source_origin = "unknown"
    if source_candidate and source_candidate.is_file() and source_candidate != target:
        print(f"[INFO] Reusing existing local asset: {source_candidate}")
        # Copy safely to isolated test target without altering source
        shutil.copyfile(source_candidate, target)
        source_origin = f"reused_from_local_cache ({source_candidate})"
    elif not target.is_file():
        if not allow_download:
            raise FileNotFoundError(
                f"Tears of Steel real-media asset not found at '{target}' or '{DEFAULT_BENCHMARK_PATH}'. "
                "Per real-media corpus rules, automatic downloads are disabled. "
                "To download explicitly, run 'python scripts/prepare_real_media.py --download', "
                "or point TEARS_OF_STEEL_PATH to an existing copy."
            )
        print(f"[INFO] Downloading official Tears of Steel asset from {OFFICIAL_SOURCE_URL}...")
        urllib.request.urlretrieve(OFFICIAL_SOURCE_URL, str(target))
        source_origin = f"downloaded_from_blender ({OFFICIAL_SOURCE_URL})"

    # Verify checksum
    actual_hash = compute_sha256(target)
    if actual_hash != EXPECTED_SHA256:
        print(f"[WARN] SHA-256 mismatch: expected {EXPECTED_SHA256}, got {actual_hash}")

    # Enforce read-only
    make_readonly(target)

    # Write manifest
    manifest = {
        "name": "Tears of Steel (720p)",
        "filename": target.name,
        "source_url": OFFICIAL_SOURCE_URL,
        "project_url": OFFICIAL_PROJECT_URL,
        "file_size_bytes": target.stat().st_size,
        "sha256": actual_hash,
        "checksum_note": "Locally computed SHA-256; not an official publisher checksum.",
        "attribution": ATTRIBUTION_NOTICE,
        "license": LICENSE_NOTICE,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "source_origin": source_origin,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    generate_ground_truth_templates(target_dir / "ground_truth")
    print(f"[SUCCESS] Real-media asset prepared: {target} (SHA256: {actual_hash[:16]}...)")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare real-media regression asset (Tears of Steel)")
    parser.add_argument("--target", type=Path, default=None, help="Target location for video file")
    parser.add_argument("--download", action="store_true", help="Explicitly permit download if local asset is missing")
    parser.add_argument("--force", action="store_true", help="Force re-preparation and manifest recreation")
    args = parser.parse_args()

    try:
        manifest = prepare_real_media(
            target_path=args.target,
            allow_download=args.download,
            force=args.force,
        )
        print(json.dumps(manifest, indent=2))
    except Exception as exc:
        print(f"[ERROR] Failed to prepare real media: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
