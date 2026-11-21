from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .ui import run


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="scrapix",
        description="TUI downloader for YouTube, Instagram and TikTok.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path.home() / "Downloads" / "Scrapix",
        help="folder tujuan (default: ~/Downloads/Scrapix)",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    raise SystemExit(run(args.output.expanduser()))
