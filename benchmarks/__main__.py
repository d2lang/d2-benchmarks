"""Run with python3 -m benchmarks --help."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

from .runner import ROOT, PUBLIC_TOOLS, hardware, inspect_tools, load_toolchain, run


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def nonnegative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproducible D2, Mermaid, Graphviz and PlantUML CLI benchmark")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="check configured tools and display machine metadata without benchmarking")
    doctor.add_argument("--toolchain", type=Path, default=ROOT / ".tools/toolchain.json")
    doctor.add_argument("--tools", nargs="+", default=PUBLIC_TOOLS)
    sub.add_parser("validate", help="verify the frozen corpus and translations without installing tools")
    measure = sub.add_parser("run", help="run serial CLI measurements into a new result directory, then generate a report")
    measure.add_argument("--toolchain", type=Path, help="existing custom toolchain (skips automatic setup)")
    measure.add_argument("--setup", action="store_true", help="install or reuse pinned tools before running (used by ./make.sh)")
    measure.add_argument("--tools", nargs="+", default=PUBLIC_TOOLS)
    measure.add_argument("--formats", nargs="+", choices=["svg", "png"], default=["svg", "png"])
    measure.add_argument("--fixtures", nargs="+")
    measure.add_argument("--warmups", type=nonnegative, default=3)
    measure.add_argument("--repetitions", type=positive, default=20)
    measure.add_argument("--timeout", type=positive, default=120)
    measure.add_argument("--seed", type=int, default=20260905)
    measure.add_argument("--output", type=Path, default=ROOT / "results" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
    measure.add_argument("--label", default="Local benchmark")
    measure.add_argument("--baseline", default="d2-dagre")
    measure.add_argument("--bootstrap", type=positive, default=2000)
    reporting = sub.add_parser("report", help="regenerate reports from retained raw samples")
    reporting.add_argument("run_dir", type=Path)
    reporting.add_argument("--baseline", default="d2-dagre")
    reporting.add_argument("--bootstrap", type=positive, default=2000)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            print(json.dumps({"machine": hardware(), "tools": inspect_tools(load_toolchain(args.toolchain), args.tools)}, indent=2))
        elif args.command == "validate":
            from .corpus import validate_corpus
            result = validate_corpus(ROOT / "corpus")
            print(json.dumps(result, indent=2))
            return int(bool(result.get("errors")))
        else:
            from .report import generate
            if args.command == "run":
                if len(args.tools) != len(set(args.tools)) or len(args.formats) != len(set(args.formats)):
                    raise ValueError("tools and formats cannot contain duplicates")
                if args.toolchain is None:
                    if args.setup:
                        from scripts.setup import ensure_installed
                        ensure_installed(ROOT / ".tools")
                    args.toolchain = ROOT / ".tools/toolchain.json"
                directory, status = run(args)
                generate(directory, baseline=args.baseline, bootstrap=args.bootstrap)
                print(f"Report: {directory / 'index.html'}")
                return status
            generate(args.run_dir.resolve(), baseline=args.baseline, bootstrap=args.bootstrap)
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required")
    raise SystemExit(main())
