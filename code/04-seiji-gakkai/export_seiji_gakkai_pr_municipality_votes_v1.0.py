# -*- coding: utf-8 -*-
"""
export_seiji_gakkai_pr_municipality_votes_v1.0.py
- 政治学会 SH-HD Bronze → 市区町村×比例政党得票の別 parquet（MIC に merge しない）
- source_code: seiji-gakkai-pr-muni-{kaiji:02d}
- 地名: city_raw/ward_raw 原文保持。表示は NFKC + 手動 override のみ

出力:
  data/warehouse/parquet/seiji_gakkai_pr_municipality_votes.parquet
  web/data/seiji_gakkai_pr_municipality_votes.parquet
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
SHHD = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "01-bronze"
    / "1996-2017"
    / "05-SH-HD"
    / "sh-hd-votes.jsonl"
)
OVERRIDES_JSON = Path(__file__).resolve().parent / "seiji_gakkai_municipality_name_overrides.json"
WAREHOUSE_OUT = REPO / "data" / "warehouse" / "parquet" / "seiji_gakkai_pr_municipality_votes.parquet"
WEB_OUT = REPO / "web" / "data" / "seiji_gakkai_pr_municipality_votes.parquet"
OUT_DIR = REPO / "output" / "04-seiji-gakkai"

PREF_OFFICIAL = {
    "北海道": "北海道",
    "青森": "青森県", "岩手": "岩手県", "宮城": "宮城県", "秋田": "秋田県",
    "山形": "山形県", "福島": "福島県", "茨城": "茨城県", "栃木": "栃木県",
    "群馬": "群馬県", "埼玉": "埼玉県", "千葉": "千葉県", "東京": "東京都",
    "神奈川": "神奈川県", "新潟": "新潟県", "富山": "富山県", "石川": "石川県",
    "福井": "福井県", "山梨": "山梨県", "長野": "長野県", "岐阜": "岐阜県",
    "静岡": "静岡県", "愛知": "愛知県", "三重": "三重県", "滋賀": "滋賀県",
    "京都": "京都府", "大阪": "大阪府", "兵庫": "兵庫県", "奈良": "奈良県",
    "和歌山": "和歌山県", "鳥取": "鳥取県", "島根": "島根県", "岡山": "岡山県",
    "広島": "広島県", "山口": "山口県", "徳島": "徳島県", "香川": "香川県",
    "愛媛": "愛媛県", "高知": "高知県", "福岡": "福岡県", "佐賀": "佐賀県",
    "長崎": "長崎県", "熊本": "熊本県", "大分": "大分県", "宮崎": "宮崎県",
    "鹿児島": "鹿児島県", "沖縄": "沖縄県",
}
PREF_CODE = {
    "北海道": "01", "青森県": "02", "岩手県": "03", "宮城県": "04", "秋田県": "05",
    "山形県": "06", "福島県": "07", "茨城県": "08", "栃木県": "09", "群馬県": "10",
    "埼玉県": "11", "千葉県": "12", "東京都": "13", "神奈川県": "14", "新潟県": "15",
    "富山県": "16", "石川県": "17", "福井県": "18", "山梨県": "19", "長野県": "20",
    "岐阜県": "21", "静岡県": "22", "愛知県": "23", "三重県": "24", "滋賀県": "25",
    "京都府": "26", "大阪府": "27", "兵庫県": "28", "奈良県": "29", "和歌山県": "30",
    "鳥取県": "31", "島根県": "32", "岡山県": "33", "広島県": "34", "山口県": "35",
    "徳島県": "36", "香川県": "37", "愛媛県": "38", "高知県": "39", "福岡県": "40",
    "佐賀県": "41", "長崎県": "42", "熊本県": "43", "大分県": "44", "宮崎県": "45",
    "鹿児島県": "46", "沖縄県": "47",
}
BLOCK_NORM = {
    "北海道": "北海道", "東北": "東北", "北関東": "北関東", "南関東": "南関東",
    "東京": "東京都", "東京都": "東京都", "北陸信越": "北陸信越", "東海": "東海",
    "近畿": "近畿", "中国": "中国", "四国": "四国", "九州": "九州",
}


def nfkc(value: str | None) -> str:
    return unicodedata.normalize("NFKC", str(value or "").strip())


def prefecture_from_district_name(district_name: str) -> tuple[str | None, str | None]:
    s = nfkc(district_name)
    s = re.sub(r"\d+\s*区\s*$", "", s)
    for short, official in sorted(PREF_OFFICIAL.items(), key=lambda x: -len(x[0])):
        if s.startswith(short) or s.startswith(official):
            return official, PREF_CODE[official]
    return None, None


def load_name_overrides() -> dict[tuple[str, str], dict]:
    if not OVERRIDES_JSON.is_file():
        return {}
    data = json.loads(OVERRIDES_JSON.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], dict] = {}
    for row in data.get("overrides") or []:
        field = (row.get("field") or "").strip()
        match = nfkc(row.get("match"))
        replace = nfkc(row.get("replace"))
        if field not in {"city", "ward"} or not match or not replace:
            continue
        out[(field, match)] = row
    return out


def apply_name(field: str, raw: str, overrides: dict[tuple[str, str], dict]) -> tuple[str, list[str]]:
    flags: list[str] = []
    value = nfkc(raw)
    if value != (raw or "").strip():
        flags.append("nfkc")
    key = (field, value)
    if key in overrides:
        value = nfkc(overrides[key].get("replace"))
        flags.append("manual_override")
    return value, flags


def compose_municipality(city: str, ward: str) -> str:
    if not city:
        return ward
    if not ward or ward == city:
        return city
    if ward.startswith(city):
        return ward
    return f"{city}{ward}"


def flatten(path: Path, overrides: dict) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            th = int(rec["election_th"])
            year = int(rec["election_year"])
            dist_name = nfkc(rec.get("district_name"))
            pref, pref_code = prefecture_from_district_name(dist_name)
            block = BLOCK_NORM.get(nfkc(rec.get("block")), nfkc(rec.get("block")))
            parties = rec.get("parties") or []
            source_code = f"seiji-gakkai-pr-muni-{th:02d}"
            for muni in rec.get("municipalities") or []:
                city_raw = str(muni.get("city") or "")
                ward_raw = str(muni.get("ward") or "")
                city, city_flags = apply_name("city", city_raw, overrides)
                ward, ward_flags = apply_name("ward", ward_raw, overrides)
                municipality = compose_municipality(city, ward)
                flags = city_flags + ward_flags
                base = {
                    "election_kaiji": th,
                    "election_year": year,
                    "election_id": f"shugiin-{th}",
                    "contest": "pr",
                    "category": "比例代表",
                    "prefecture": pref,
                    "prefecture_code": pref_code,
                    "district_number": int(rec["district_num"]),
                    "district_name": dist_name,
                    "pr_block": block or None,
                    "city_raw": city_raw,
                    "ward_raw": ward_raw,
                    "city": city,
                    "ward": ward,
                    "municipality": municipality,
                    "name_flags": "|".join(flags) if flags else None,
                    "grain": "municipality",
                    "source_code": source_code,
                    "dataset": "政治学会・比例市区町村（SH-HD）",
                    "source_file": rec.get("source_file"),
                    "source": "seiji-gakkai",
                }
                for metric, value, unit, subject in (
                    ("eligible_voters", muni.get("eligible_voters"), "people", "有権者数"),
                    ("voters", muni.get("total_votes"), "people", "投票者数"),
                ):
                    if value is None:
                        continue
                    rows.append(
                        {
                            **base,
                            "party": None,
                            "party_position": None,
                            "subject": subject,
                            "metric": metric,
                            "value": int(value),
                            "unit": unit,
                        }
                    )
                votes = muni.get("party_votes") or []
                for i, party in enumerate(parties):
                    vote = votes[i] if i < len(votes) else None
                    if vote is None:
                        continue
                    pname = nfkc(party.get("name"))
                    rows.append(
                        {
                            **base,
                            "party": pname or None,
                            "party_position": party.get("position"),
                            "subject": pname,
                            "metric": "party_votes",
                            "value": int(vote),
                            "unit": "votes",
                        }
                    )
    return rows


def main() -> None:
    if not SHHD.is_file():
        raise SystemExit(f"missing SH-HD: {SHHD}")
    overrides = load_name_overrides()
    rows = flatten(SHHD, overrides)
    if not rows:
        raise SystemExit("no rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_seiji_gakkai_pr_municipality_votes.jsonl"
    with staging.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    WAREHOUSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_json_auto('{staging.as_posix()}')
          ORDER BY election_kaiji, prefecture_code NULLS LAST, district_number,
                   municipality, metric, party_position NULLS LAST
        ) TO '{WAREHOUSE_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )
    WEB_OUT.write_bytes(WAREHOUSE_OUT.read_bytes())

    by_th = Counter(r["election_kaiji"] for r in rows)
    by_metric = Counter(r["metric"] for r in rows)
    report = OUT_DIR / f"{stamp}_pr_muni_export_report.txt"
    lines = [
        "# 政治学会 SH-HD → seiji_gakkai_pr_municipality_votes",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"rows={len(rows)}",
        f"warehouse={WAREHOUSE_OUT}",
        f"web={WEB_OUT}",
        "",
        "## by election_kaiji",
        *[f"- {k}: {v}" for k, v in sorted(by_th.items())],
        "",
        "## by metric",
        *[f"- {k}: {v}" for k, v in sorted(by_metric.items())],
        "",
        "OK: SH-HD municipality PR export complete",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
