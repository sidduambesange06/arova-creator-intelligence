"""CLI command handler for 'arova models' (list, catalog, install, verify, remove)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from app.ai.models_registry import (
    DEFAULT_MODELS,
    download_and_install_model,
    get_model_preflight,
    get_models_home,
    load_registry,
    remove_installed_model,
    verify_installed_model,
)


def format_bytes(b: int | float) -> str:
    val = float(b)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if val < 1024:
            return f"{val:.1f} {unit}" if unit in ("MB", "GB", "TB") else f"{int(val)} {unit}"
        val /= 1024
    return f"{val:.1f} PB"


def cmd_list(args: argparse.Namespace) -> int:
    registry = load_registry()
    if args.json:
        data = {mid: meta.__dict__ for mid, meta in registry.items()}
        print(json.dumps(data, indent=2))
        return 0

    print("==========================================================================================")
    print(f"{'MODEL ID':<24} {'FORMAT':<12} {'SIZE':<12} {'STATUS':<20} {'LANGUAGES'}")
    print("==========================================================================================")
    for mid, meta in registry.items():
        sz = format_bytes(meta.installed_size_bytes or meta.estimated_size_bytes)
        langs = ", ".join(meta.supported_languages[:5])
        if len(meta.supported_languages) > 5:
            langs += f" (+{len(meta.supported_languages) - 5})"
        print(f"{meta.model_id:<24} {meta.format:<12} {sz:<12} {meta.install_status:<20} {langs}")
    print("==========================================================================================")
    print(f"Models storage directory: {get_models_home()}")
    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    if args.json:
        data = {mid: meta.__dict__ for mid, meta in DEFAULT_MODELS.items()}
        print(json.dumps(data, indent=2))
        return 0

    print("==========================================================================================")
    print("Arova Speech-to-Text Model Catalog (Offline Reference Candidates)")
    print("==========================================================================================")
    for mid, meta in DEFAULT_MODELS.items():
        sz = format_bytes(meta.estimated_size_bytes)
        print(f"Model ID:        {meta.model_id}")
        print(f"Hugging Face:    {meta.repo_id} (rev: {meta.commit_revision[:12]}...)")
        print(f"License:         {meta.license} ({meta.license_url})")
        print(f"Model Card:      {meta.model_card_url}")
        print(f"Estimated Size:  {sz}")
        print(f"Languages:       {', '.join(meta.supported_languages)}")
        print(f"Min RAM:         {meta.min_ram_mb} MB")
        print("------------------------------------------------------------------------------------------")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    model_id = args.model_id
    try:
        preflight = get_model_preflight(model_id)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("==========================================================================================")
    print(f"Preflight Verification: {model_id}")
    print("==========================================================================================")
    print(f"Repository:            {preflight['repo_id']}")
    print(f"Commit Revision:       {preflight['commit_revision']}")
    print(f"License:               {preflight['license']} ({preflight['license_url']})")
    print(f"Model Card:            {preflight['model_card_url']}")
    print(f"Estimated Download:    {format_bytes(preflight['estimated_size_bytes'])}")
    print(f"Expected Size:         {format_bytes(preflight['expected_installed_size_bytes'])}")
    print(f"Destination:           {preflight['destination_directory']}")
    print(f"HF Cache:              {preflight['cache_directory']}")
    print(f"Current Footprint:     {format_bytes(preflight['current_allocated_bytes'])} (Cap: {format_bytes(preflight['budget_cap_bytes'])})")
    print(f"Projected Footprint:   {format_bytes(preflight['projected_allocated_bytes'])}")
    print(f"Current Free Disk:     {format_bytes(preflight['current_free_bytes'])} (Floor: {format_bytes(preflight['free_floor_bytes'])})")
    print(f"Projected Free Disk:   {format_bytes(preflight['projected_free_bytes'])}")
    print(f"Min System RAM:        {preflight['min_ram_mb']} MB")
    print(f"Compute Type:          {preflight['quantization']}")
    print("==========================================================================================")

    if not preflight["can_install"]:
        print("HARD STOP: Preflight budget check failed!", file=sys.stderr)
        for r in preflight["rejection_reasons"]:
            print(f"  - {r}", file=sys.stderr)
        return 1

    if not args.yes:
        try:
            resp = input(f"Proceed with downloading and installing '{model_id}'? [y/N]: ").strip().lower()
            if resp not in ("y", "yes"):
                print("Installation aborted by user.")
                return 1
        except (KeyboardInterrupt, EOFError):
            print("\nInstallation aborted.")
            return 1

    try:
        meta = download_and_install_model(model_id)
        print(f"\nSuccessfully installed and verified '{model_id}'!")
        print(f"Path: {meta.installed_path}")
        print(f"Installed Size: {format_bytes(meta.installed_size_bytes)}")
        print(f"Inventory: {len(meta.files_inventory)} files hashed with SHA-256")
        return 0
    except Exception as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1


def cmd_verify(args: argparse.Namespace) -> int:
    model_id = args.model_id
    print(f"Verifying model '{model_id}'...")
    ok, msg = verify_installed_model(model_id)
    if ok:
        print(f"PASS: {msg}")
        return 0
    else:
        print(f"FAIL: {msg}", file=sys.stderr)
        return 1


def cmd_remove(args: argparse.Namespace) -> int:
    model_id = args.model_id
    registry = load_registry()
    if model_id not in registry:
        print(f"Error: Unknown model '{model_id}'", file=sys.stderr)
        return 1

    meta = registry[model_id]
    models_home = get_models_home()
    dest_dir = models_home / model_id

    print(f"Target removal directory: {dest_dir}")
    if not dest_dir.exists():
        print(f"Model directory does not exist on disk.")
        remove_installed_model(model_id)
        return 0

    if not args.yes:
        try:
            resp = input(f"Are you sure you want to permanently delete {dest_dir}? [y/N]: ").strip().lower()
            if resp not in ("y", "yes"):
                print("Removal aborted by user.")
                return 1
        except (KeyboardInterrupt, EOFError):
            print("\nRemoval aborted.")
            return 1

    ok, msg = remove_installed_model(model_id)
    if ok:
        print(f"SUCCESS: {msg}")
        return 0
    else:
        print(f"FAIL: {msg}", file=sys.stderr)
        return 1


def run_models_cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arova models",
        description="Manage local speech-to-text models for Arova Creator Intelligence",
    )
    subparsers = parser.add_subparsers(dest="models_action", help="Models subcommands")

    # list
    list_p = subparsers.add_parser("list", help="List registered models and local installation status")
    list_p.add_argument("--json", action="store_true", help="Output in structured JSON format")

    # catalog
    cat_p = subparsers.add_parser("catalog", help="List available model candidates and metadata")
    cat_p.add_argument("--json", action="store_true", help="Output in structured JSON format")

    # install
    inst_p = subparsers.add_parser("install", help="Download and verify a model at pinned revision")
    inst_p.add_argument("model_id", help="Model ID to install (e.g. faster-whisper-small)")
    inst_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # verify
    ver_p = subparsers.add_parser("verify", help="Verify integrity and runtime load of an installed model")
    ver_p.add_argument("model_id", help="Model ID to verify")

    # remove
    rem_p = subparsers.add_parser("remove", help="Safely remove an installed model directory")
    rem_p.add_argument("model_id", help="Model ID to remove")
    rem_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args(argv)
    if not args.models_action:
        parser.print_help()
        return 0

    if args.models_action == "list":
        return cmd_list(args)
    elif args.models_action == "catalog":
        return cmd_catalog(args)
    elif args.models_action == "install":
        return cmd_install(args)
    elif args.models_action == "verify":
        return cmd_verify(args)
    elif args.models_action == "remove":
        return cmd_remove(args)

    parser.print_help()
    return 0

