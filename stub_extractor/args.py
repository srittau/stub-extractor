from argparse import ArgumentParser
from dataclasses import dataclass
from typing import List


@dataclass
class Args:
    files: List[str]
    overwrite: bool = False


def parse_args() -> Args:
    parser = ArgumentParser(description="Extract type stubs from Python source files.")
    parser.add_argument(
        "files",
        metavar="FILE",
        nargs="*",
        help="Python source files or directories",
    )
    parser.add_argument(
        "-w",
        "--overwrite",
        dest="overwrite",
        action="store_true",
        help="overwrite existing stub files",
    )
    args = parser.parse_args()
    return Args(args.files, overwrite=args.overwrite)
