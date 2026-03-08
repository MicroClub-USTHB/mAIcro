"""Compatibility wrapper for `python ingest.py` in a src-layout project."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from maicro.cli import ingest_main


if __name__ == "__main__":
    ingest_main()
