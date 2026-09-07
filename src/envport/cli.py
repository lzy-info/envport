"""Command line entry point. Report failures exit 1; usage/input errors exit 2."""

import argparse
from contextlib import redirect_stdout
import importlib
import json
from pathlib import Path
import sys

from .demo import BrokenCounterEnvironment, CounterEnvironment
from .doctor import doctor
from .trajectory import validate_trajectory


def _factory(value):
    if value.count(":") != 1:
        raise ValueError("factory must be module:callable (trusted local Python only)")
    module, name = value.split(":")
    if not module or not name or not all(p.isidentifier() for p in module.split(".")) or not name.isidentifier():
        raise ValueError("factory must use a dotted module name and a callable name")
    result = getattr(importlib.import_module(module), name)
    if not callable(result):
        raise ValueError("factory target is not callable")
    return result


def _reject_constant(value):
    raise ValueError(f"non-standard JSON number {value} is not allowed")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load(path):
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("trajectory exceeds the 10 MiB input limit")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_constant,
                      object_pairs_hook=_unique_object)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="envport", description="Sample environment behavior and validate trajectory structure.")
    sub = parser.add_subparsers(dest="command", required=True)
    doc = sub.add_parser("doctor", help="run bounded environment probes")
    source = doc.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", choices=("good", "bad"))
    source.add_argument("--factory", help="trusted local module:callable; runs arbitrary Python in this process")
    doc.add_argument("--seed", type=int, default=7)
    val = sub.add_parser("validate-trajectory", help="schema-only JSON validation; does not check gradient flow")
    val.add_argument("path", type=Path)
    for command in (doc, val):
        command.add_argument("--format", choices=("text", "json"), default="text")
        command.add_argument("--output", type=Path, help="write a JSON report to a new file (existing files are not overwritten)")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            # Keep third-party diagnostic prints out of machine-readable stdout.
            with redirect_stdout(sys.stderr):
                if args.factory:
                    factory, label = _factory(args.factory), args.factory
                else:
                    factory = CounterEnvironment if args.demo == "good" else BrokenCounterEnvironment
                    label = f"demo:{args.demo}"
                result = doctor(factory, seed=args.seed, source=label)
        else:
            result = validate_trajectory(_load(args.path))
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(serialized)
        if args.format == "json":
            print(serialized, end="")
        else:
            counts = result["summary"]
            print(f"EnvPort {result['kind']}: {result['status'].upper()} "
                  f"({counts['pass']} pass, {counts['fail']} fail, {counts['skip']} skip)")
            for check in result["checks"]:
                print(f"  {check['status'].upper():4}  {check['name']}: {check['detail']}")
            print(result["scope"])
        return 1 if result["status"] == "fail" else 0
    except Exception as exc:
        print(f"envport: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
