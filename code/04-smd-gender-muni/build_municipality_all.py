# v1.2.0: 本体は soumu_election.municipality へ移行。互換ラッパーのみ残す。
"""Backward-compatible entry point for municipality parquet build."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.municipality import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["--project-root", str(ROOT), *sys.argv[1:]]))
