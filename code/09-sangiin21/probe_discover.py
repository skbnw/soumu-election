#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import USER_AGENT, discover, get  # noqa: E402

BASE = "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin21/"


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    for name in ("index.html", "index_1.html", "sangiin21_8.html", "sangiin21_7.html", "shikuchouson.html"):
        try:
            r = get(session, BASE + name)
            print("OK", r.status_code, len(r.content), name)
        except Exception as exc:
            print("FAIL", name, type(exc).__name__)

    pages, links = discover(session, 21, chamber="sangiin")
    summary = [x for x in links if x["page_kind"] == "summary"]
    muni = [x for x in links if x["page_kind"] == "municipality_votes"]
    print("pages", pages)
    print("summary", len(summary), "muni", len(muni), Counter(x["category"] for x in muni))
    print("summary codes", Counter((x.get("source_code") or "?")[:5] for x in summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
