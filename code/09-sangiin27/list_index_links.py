# v1.0: sangiin27 index のリンク一覧
from pathlib import Path
from urllib.parse import urljoin
import json
import requests
from bs4 import BeautifulSoup

URL = "https://www.soumu.go.jp/senkyo/senkyo_s/data/sangiin27/index.html"
out = Path(__file__).resolve().parent / "output"
out.mkdir(exist_ok=True)

html = requests.get(URL, headers={"User-Agent": "soumu-election/1.0"}, timeout=60)
html.raise_for_status()
soup = BeautifulSoup(html.text, "html.parser")
links = []
for a in soup.select("a[href]"):
    href = a.get("href", "")
    text = " ".join(a.get_text(" ", strip=True).split())
    if not href:
        continue
    full = urljoin(URL, href)
    if any(full.lower().endswith(ext) for ext in (".xlsx", ".xls", ".pdf", ".zip")) or "sangiin27" in full:
        links.append({"text": text, "url": full})

(out / "sangiin27_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")
print("count", len(links))
for item in links[:40]:
    print(item["text"][:60], "=>", item["url"].split("/")[-1])
