#!/usr/bin/env python3
"""Backward-compatible entry point. New code lives in soumu_election.normalize."""

from soumu_election.normalize import main


if __name__ == "__main__":
    raise SystemExit(main())
