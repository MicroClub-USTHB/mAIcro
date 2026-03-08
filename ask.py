"""Compatibility wrapper for `python ask.py` in a src-layout project."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from maicro.cli import ask_main


if __name__ == "__main__":
    ask_main()
