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

BASE = "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin22/"


def show_page(session: requests.Session, name: str) -> None:
    url = BASE + name
    r = get(session, url)
    r.encoding = r.apparent_encoding or "shift_jis"
    soup = BeautifulSoup(r.text, "html.parser")
    files = []
    htmls = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        text = a.get_text(" ", strip=True)[:70]
        low = href.lower()
        if any(low.endswith(ext) for ext in (".xls", ".xlsx", ".pdf")):
            files.append((text, href))
        elif "sangiin22" in low and low.endswith(".html"):
            htmls.append((text, href))
    print(f"=== {name} files={len(files)} html={len(htmls)} ===")
    for text, href in files[:8]:
        print(" F", text, "->", href.rsplit("/", 1)[-1])
    for text, href in htmls:
        if "市区" in text or "_7" in href or "index" in href:
            print(" H", text, "->", href.rsplit("/", 1)[-1])


def main() -> int:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    show_page(session, "index.html")
    show_page(session, "index_1.html")
    show_page(session, "sangiin22_7.html")

    pages, links = discover(session, 22, chamber="sangiin")
    summary = [x for x in links if x["page_kind"] == "summary"]
    muni = [x for x in links if x["page_kind"] == "municipality_votes"]
    print("discover pages", pages)
    print("summary", len(summary), "muni", len(muni), Counter(x["category"] for x in muni))
    print("summary codes", Counter((x.get("source_code") or "?") for x in summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
