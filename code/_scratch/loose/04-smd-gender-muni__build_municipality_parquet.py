# v1.0: 03-14 小選挙区市区町村別得票を parquet 化（第45〜51回）
"""Parse municipality SMD vote workbooks into a compact parquet for the web explorer."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import parse_smd  # noqa: E402

DISTRICT_RE = re.compile(r"第(\d+)区")
PREFECTURE_CODES = {
    name: f"{index:02d}" for index, name in enumerate((
        "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
        "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
        "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
        "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
        "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
        "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
        "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"), 1)
}


def source_code_from_name(name: str) -> str:
    match = re.match(r"(03-14-smd-\d+)", name)
    return match.group(1) if match else "03-14-smd"


def district_number(district: str | None) -> int | None:
    if not district:
        return None
    match = DISTRICT_RE.search(district)
    return int(match.group(1)) if match else None


def load_manifest_urls(kaiji: int) -> dict[str, str]:
    path = ROOT / "data" / f"shugiin{kaiji}" / "manifest.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping = {}
    for item in data.get("sources", []):
        file_name = Path(str(item.get("file", "")).replace("\\", "/")).name
        if file_name:
            mapping[file_name] = item.get("url") or ""
    return mapping


def parse_kaiji(kaiji: int) -> list[dict]:
    raw_dir = ROOT / "data" / f"shugiin{kaiji}" / "raw"
    files = sorted(raw_dir.glob("03-14-smd-*"))
    urls = load_manifest_urls(kaiji)
    rows: list[dict] = []
    for path in files:
        # Label is embedded in filename: 03-14-smd-01_北海道_....
        parts = path.stem.split("_")
        prefecture = parts[1] if len(parts) > 1 else ""
        source = {
            "label": prefecture,
            "url": urls.get(path.name, ""),
            "category": "smd",
        }
        try:
            records = parse_smd(path, source, kaiji)
        except Exception as exc:  # keep going across prefectures
            print(f"FAIL {kaiji} {path.name}: {exc}", flush=True)
            continue
        code = source_code_from_name(path.name)
        for item in records:
            if item.get("row_type") != "reporting_unit":
                continue
            rows.append({
                "election_kaiji": kaiji,
                "contest": "smd",
                "prefecture": item["prefecture"],
                "prefecture_code": PREFECTURE_CODES.get(item["prefecture"]),
                "district_number": district_number(item.get("district")),
                "municipality": item.get("reporting_unit"),
                "candidate": item.get("candidate"),
                "candidate_raw": item.get("candidate_raw"),
                "party": item.get("party"),
                "metric": "candidate_votes",
                "value": item.get("votes"),
                "unit": "votes",
                "source_code": code,
                "source_file": item.get("source_file"),
                "source_url": item.get("source_url") or source["url"],
                "source_sheet": item.get("source_sheet"),
                "source_row": item.get("source_row"),
            })
    return rows


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    summary = []
    for kaiji in range(45, 52):
        print(f"parsing kaiji {kaiji} ...", flush=True)
        rows = parse_kaiji(kaiji)
        summary.append({"kaiji": kaiji, "records": len(rows)})
        print(summary[-1], flush=True)
        all_rows.extend(rows)

    ndjson = out_dir / "smd_municipality_votes.ndjson"
    with ndjson.open("w", encoding="utf-8") as handle:
        for row in all_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    warehouse_dir = ROOT / "data" / "warehouse" / "parquet"
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    web_dir = ROOT / "web" / "data"
    web_dir.mkdir(parents=True, exist_ok=True)
    target = warehouse_dir / "smd_municipality_votes.parquet"
    web_target = web_dir / "smd_municipality_votes.parquet"

    con = duckdb.connect()
    src = ndjson.as_posix().replace("'", "''")
    dst = target.as_posix().replace("'", "''")
    con.execute(f"""
        COPY (
          SELECT * FROM read_json_auto('{src}', format='newline_delimited', union_by_name=true)
        ) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.close()
    web_target.write_bytes(target.read_bytes())

    (out_dir / "summary.json").write_text(
        json.dumps({"total": len(all_rows), "by_kaiji": summary, "parquet_bytes": target.stat().st_size},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print({"total": len(all_rows), "bytes": target.stat().st_size})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
