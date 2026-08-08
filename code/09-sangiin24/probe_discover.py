#!/usr/bin/env python3
# Probe sangiin24 discoverability (summary + municipality tree)
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
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin24/index.html",
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin24/sangiin24_8.html",
        "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin24/shikuchouson.html",
    ):
        try:
            r = get(session, url)
            print("OK", r.status_code, len(r.content), url)
        except Exception as exc:
            print("FAIL", type(exc).__name__, exc)

    pages, links = discover(session, 24, chamber="sangiin")
    summary = [x for x in links if x["page_kind"] == "summary"]
    muni = [x for x in links if x["page_kind"] == "municipality_votes"]
    print("pages", pages)
    print("summary", len(summary), "muni", len(muni))
    print("muni categories", Counter(x["category"] for x in muni))
    print("summary sample codes", Counter((x.get("source_code") or "?")[:5] for x in summary))
    for item in muni[:3]:
        print("muni", item["source_code"], item["label"], item["url"][-50:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
