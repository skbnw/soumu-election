#!/usr/bin/env python3
# Probe sangiin25 municipality hub and discover counts
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import USER_AGENT, discover, get  # noqa: E402


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    for url in (
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin25/sangiin25_8.html",
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin25/shikuchouson.html",
    ):
        try:
            r = get(session, url)
            print("OK", url, r.status_code, len(r.content))
        except Exception as exc:
            print("FAIL", url, type(exc).__name__, exc)

    pages, links = discover(session, 25, chamber="sangiin")
    summary = [x for x in links if x["page_kind"] == "summary"]
    muni = [x for x in links if x["page_kind"] == "municipality_votes"]
    print("pages", pages)
    print("summary", len(summary), "muni", len(muni))
    print("muni categories", Counter(x["category"] for x in muni))
    for item in muni[:6]:
        print(item["source_code"], item["category"], item["label"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
