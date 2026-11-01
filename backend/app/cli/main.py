import argparse
import sys
from typing import Sequence

from app.cli.doctor import run_doctor_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arova",
        description="Arova Creator Intelligence — Local-first video intelligence engine CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

    # arova doctor
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Run non-destructive system health diagnostics and prerequisite checks",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="Output diagnostics in structured JSON format",
    )

    # arova demo (placeholder for TASK-007)
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run 5-minute synthetic first-use workflow without external credentials",
    )
    demo_parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Synthetic video duration in seconds (default: 2.0)",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 0

    if args.subcommand == "doctor":
        return run_doctor_cli(as_json=args.json)

    if args.subcommand == "demo":
        print("Command 'arova demo' is scheduled for TASK-007. Run 'arova doctor' for diagnostics.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
