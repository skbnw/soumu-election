#!/usr/bin/env python3
"""Backward-compatible entry point. New code lives in soumu_election.download."""

from soumu_election.download import main


if __name__ == "__main__":
    raise SystemExit(main())
