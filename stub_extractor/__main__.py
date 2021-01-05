#!/usr/bin/env python3

import os
import sys

from .args import Args, parse_args
from .extractor import extract


def main() -> None:
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or above required", file=sys.stderr)
        sys.exit(1)
    args = parse_args()
    if len(args.files) == 0:
        extract(sys.stdin, sys.stderr)
    else:
        _parse_files(args)


def _parse_files(args: Args) -> None:
    for filename in args.files:
        if os.path.isdir(filename):
            _parse_directory(args, filename)
        else:
            _extract_file(args, filename)


def _parse_directory(args: Args, filename: str) -> None:
    for dir_path, __, files in os.walk(filename):
        for fn in files:
            if fn.endswith(".py"):
                _extract_file(args, os.path.join(dir_path, fn))


def _extract_file(args: Args, filename: str) -> None:
    target_name = filename + "i" if filename.endswith(".py") else filename + ".pyi"
    try:
        with open(filename) as source:
            try:
                mode = "w" if args.overwrite else "x"
                with open(target_name, mode) as target:
                    try:
                        extract(source, target, filename)
                    except SyntaxError as exc:
                        print(f"WARNING: invalid Python file '{filename}': {exc}")
            except FileExistsError:
                print(f"WARNING: file '{target_name}' already exists")
    except OSError as exc:
        print(f"WARNING: {exc}")


if __name__ == "__main__":
    main()
