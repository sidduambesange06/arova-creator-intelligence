"""CLI command handler for 'arova scan'."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from app.core.config import settings
from app.database.session import SessionLocal, init_db
from app.services.discovery_service import (
    create_or_get_library,
    register_library_root,
    run_root_media_scan,
)


def run_scan_cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arova scan",
        description="Scan and index media folder into deterministic library memory.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to media directory within allowed media roots",
    )
    parser.add_argument(
        "--library",
        default="Default Library",
        help="Target library label (default: 'Default Library')",
    )
    parser.add_argument(
        "--policy",
        default="local_only",
        choices=["local_only", "allow_remote", "quarantined"],
        help="Root execution policy (default: 'local_only')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output scan results in structured JSON format",
    )

    args = parser.parse_args(argv)

    target_path = args.path
    if not target_path:
        first_allowed = settings.ALLOWED_MEDIA_ROOTS.split(",")[0].strip()
        target_path = first_allowed

    init_db()
    with SessionLocal() as db:
        try:
            lib = create_or_get_library(db, label=args.library)
            root = register_library_root(
                db=db,
                library_id=lib.id,
                path=target_path,
                policy=args.policy,
            )
            scan_run = run_root_media_scan(db=db, root_id=root.id)
            counts = json.loads(scan_run.counts) if scan_run.counts else {}

            if args.json:
                out = {
                    "scan_id": scan_run.id,
                    "root_id": root.id,
                    "path": root.volume_id,
                    "status": scan_run.status,
                    "counts": counts,
                    "started_at": scan_run.started_at.isoformat() if scan_run.started_at else None,
                    "finished_at": scan_run.finished_at.isoformat() if scan_run.finished_at else None,
                }
                print(json.dumps(out, indent=2))
                return 0

            print("==========================================================================================")
            print(f"Arova Media Discovery Scan Completed ({scan_run.status.upper()})")
            print("==========================================================================================")
            print(f"Root ID:            {root.id}")
            print(f"Root Path:          {root.volume_id}")
            print(f"Scanned Files:      {counts.get('scanned_files', 0)}")
            print(f"Discovered Media:   {counts.get('discovered_media', 0)}")
            print(f"New Assets:         {counts.get('new_assets', 0)}")
            print(f"New Versions:       {counts.get('new_versions', 0)}")
            print(f"New Locations:      {counts.get('new_locations', 0)}")
            print(f"Updated Locations:  {counts.get('updated_locations', 0)}")
            print(f"Missing Locations:  {counts.get('missing_locations', 0)}")
            print(f"Relocated Files:    {counts.get('relocated_locations', 0)}")
            print(f"Errors:             {counts.get('errors', 0)}")
            print("==========================================================================================")
            return 0

        except Exception as exc:
            if args.json:
                print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
            else:
                print(f"Error executing media scan: {exc}", file=sys.stderr)
            return 1
