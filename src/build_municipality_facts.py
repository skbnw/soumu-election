#!/usr/bin/env python3
"""Compatibility wrapper for municipality_facts parquet builder."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soumu_election.municipality import main


if __name__ == "__main__":
    raise SystemExit(main())
