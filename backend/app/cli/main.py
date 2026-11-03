import argparse
import sys
from typing import Sequence

from app.cli.demo import run_demo_cli
from app.cli.doctor import run_doctor_cli

try:
    from app.cli.models import run_models_cli
except ImportError:
    run_models_cli = None


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

    # arova demo
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
    demo_parser.add_argument(
        "--query",
        type=str,
        default="demo",
        help="Natural language query to test against indexed demo clip (default: 'demo')",
    )
    demo_parser.add_argument(
        "--json",
        action="store_true",
        help="Output demo execution results in structured JSON format",
    )
    demo_parser.add_argument(
        "--clean",
        action="store_true",
        help="Automatically clean up synthetic test files and index after completion",
    )

    # arova models
    models_parser = subparsers.add_parser(
        "models",
        help="Manage speech-to-text models (list, catalog, install, verify, remove)",
    )
    models_parser.add_argument(
        "models_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to models manager",
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
        return run_demo_cli(
            duration=args.duration,
            query=args.query,
            as_json=args.json,
            keep_demo=not args.clean,
        )

    if args.subcommand == "models":
        if run_models_cli is not None:
            return run_models_cli(argv=args.models_args)
        print("Models manager is not available in base installation.", file=sys.stderr)
        return 1

    parser.print_help()
    return 0



if __name__ == "__main__":
    sys.exit(main())
