#!/usr/bin/env python3

import sys

from .extractor import extract


def main() -> None:
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or above required", file=sys.stderr)
        sys.exit(1)
    extract(sys.stdin, sys.stderr)


if __name__ == "__main__":
    main()
