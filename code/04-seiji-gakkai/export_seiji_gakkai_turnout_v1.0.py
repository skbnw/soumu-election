# -*- coding: utf-8 -*-
"""
export_seiji_gakkai_turnout_v1.0.py
- v1.1: grain に小選挙区・市町村を追加（都道府県／ブロック／全国は維持）
- v1.0: 政治学会 SH-D（小選挙区）＋ SH-B（比例ブロック）から投票・有権者を別 parquet 化
- MIC facts には merge しない
- source_code:
  - smd: seiji-gakkai-turnout-smd-{kaiji:02d}
  - pr:  seiji-gakkai-turnout-pr-{kaiji:02d}

粒 (grain):
- smd: prefecture / district / municipality
- pr:  block / national
  ※ 市町村粒の候補得票は seiji_gakkai_smd_municipality_votes。
    ここは有権者・投票者メトリクス用。

出力:
  data/warehouse/parquet/seiji_gakkai_turnout.parquet
  web/data/seiji_gakkai_turnout.parquet
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
SHD = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "02-silver"
    / "1996-2017"
    / "03-SH-D"
    / "sh-d-votes.jsonl"
)
SHB = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "01-bronze"
    / "1996-2017"
    / "04-SH-B"
    / "shb-blocks.jsonl"
)
WAREHOUSE_OUT = REPO / "data" / "warehouse" / "parquet" / "seiji_gakkai_turnout.parquet"
WEB_OUT = REPO / "web" / "data" / "seiji_gakkai_turnout.parquet"
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
    "北海道": "北海道",
    "東北": "東北",
    "北関東": "北関東",
    "南関東": "南関東",
    "東京": "東京都",
    "東京都": "東京都",
    "北陸信越": "北陸信越",
    "東海": "東海",
    "近畿": "近畿",
    "中国": "中国",
    "四国": "四国",
    "九州": "九州",
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


def compose_municipality(city: str, ward: str) -> str:
    city = nfkc(city)
    ward = nfkc(ward)
    if not city:
        return ward
    if not ward or ward == city:
        return city
    if ward.startswith(city):
        return ward
    return f"{city}{ward}"


def metric_rows(
    *,
    th: int,
    year: int,
    contest: str,
    prefecture: str | None,
    prefecture_code: str | None,
    pr_block: str | None,
    grain: str,
    eligible: int | None,
    voters: int | None,
    source_code: str,
    source_file: str | None,
    district_number: int | None = None,
    district_name: str | None = None,
    municipality: str | None = None,
) -> list[dict]:
    out: list[dict] = []
    base = {
        "election_kaiji": th,
        "election_year": year,
        "election_id": f"shugiin-{th}",
        "contest": contest,
        "prefecture": prefecture,
        "prefecture_code": prefecture_code,
        "district_number": district_number,
        "district_name": district_name,
        "municipality": municipality,
        "pr_block": pr_block,
        "grain": grain,
        "gender": "total",
        "scope": "all",
        "source_code": source_code,
        "dataset": "政治学会・投票有権者（SH-D/SH-B）",
        "source_file": source_file,
        "source": "seiji-gakkai",
    }
    if eligible is not None:
        out.append({**base, "metric": "eligible_voters", "value": int(eligible), "unit": "people"})
    if voters is not None:
        out.append({**base, "metric": "voters", "value": int(voters), "unit": "people"})
    if eligible and voters is not None and eligible > 0:
        rate = round(100.0 * float(voters) / float(eligible), 3)
        out.append({**base, "metric": "turnout_rate", "value": rate, "unit": "percent"})
    return out


def build_smd_pref_rows() -> list[dict]:
    agg: dict[tuple[int, int, str], dict] = {}
    with SHD.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            th = int(rec["election_th"])
            year = int(rec["election_year"])
            pref, pref_code = prefecture_from_district_name(nfkc(rec.get("district_name")))
            if not pref:
                continue
            key = (th, year, pref)
            bucket = agg.setdefault(
                key,
                {
                    "prefecture_code": pref_code,
                    "eligible": 0,
                    "voters": 0,
                    "source_file": rec.get("source_file"),
                    "n": 0,
                },
            )
            if rec.get("eligible_voters") is not None:
                bucket["eligible"] += int(rec["eligible_voters"])
            if rec.get("total_votes") is not None:
                bucket["voters"] += int(rec["total_votes"])
            bucket["n"] += 1

    rows: list[dict] = []
    for (th, year, pref), b in sorted(agg.items()):
        rows.extend(
            metric_rows(
                th=th,
                year=year,
                contest="smd",
                prefecture=pref,
                prefecture_code=b["prefecture_code"],
                pr_block=None,
                grain="prefecture",
                eligible=b["eligible"] or None,
                voters=b["voters"] or None,
                source_code=f"seiji-gakkai-turnout-smd-{th:02d}",
                source_file=b["source_file"],
            )
        )
    return rows


def build_smd_district_rows() -> list[dict]:
    rows: list[dict] = []
    with SHD.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            th = int(rec["election_th"])
            year = int(rec["election_year"])
            dist_name = nfkc(rec.get("district_name"))
            pref, pref_code = prefecture_from_district_name(dist_name)
            eligible = rec.get("eligible_voters")
            voters = rec.get("total_votes")
            rows.extend(
                metric_rows(
                    th=th,
                    year=year,
                    contest="smd",
                    prefecture=pref,
                    prefecture_code=pref_code,
                    pr_block=None,
                    grain="district",
                    eligible=int(eligible) if eligible is not None else None,
                    voters=int(voters) if voters is not None else None,
                    source_code=f"seiji-gakkai-turnout-smd-{th:02d}",
                    source_file=rec.get("source_file"),
                    district_number=int(rec["district_num"]),
                    district_name=dist_name,
                )
            )
    return rows


def build_smd_municipality_rows() -> list[dict]:
    rows: list[dict] = []
    with SHD.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            th = int(rec["election_th"])
            year = int(rec["election_year"])
            dist_name = nfkc(rec.get("district_name"))
            pref, pref_code = prefecture_from_district_name(dist_name)
            for muni in rec.get("municipalities") or []:
                municipality = compose_municipality(muni.get("city") or "", muni.get("ward") or "")
                if not municipality:
                    continue
                eligible = muni.get("eligible_voters")
                voters = muni.get("total_votes")
                rows.extend(
                    metric_rows(
                        th=th,
                        year=year,
                        contest="smd",
                        prefecture=pref,
                        prefecture_code=pref_code,
                        pr_block=None,
                        grain="municipality",
                        eligible=int(eligible) if eligible is not None else None,
                        voters=int(voters) if voters is not None else None,
                        source_code=f"seiji-gakkai-turnout-smd-{th:02d}",
                        source_file=rec.get("source_file"),
                        district_number=int(rec["district_num"]),
                        district_name=dist_name,
                        municipality=municipality,
                    )
                )
    return rows


def build_pr_block_rows() -> list[dict]:
    rows: list[dict] = []
    national: dict[tuple[int, int], dict] = defaultdict(lambda: {"eligible": 0, "voters": 0})
    with SHB.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            th = int(rec["election_th"])
            year = int(rec["election_year"])
            block = BLOCK_NORM.get(nfkc(rec.get("block_name")), nfkc(rec.get("block_name")))
            eligible = rec.get("eligible_voters")
            voters = rec.get("total_votes")
            rows.extend(
                metric_rows(
                    th=th,
                    year=year,
                    contest="pr",
                    prefecture=None,
                    prefecture_code=None,
                    pr_block=block or None,
                    grain="block",
                    eligible=int(eligible) if eligible is not None else None,
                    voters=int(voters) if voters is not None else None,
                    source_code=f"seiji-gakkai-turnout-pr-{th:02d}",
                    source_file=rec.get("source_file"),
                )
            )
            if eligible is not None:
                national[(th, year)]["eligible"] += int(eligible)
            if voters is not None:
                national[(th, year)]["voters"] += int(voters)

    for (th, year), b in sorted(national.items()):
        rows.extend(
            metric_rows(
                th=th,
                year=year,
                contest="pr",
                prefecture=None,
                prefecture_code=None,
                pr_block="全国",
                grain="national",
                eligible=b["eligible"] or None,
                voters=b["voters"] or None,
                source_code=f"seiji-gakkai-turnout-pr-{th:02d}",
                source_file=None,
            )
        )
    return rows


def main() -> None:
    if not SHD.is_file():
        raise SystemExit(f"missing SH-D silver: {SHD}")
    if not SHB.is_file():
        raise SystemExit(f"missing SH-B bronze: {SHB}")

    rows = (
        build_smd_pref_rows()
        + build_smd_district_rows()
        + build_smd_municipality_rows()
        + build_pr_block_rows()
    )
    if not rows:
        raise SystemExit("no turnout rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_seiji_gakkai_turnout.jsonl"
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
          ORDER BY election_kaiji, contest, grain, prefecture_code NULLS LAST, pr_block NULLS LAST, metric
        ) TO '{WAREHOUSE_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )
    WEB_OUT.write_bytes(WAREHOUSE_OUT.read_bytes())

    by = Counter((r["contest"], r["metric"], r["grain"]) for r in rows)
    report = [
        "# 政治学会 → seiji_gakkai_turnout エクスポート",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"rows={len(rows)}",
        f"warehouse_out={WAREHOUSE_OUT}",
        f"web_out={WEB_OUT}",
        "",
        "## counts",
    ]
    for key, n in sorted(by.items()):
        report.append(f"- {key}: {n}")
    report.append("")
    report.append("- MIC facts へは merge しない")
    report_path = OUT_DIR / f"{stamp}_turnout_export_report.txt"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    (OUT_DIR / "turnout_export_report.txt").write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {len(rows)} rows -> {WEB_OUT}")
    print(f"report -> {report_path}")


if __name__ == "__main__":
    main()
