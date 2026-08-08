#!/usr/bin/env python3
# Probe sangiin municipality parsers on Hokkaido samples
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.municipality import (  # noqa: E402
    parse_sangiin_muni_district,
    parse_sangiin_muni_pr_cand,
    parse_sangiin_muni_pr_party,
)

OUT = ROOT / "code" / "09-sangiin26" / "output"


def main() -> int:
    d = parse_sangiin_muni_district(
        OUT / "hokkaido_district.xlsx",
        {"label": "北海道_選挙区", "url": "", "category": "district"},
        26,
    )
    p = parse_sangiin_muni_pr_party(
        OUT / "hokkaido_pr_party.xlsx",
        {"label": "北海道_政党別", "url": "", "category": "pr_party"},
        26,
    )
    c = parse_sangiin_muni_pr_cand(
        OUT / "hokkaido_pr_cand.xlsx",
        {"label": "北海道_候補者別", "url": "", "category": "pr_cand"},
        26,
    )
    print("district", len(d), d[0] if d else None)
    print("pr_party", len(p), p[0] if p else None)
    print("pr_cand", len(c), c[0] if c else None)
    # smoke: 札幌市中央区 大村
    hit = [r for r in d if r["municipality"] == "札幌市中央区" and r["candidate"] == "大村小太郎"]
    print("omura chuo", hit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
