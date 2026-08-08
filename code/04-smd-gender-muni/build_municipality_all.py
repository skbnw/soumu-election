# v1.1.0: 小選挙区+比例の市区町村別得票を parquet 化（第45〜51回）
"""Build municipality SMD/PR vote parquets for the web explorer."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.download import parse_pr, parse_smd  # noqa: E402

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


def source_code_from_name(name: str, prefix: str) -> str:
    match = re.match(rf"({prefix}-\d+)", name)
    return match.group(1) if match else prefix


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


def prefecture_from_filename(stem: str, fallback: str = "") -> str:
    parts = stem.split("_")
    if len(parts) < 2:
        return fallback
    label = parts[1]
    # 北海道選挙区 -> 北海道
    for pref in PREFECTURE_CODES:
        if label.startswith(pref.replace("県", "").replace("府", "").replace("都", "")) or label.startswith(pref):
            if pref in label or label.startswith(pref[:2]):
                pass
    if label.endswith("選挙区"):
        base = label.replace("選挙区", "")
        for pref in PREFECTURE_CODES:
            if pref.startswith(base) or base in pref:
                return pref
        return base
    return label if label in PREFECTURE_CODES else fallback or label


def parse_smd_kaiji(kaiji: int) -> list[dict]:
    raw_dir = ROOT / "data" / f"shugiin{kaiji}" / "raw"
    urls = load_manifest_urls(kaiji)
    rows: list[dict] = []
    for path in sorted(raw_dir.glob("03-14-smd-*")):
        parts = path.stem.split("_")
        prefecture = parts[1] if len(parts) > 1 else ""
        source = {"label": prefecture, "url": urls.get(path.name, ""), "category": "smd"}
        try:
            records = parse_smd(path, source, kaiji)
        except Exception as exc:
            print(f"FAIL SMD {kaiji} {path.name}: {exc}", flush=True)
            continue
        code = source_code_from_name(path.name, "03-14-smd")
        for item in records:
            if item.get("row_type") != "reporting_unit":
                continue
            rows.append({
                "election_kaiji": kaiji,
                "category": "小選挙区",
                "contest": "smd",
                "prefecture": item["prefecture"],
                "prefecture_code": PREFECTURE_CODES.get(item["prefecture"]),
                "district_number": district_number(item.get("district")),
                "municipality": item.get("reporting_unit"),
                "subject": item.get("candidate"),
                "candidate": item.get("candidate"),
                "party": item.get("party"),
                "metric": "candidate_votes",
                "value": item.get("votes"),
                "unit": "votes",
                "grain": "municipality",
                "source_code": code,
                "source_file": item.get("source_file"),
            })
    return rows


def parse_pr_kaiji(kaiji: int) -> list[dict]:
    raw_dir = ROOT / "data" / f"shugiin{kaiji}" / "raw"
    urls = load_manifest_urls(kaiji)
    rows: list[dict] = []
    for path in sorted(raw_dir.glob("03-14-pr-*")):
        parts = path.stem.split("_")
        label = parts[1] if len(parts) > 1 else ""
        # For block files label is like 東京都選挙区; parse_pr uses source label for block mapping
        source = {"label": label, "url": urls.get(path.name, ""), "category": "pr"}
        try:
            records = parse_pr(path, source, kaiji)
        except Exception as exc:
            print(f"FAIL PR {kaiji} {path.name}: {exc}", flush=True)
            continue
        code = source_code_from_name(path.name, "03-14-pr")
        for item in records:
            if item.get("row_type") != "reporting_unit":
                continue
            # Infer prefecture from unit name is hard; use source_area / block
            area = item.get("source_area") or ""
            prefecture = area if area in PREFECTURE_CODES else None
            if prefecture is None:
                block = str(item.get("block") or "")
                for pref in PREFECTURE_CODES:
                    if pref.replace("県", "").replace("府", "").replace("都", "") in block.replace("選挙区", ""):
                        if block.startswith(pref[:2]) or pref.startswith(block.replace("選挙区", "")[:2]):
                            prefecture = pref
                            break
                if prefecture is None and area.endswith("選挙区"):
                    prefecture = None
                # Per-prefecture PR files (older kaiji): label is prefecture
                if label in PREFECTURE_CODES:
                    prefecture = label
                elif area in PREFECTURE_CODES:
                    prefecture = area
            if prefecture is None and label in PREFECTURE_CODES:
                prefecture = label
            if prefecture is None:
                # block-only file: leave prefecture null; UI can still filter by municipality name
                prefecture = area if area else None
            rows.append({
                "election_kaiji": kaiji,
                "category": "比例代表",
                "contest": "pr",
                "prefecture": prefecture,
                "prefecture_code": PREFECTURE_CODES.get(prefecture) if prefecture else None,
                "district_number": None,
                "municipality": item.get("reporting_unit"),
                "pr_block": item.get("block"),
                "subject": item.get("party"),
                "candidate": None,
                "party": item.get("party"),
                "metric": "party_votes",
                "value": item.get("votes"),
                "unit": "votes",
                "grain": "municipality",
                "source_code": code,
                "source_file": item.get("source_file"),
            })
    return rows


def write_parquet(rows: list[dict], path: Path) -> None:
    out_dir = path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    ndjson = path.with_suffix(".ndjson")
    with ndjson.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    con = duckdb.connect()
    src = ndjson.as_posix().replace("'", "''")
    dst = path.as_posix().replace("'", "''")
    con.execute(f"""
        COPY (
          SELECT * FROM read_json_auto('{src}', format='newline_delimited', union_by_name=true)
        ) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    con.close()
    ndjson.unlink(missing_ok=True)


def main() -> int:
    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    summary = []
    for kaiji in range(45, 52):
        print(f"parsing kaiji {kaiji} ...", flush=True)
        smd_rows = parse_smd_kaiji(kaiji)
        pr_rows = parse_pr_kaiji(kaiji)
        rows = smd_rows + pr_rows
        summary.append({
            "kaiji": kaiji,
            "smd": len(smd_rows),
            "pr": len(pr_rows),
            "total": len(rows),
        })
        print(summary[-1], flush=True)
        all_rows.extend(rows)

    warehouse = ROOT / "data" / "warehouse" / "parquet" / "municipality_facts.parquet"
    web = ROOT / "web" / "data" / "municipality_facts.parquet"
    write_parquet(all_rows, warehouse)
    web.write_bytes(warehouse.read_bytes())

    # Keep legacy filename as alias for SMD-only consumers
    smd_only = [r for r in all_rows if r["category"] == "小選挙区"]
    legacy = ROOT / "data" / "warehouse" / "parquet" / "smd_municipality_votes.parquet"
    legacy_web = ROOT / "web" / "data" / "smd_municipality_votes.parquet"
    write_parquet(smd_only, legacy)
    legacy_web.write_bytes(legacy.read_bytes())

    (out_dir / "muni_all_summary.json").write_text(
        json.dumps({
            "total": len(all_rows),
            "by_kaiji": summary,
            "bytes": warehouse.stat().st_size,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print({"total": len(all_rows), "bytes": warehouse.stat().st_size})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
