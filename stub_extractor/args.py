from argparse import ArgumentParser
from dataclasses import dataclass
from typing import List


@dataclass
class Args:
    files: List[str]


def parse_args() -> Args:
    parser = ArgumentParser(description="Extract type stubs from Python source files.")
    parser.add_argument(
        "files", metavar="FILE", nargs="*", help="Python source files to parse"
    )
    args = parser.parse_args()
    return Args(args.files)
