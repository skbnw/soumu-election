#!/usr/bin/env python3
# Probe sangiin26 municipality page links + discover()
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import USER_AGENT, discover, get  # noqa: E402


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    url = "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin26/sangiin26_8_01.html"
    response = get(session, url)
    response.encoding = response.apparent_encoding or "shift_jis"
    soup = BeautifulSoup(response.text, "html.parser")
    print("=== Hokkaido page anchors ===")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        text = anchor.get_text(" ", strip=True)
        if re.search(r"\.xls[x]?$", href, re.I) or any(k in text for k in ("選挙", "比例", "政党", "候補")):
            print(repr(text), "->", urljoin(url, href))

    print("\n=== discover sangiin 26 ===")
    pages, links = discover(session, 26, chamber="sangiin")
    print("pages:", pages)
    summary = [x for x in links if x["page_kind"] == "summary"]
    muni = [x for x in links if x["page_kind"] == "municipality_votes"]
    print("summary", len(summary), "muni", len(muni))
    print("muni categories", Counter(x["category"] for x in muni))
    for item in muni:
        if "北海道" in item["label"] or "8_01" in item["url"] or "/01" in item["url"]:
            print("HKD", item["source_code"], item["category"], item["label"], item["url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
