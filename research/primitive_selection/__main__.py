"""Command line entry point for the containerized primitive study."""

from __future__ import annotations

import argparse
from pathlib import Path

from .report import generate
from .runner import run


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="primitive-study")
    sub = result.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke")
    smoke.add_argument("--output", type=Path)
    execute = sub.add_parser("run")
    execute.add_argument("--cohort", choices=("development", "validation"), required=True)
    execute.add_argument("--nonce", help="fresh reviewer nonce; required for validation")
    execute.add_argument("--output", type=Path)
    report = sub.add_parser("report")
    report.add_argument("--input", type=Path, action="append")
    report.add_argument("--output", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "smoke":
        path = run("development", output=args.output, smoke=True, repetitions=1)
    elif args.command == "run":
        if args.cohort == "validation" and not args.nonce:
            raise SystemExit("--nonce is required for the validation cohort")
        path = run(args.cohort, nonce=args.nonce, output=args.output)
    else:
        path = generate(args.input, args.output)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
