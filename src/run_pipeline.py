#!/usr/bin/env python3
"""Public entry point: download → normalize → warehouse → municipality."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soumu_election.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
