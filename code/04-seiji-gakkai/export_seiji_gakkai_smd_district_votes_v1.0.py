# -*- coding: utf-8 -*-
"""
export_seiji_gakkai_smd_district_votes_v1.0.py
- 政治学会 SH-D Silver → 選挙区×候補の別 parquet（MIC facts に merge しない）
- source_code: seiji-gakkai-smd-{kaiji:02d}
- 出力:
  data/warehouse/parquet/seiji_gakkai_smd_district_votes.parquet
  web/data/seiji_gakkai_smd_district_votes.parquet
  output/04-seiji-gakkai/*_export_report.txt
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
SILVER = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "02-silver"
    / "1996-2017"
    / "03-SH-D"
    / "sh-d-votes.jsonl"
)
WAREHOUSE_OUT = REPO / "data" / "warehouse" / "parquet" / "seiji_gakkai_smd_district_votes.parquet"
WEB_OUT = REPO / "web" / "data" / "seiji_gakkai_smd_district_votes.parquet"
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


def nfkc(value: str | None) -> str:
    return unicodedata.normalize("NFKC", str(value or "").strip())


def prefecture_from_district_name(district_name: str) -> tuple[str | None, str | None]:
    s = nfkc(district_name)
    s = re.sub(r"\d+\s*区\s*$", "", s)
    for short, official in sorted(PREF_OFFICIAL.items(), key=lambda x: -len(x[0])):
        if s.startswith(short) or s.startswith(official):
            return official, PREF_CODE[official]
    return None, None


def flatten_silver(path: Path) -> list[dict]:
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
            source_code = f"seiji-gakkai-smd-{th:02d}"
            for cand in rec.get("candidates") or []:
                rows.append(
                    {
                        "election_kaiji": th,
                        "election_year": year,
                        "election_id": f"shugiin-{th}",
                        "seiji_election_id": rec.get("election_id"),
                        "contest": "smd",
                        "prefecture": pref,
                        "prefecture_code": pref_code,
                        "district_number": int(rec["district_num"]),
                        "district_name": dist_name,
                        "district_code": nfkc(rec.get("district_code")),
                        "pr_block": nfkc(rec.get("block")),
                        "list_position": cand.get("position"),
                        "candidate": nfkc(cand.get("name_kana")),
                        "candidate_raw": cand.get("name_kana"),
                        "party": nfkc(cand.get("party")) or None,
                        "dual_candidacy": bool(cand.get("is_proportional_duplicate")),
                        "placement_num": cand.get("placement_num"),
                        "metric": "candidate_votes",
                        "value": cand.get("district_total_votes"),
                        "unit": "votes",
                        "district_eligible_voters": rec.get("eligible_voters"),
                        "district_total_votes": rec.get("total_votes"),
                        "district_valid_votes": rec.get("valid_votes"),
                        "source_code": source_code,
                        "dataset": "政治学会・小選挙区投票数（SH-D）",
                        "source_file": rec.get("source_file"),
                        "source": "seiji-gakkai",
                    }
                )
    return rows


def main() -> None:
    if not SILVER.is_file():
        raise SystemExit(f"missing silver: {SILVER}")

    rows = flatten_silver(SILVER)
    if not rows:
        raise SystemExit("no rows exported")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_seiji_gakkai_smd_district_votes.jsonl"
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
          ORDER BY election_kaiji, prefecture_code NULLS LAST, district_number, list_position
        ) TO '{WAREHOUSE_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )
    WEB_OUT.write_bytes(WAREHOUSE_OUT.read_bytes())

    by_th = Counter(r["election_kaiji"] for r in rows)
    missing_pref = sum(1 for r in rows if not r["prefecture"])
    null_votes = sum(1 for r in rows if r["value"] is None)
    source_codes = sorted({r["source_code"] for r in rows})

    # MIC overlap check: do not touch facts; only compare district counts
    facts = REPO / "web" / "data" / "facts.parquet"
    mic_lines: list[str] = []
    if facts.is_file():
        mic = con.execute(
            f"""
            SELECT election_kaiji,
                   count(DISTINCT (prefecture, district_number)) AS districts
            FROM read_parquet('{facts.as_posix()}')
            WHERE election_id LIKE 'shugiin-%'
              AND contest = 'smd' AND metric = 'candidate_votes'
              AND election_kaiji BETWEEN 44 AND 48
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        sg = con.execute(
            f"""
            SELECT election_kaiji,
                   count(DISTINCT (prefecture, district_number)) AS districts,
                   count(*) AS candidate_rows
            FROM read_parquet('{WAREHOUSE_OUT.as_posix()}')
            WHERE election_kaiji BETWEEN 44 AND 48
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        sg_map = {int(a): (int(b), int(c)) for a, b, c in sg}
        mic_lines.append("| th | seiji districts | seiji candidates | MIC districts |")
        mic_lines.append("|---:|---:|---:|---:|")
        for th, md in mic:
            sd, sc = sg_map.get(int(th), (0, 0))
            mic_lines.append(f"| {int(th)} | {sd} | {sc} | {int(md)} |")

    report_lines = [
        "# 政治学会 SH-D → seiji_gakkai_smd_district_votes エクスポート",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"silver={SILVER}",
        f"warehouse_out={WAREHOUSE_OUT}",
        f"web_out={WEB_OUT}",
        f"rows={len(rows)}",
        f"missing_prefecture={missing_pref}",
        f"null_votes={null_votes}",
        f"source_codes={source_codes}",
        "",
        "## rows by election_kaiji",
    ]
    for th in sorted(by_th):
        report_lines.append(f"- {th}: {by_th[th]}")
    if mic_lines:
        report_lines += ["", "## MIC district coverage (44–48, compare only)"] + mic_lines
    report_lines += [
        "",
        "## policy",
        "- MIC facts.parquet は未変更",
        "- UI 既定検索には未接続（opt-in データ配置のみ）",
        "- 中選挙区 historical は含まない",
    ]
    if missing_pref or null_votes:
        report_lines.append("WARN: prefecture or votes gaps remain")
    else:
        report_lines.append("OK: export complete")

    text = "\n".join(report_lines) + "\n"
    report = OUT_DIR / f"{stamp}_seiji_gakkai_smd_export_report.txt"
    latest = OUT_DIR / "seiji_gakkai_smd_export_report.txt"
    report.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {WAREHOUSE_OUT}")
    print(f"wrote {WEB_OUT}")


if __name__ == "__main__":
    main()
