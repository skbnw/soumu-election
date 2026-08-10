# -*- coding: utf-8 -*-
"""
export_seiji_gakkai_smd_municipality_votes_v1.0.py
- v1.0.2: city/ward がともに「〜市」で異なるとき連結しない（士別市土別市など OCR・異体字）
- v1.0.1: 開票区表記を「市（N区）」に統一（市-N / 市N区）。city_raw/ward_raw は原文保持
- 政治学会 SH-D Silver の municipalities を市区町村×候補へ flatten
- MIC municipality_facts には merge しない（別 parquet）
- 自治体名: 原本を city_raw/ward_raw に保持。表示用は NFKC + 手動 override + 開票区接尾正規化
  （勝手な地名訂正はしない。漢字間スペース等の明確ノイズのみ）
- source_code: seiji-gakkai-smd-muni-{kaiji:02d}

出力:
  data/warehouse/parquet/seiji_gakkai_smd_municipality_votes.parquet
  web/data/seiji_gakkai_smd_municipality_votes.parquet
  output/04-seiji-gakkai/*_muni_export_report.txt
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
SILVER = (
    REPO
    / "references"
    / "seiji-gakkai"
    / "02-silver"
    / "1996-2017"
    / "03-SH-D"
    / "sh-d-votes.jsonl"
)
OVERRIDES_JSON = Path(__file__).resolve().parent / "seiji_gakkai_municipality_name_overrides.json"
WAREHOUSE_OUT = REPO / "data" / "warehouse" / "parquet" / "seiji_gakkai_smd_municipality_votes.parquet"
WEB_OUT = REPO / "web" / "data" / "seiji_gakkai_smd_municipality_votes.parquet"
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

CJK_SPACE_RE = re.compile(r"(?<=[\u4e00-\u9fff々〆ヵヶ])[\s\u3000]+(?=[\u4e00-\u9fff々〆ヵヶ])")
AGG_EXACT = {"計", "合計", "確定", "不在者投票", "在外", "在外投票"}
SPLIT_WARD_RE = re.compile(r"^(.+)-(\d+)$")
CITY_N_KU_RE = re.compile(r"^(.+?[市町村])(\d+)区$")


def nfkc(value: str | None) -> str:
    return unicodedata.normalize("NFKC", str(value or "").strip())


def normalize_municipality_label(name: str) -> str:
    """開票区接尾の表記ゆれのみ揃える（行政名そのものは変えない）。"""
    s = nfkc(name)
    m = SPLIT_WARD_RE.match(s)
    if m:
        return f"{m.group(1)}（{m.group(2)}区）"
    m = CITY_N_KU_RE.match(s)
    if m:
        return f"{m.group(1)}（{m.group(2)}区）"
    return s


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if ca == cb else 1)))
        prev = cur
    return prev[-1]


def compose_municipality(city: str, ward: str) -> tuple[str, list[str]]:
    """
    Returns (municipality_label, compose_flags).
    - 郡+町村 / 市+区 は従来どおり連結
    - city/ward がともに「〜市」で異なる場合は連結しない（OCR・異体字の二重名を防ぐ）
    """
    flags: list[str] = []
    city = nfkc(city)
    ward = nfkc(ward)
    if city and ward:
        if ward.startswith(city) or ward == city:
            return normalize_municipality_label(ward if ward.startswith(city) else city), flags
        if city.endswith("市") and ward.endswith("市") and city != ward:
            flags.append("skip_shi_shi_concat")
            if edit_distance(city, ward) <= 1:
                flags.append("near_duplicate_ward")
            else:
                flags.append("conflicting_shi_ward")
            return normalize_municipality_label(city), flags
        return normalize_municipality_label(f"{city}{ward}"), flags
    return normalize_municipality_label(city or ward or ""), flags


def prefecture_from_district_name(district_name: str) -> tuple[str | None, str | None]:
    s = nfkc(district_name)
    s = re.sub(r"\d+\s*区\s*$", "", s)
    for short, official in sorted(PREF_OFFICIAL.items(), key=lambda x: -len(x[0])):
        if s.startswith(short) or s.startswith(official):
            return official, PREF_CODE[official]
    return None, None


def load_name_overrides() -> dict[tuple[str, str], dict]:
    """(field, match_nfkc) -> override row"""
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


def apply_name(
    field: str,
    raw: str,
    overrides: dict[tuple[str, str], dict],
) -> tuple[str, list[str], str | None]:
    """
    Returns (value_for_display, flags, note).
    - raw is preserved by caller
    - only NFKC + explicit override; no silent gazetteer rewrite
    """
    flags: list[str] = []
    note = None
    value = nfkc(raw)
    if value != (raw or "").strip():
        flags.append("nfkc")
    key = (field, value)
    if key in overrides:
        ov = overrides[key]
        value = nfkc(ov.get("replace"))
        flags.append("manual_override")
        note = (ov.get("note") or "").strip() or None
    elif CJK_SPACE_RE.search(value):
        flags.append("cjk_internal_space")
    if value in AGG_EXACT:
        flags.append("aggregate_label")
    return value, flags, note


def flatten(path: Path, overrides: dict[tuple[str, str], dict]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    name_events: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            th = int(rec["election_th"])
            year = int(rec["election_year"])
            dist_name = nfkc(rec.get("district_name"))
            pref, pref_code = prefecture_from_district_name(dist_name)
            source_code = f"seiji-gakkai-smd-muni-{th:02d}"
            candidates = rec.get("candidates") or []

            for muni in rec.get("municipalities") or []:
                city_raw = str(muni.get("city") or "")
                ward_raw = str(muni.get("ward") or "")
                city, city_flags, city_note = apply_name("city", city_raw, overrides)
                ward, ward_flags, ward_note = apply_name("ward", ward_raw, overrides)
                municipality, compose_flags = compose_municipality(city, ward)
                flags = sorted(set(city_flags + ward_flags + compose_flags))
                if flags:
                    name_events.append(
                        {
                            "election_kaiji": th,
                            "district_name": dist_name,
                            "city_raw": city_raw,
                            "ward_raw": ward_raw,
                            "city": city,
                            "ward": ward,
                            "municipality": municipality,
                            "flags": "|".join(flags),
                            "note": city_note or ward_note,
                        }
                    )

                base = {
                    "election_kaiji": th,
                    "election_year": year,
                    "election_id": f"shugiin-{th}",
                    "seiji_election_id": rec.get("election_id"),
                    "contest": "smd",
                    "category": "小選挙区",
                    "prefecture": pref,
                    "prefecture_code": pref_code,
                    "district_number": int(rec["district_num"]),
                    "district_name": dist_name,
                    "pr_block": nfkc(rec.get("block")),
                    "city_raw": city_raw,
                    "ward_raw": ward_raw,
                    "city": city,
                    "ward": ward,
                    "municipality": municipality,
                    "name_flags": "|".join(flags) if flags else None,
                    "grain": "municipality",
                    "source_code": source_code,
                    "dataset": "政治学会・小選挙区投票数（SH-D）市区町村",
                    "source_file": rec.get("source_file"),
                    "source": "seiji-gakkai",
                }

                # 自治体単位の有権者・投票
                for metric, value, unit in (
                    ("eligible_voters", muni.get("eligible_voters"), "people"),
                    ("voters", muni.get("total_votes"), "people"),
                ):
                    rows.append(
                        {
                            **base,
                            "list_position": None,
                            "candidate": None,
                            "candidate_raw": None,
                            "party": None,
                            "dual_candidacy": None,
                            "subject": "有権者数" if metric == "eligible_voters" else "投票者数",
                            "metric": metric,
                            "value": value,
                            "unit": unit,
                        }
                    )

                votes = muni.get("candidate_votes") or []
                for i, cand in enumerate(candidates):
                    vote = votes[i] if i < len(votes) else None
                    rows.append(
                        {
                            **base,
                            "list_position": cand.get("position"),
                            "candidate": nfkc(cand.get("name_kana")),
                            "candidate_raw": cand.get("name_kana"),
                            "party": nfkc(cand.get("party")) or None,
                            "dual_candidacy": bool(cand.get("is_proportional_duplicate")),
                            "subject": nfkc(cand.get("name_kana")),
                            "metric": "candidate_votes",
                            "value": vote,
                            "unit": "votes",
                        }
                    )
    return rows, name_events


def main() -> None:
    if not SILVER.is_file():
        raise SystemExit(f"missing silver: {SILVER}")

    overrides = load_name_overrides()
    rows, name_events = flatten(SILVER, overrides)
    if not rows:
        raise SystemExit("no rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_seiji_gakkai_smd_municipality_votes.jsonl"
    with staging.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    events_path = OUT_DIR / f"{stamp}_municipality_name_flags.jsonl"
    with events_path.open("w", encoding="utf-8", newline="\n") as f:
        for ev in name_events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    (OUT_DIR / "municipality_name_flags.jsonl").write_text(
        events_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    WAREHOUSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_json_auto('{staging.as_posix()}')
          ORDER BY election_kaiji, prefecture_code NULLS LAST, district_number,
                   municipality, metric, list_position NULLS LAST
        ) TO '{WAREHOUSE_OUT.as_posix()}' (FORMAT PARQUET)
        """
    )
    WEB_OUT.write_bytes(WAREHOUSE_OUT.read_bytes())

    by_th = Counter(r["election_kaiji"] for r in rows)
    by_metric = Counter(r["metric"] for r in rows)
    flag_counts = Counter()
    for ev in name_events:
        for flag in (ev.get("flags") or "").split("|"):
            if flag:
                flag_counts[flag] += 1
    override_n = sum(1 for ev in name_events if "manual_override" in (ev.get("flags") or ""))
    space_left = sum(1 for ev in name_events if "cjk_internal_space" in (ev.get("flags") or ""))
    missing_pref = sum(1 for r in rows if not r.get("prefecture"))

    # vote length sanity vs candidates already handled at flatten; check null candidate votes share
    cand_rows = [r for r in rows if r["metric"] == "candidate_votes"]
    null_cand = sum(1 for r in cand_rows if r["value"] is None)

    report = [
        "# 政治学会 SH-D → seiji_gakkai_smd_municipality_votes エクスポート",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"silver={SILVER}",
        f"overrides={OVERRIDES_JSON}",
        f"warehouse_out={WAREHOUSE_OUT}",
        f"web_out={WEB_OUT}",
        f"rows={len(rows)}",
        f"candidate_vote_rows={len(cand_rows)} null_candidate_votes={null_cand}",
        f"missing_prefecture={missing_pref}",
        f"name_flag_events={len(name_events)} manual_override_events={override_n} "
        f"unfixed_cjk_space_events={space_left}",
        f"flag_counts={dict(flag_counts)}",
        "",
        "## rows by election_kaiji",
    ]
    for th in sorted(by_th):
        report.append(f"- {th}: {by_th[th]}")
    report += ["", "## rows by metric"]
    for metric, n in sorted(by_metric.items()):
        report.append(f"- {metric}: {n}")

    report += ["", "## name policy"]
    report.append("- city_raw / ward_raw = Silver 原文（改変なし）")
    report.append("- city / ward / municipality = NFKC + 手動 override のみ")
    report.append("- 漢字間スペースは自動では潰さず cjk_internal_space フラグ。既知例のみ override")
    report.append("- MIC municipality_facts へは merge しない")
    report.append("- UI 未接続")

    if name_events:
        report += ["", "## name flag examples (max 20)"]
        for ev in name_events[:20]:
            report.append(
                f"- th={ev['election_kaiji']} {ev['district_name']}: "
                f"raw=({ev['city_raw']!r},{ev['ward_raw']!r}) -> "
                f"({ev['city']!r},{ev['ward']!r}) flags={ev['flags']}"
            )

    if missing_pref or null_cand or space_left:
        report.append("")
        report.append("WARN: review name flags / null votes")
    else:
        report.append("")
        report.append("OK: municipality export complete")

    text = "\n".join(report) + "\n"
    report_path = OUT_DIR / f"{stamp}_seiji_gakkai_smd_muni_export_report.txt"
    latest = OUT_DIR / "seiji_gakkai_smd_muni_export_report.txt"
    report_path.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {WAREHOUSE_OUT}")
    print(f"wrote {WEB_OUT}")
    print(f"wrote {events_path}")


if __name__ == "__main__":
    main()
