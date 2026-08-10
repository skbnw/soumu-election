# -*- coding: utf-8 -*-
"""
build_seiji_kana_to_kanji_v1.0.py
- 政治学会かな名 × 読売漢字リスト → 表示用かな→漢字マップ
- 数値は触らない。原本 CSV は改変しない
- 突合優先: (th, prefecture, district_number, vote) → 必要なら政党略称で補助

出力:
  web/data/seiji_candidate_name_map.parquet
  data/warehouse/parquet/seiji_candidate_name_map.parquet
  output/03-person-aliases/*_kanji_match_report.txt
  output/03-person-aliases/*_seiji_candidate_name_map.jsonl
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
KANJI_CSV = REPO / "references" / "yomi-shosenkyo" / "yomi-candidate-kanji1996-2026.csv"
SEIJI_PQ = REPO / "web" / "data" / "seiji_gakkai_smd_district_votes.parquet"
OUT_DIR = REPO / "output" / "03-person-aliases"
WEB_OUT = REPO / "web" / "data" / "seiji_candidate_name_map.parquet"
WAREHOUSE_OUT = REPO / "data" / "warehouse" / "parquet" / "seiji_candidate_name_map.parquet"

IVS_RE = re.compile(r"[\uFE00-\uFE0F\U000E0100-\U000E01EF]")
SPACE_RE = re.compile(r"[\s\u3000]+")
DIST_RE = re.compile(
    r"^(北海道|東京都|(?:京都|大阪)府|.+?県)?\s*([０-９0-9]+)\s*区$"
)

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

# 読売略称 → 政治学会側に出やすい表記の候補
PARTY_ALIASES = {
    "自": {"自民", "自由民主党", "自"},
    "自民": {"自民", "自由民主党", "自"},
    "民": {"民主", "民主党", "民"},
    "民主": {"民主", "民主党", "民"},
    "社": {"社民", "社会民主", "社"},
    "社民": {"社民", "社会民主", "社"},
    "共": {"共産", "日本共産党", "共"},
    "共産": {"共産", "日本共産党", "共"},
    "公": {"公明", "公明党", "公"},
    "公明": {"公明", "公明党", "公"},
    "維": {"維新", "日本維新の会", "維新の党", "みんな", "維"},
    "維新": {"維新", "日本維新の会", "維新の党", "維"},
    "み": {"みんな", "みんなの党", "み"},
    "みんな": {"みんな", "みんなの党", "み"},
    "無": {"無所属", "無"},
    "無所属": {"無所属", "無"},
    "新": {"新進", "新進党", "新"},
    "新進": {"新進", "新進党", "新"},
    "希": {"希望", "希望の党", "希"},
    "希望": {"希望", "希望の党", "希"},
    "立": {"立憲", "立憲民主", "立憲民主党", "立"},
    "立憲": {"立憲", "立憲民主", "立憲民主党", "立"},
    "国": {"国民", "国民民主", "国民民主党", "国"},
    "国民": {"国民", "国民民主", "国民民主党", "国"},
    "改": {"改革", "改革クラブ", "改"},
    "生": {"生活", "生活の党", "生"},
    "次": {"次世代", "次"},
    "輝": {"輝", "日本を元気に", "輝"},
}


def nfkc(value: str | None) -> str:
    return unicodedata.normalize("NFKC", str(value or "").strip())


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    s = IVS_RE.sub("", str(value))
    s = unicodedata.normalize("NFKC", s)
    s = SPACE_RE.sub("", s)
    return s


def kana_compact(value: str | None) -> str:
    s = normalize_name(value)
    # カタカナ→ひらがな
    out = []
    for ch in s:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            out.append(chr(code - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def parse_district_kanji(text: str) -> tuple[str | None, int | None]:
    s = nfkc(text)
    m = DIST_RE.match(s)
    if not m:
        # 先頭都道府県を推定
        pref = None
        rest = s
        for short, official in sorted(PREF_OFFICIAL.items(), key=lambda x: -len(x[0])):
            if s.startswith(short) or s.startswith(official):
                pref = official
                rest = s[len(short) :] if s.startswith(short) else s[len(official) :]
                break
        m2 = re.search(r"([0-9]+)\s*区", rest)
        if pref and m2:
            return pref, int(m2.group(1))
        return None, None
    pref_raw = m.group(1) or ""
    dist = int(m.group(2))
    pref = None
    for short, official in sorted(PREF_OFFICIAL.items(), key=lambda x: -len(x[0])):
        if pref_raw.startswith(short) or pref_raw.startswith(official) or pref_raw == official:
            pref = official
            break
    return pref, dist


def party_key(value: str | None) -> str:
    return nfkc(value)


def party_match(yomi_party: str | None, seiji_party: str | None) -> bool:
    y = party_key(yomi_party)
    s = party_key(seiji_party)
    if not y or not s:
        return False
    if y == s:
        return True
    aliases = PARTY_ALIASES.get(y, {y})
    if s in aliases:
        return True
    for a in aliases:
        if a and (a in s or s in a):
            return True
    return False


def load_yomi_kanji() -> list[dict]:
    rows: list[dict] = []
    with KANJI_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                th = int(float(str(row.get("th") or "").strip()))
            except ValueError:
                continue
            pref, dist = parse_district_kanji(row.get("dstrct_Kanji") or "")
            if not pref or dist is None:
                continue
            try:
                vote = int(float(str(row.get("vote") or "").replace(",", "").strip()))
            except ValueError:
                continue
            kanji = (row.get("candidate_name") or "").strip()
            if not kanji:
                continue
            rows.append(
                {
                    "election_kaiji": th,
                    "prefecture": pref,
                    "district_number": dist,
                    "vote": vote,
                    "kanji": kanji,
                    "party": (row.get("party") or "").strip(),
                    "district_label": nfkc(row.get("dstrct_Kanji")),
                }
            )
    return rows


def load_seiji_candidates() -> list[dict]:
    if not SEIJI_PQ.is_file():
        raise SystemExit(f"missing {SEIJI_PQ}")
    con = duckdb.connect()
    df = con.execute(
        """
        SELECT election_kaiji, prefecture, district_number, candidate, party, value AS vote
        FROM read_parquet(?)
        WHERE metric = 'candidate_votes'
          AND candidate IS NOT NULL
          AND value IS NOT NULL
        """,
        [str(SEIJI_PQ)],
    ).fetchdf()
    rows = []
    for r in df.itertuples(index=False):
        rows.append(
            {
                "election_kaiji": int(r.election_kaiji),
                "prefecture": str(r.prefecture or ""),
                "district_number": int(r.district_number),
                "kana": str(r.candidate or "").strip(),
                "party": str(r.party or "").strip(),
                "vote": int(r.vote),
            }
        )
    return rows


def match_all(yomi: list[dict], seiji: list[dict]) -> tuple[list[dict], list[dict], Counter]:
    by_key: dict[tuple[int, str, int, int], list[dict]] = defaultdict(list)
    for y in yomi:
        by_key[(y["election_kaiji"], y["prefecture"], y["district_number"], y["vote"])].append(y)

    matched: list[dict] = []
    unmatched: list[dict] = []
    methods = Counter()

    for s in seiji:
        key = (s["election_kaiji"], s["prefecture"], s["district_number"], s["vote"])
        cands = by_key.get(key) or []
        method = None
        chosen = None
        if len(cands) == 1:
            chosen = cands[0]
            method = "th_pref_dist_vote"
        elif len(cands) > 1:
            party_hits = [c for c in cands if party_match(c["party"], s["party"])]
            if len(party_hits) == 1:
                chosen = party_hits[0]
                method = "th_pref_dist_vote_party"
            else:
                # 同票・同区で複数 → 未突合扱い
                method = None

        if chosen is None:
            unmatched.append(s)
            methods["unmatched"] += 1
            continue

        methods[method] += 1
        matched.append(
            {
                "election_kaiji": s["election_kaiji"],
                "prefecture": s["prefecture"],
                "district_number": s["district_number"],
                "kana": s["kana"],
                "kana_norm": kana_compact(s["kana"]),
                "kanji": chosen["kanji"],
                "kanji_norm": normalize_name(chosen["kanji"]),
                "vote": s["vote"],
                "party_seiji": s["party"] or None,
                "party_yomi": chosen["party"] or None,
                "match_method": method,
                "source": "yomi-candidate-kanji",
            }
        )
    return matched, unmatched, methods


def main() -> None:
    if not KANJI_CSV.is_file():
        raise SystemExit(f"missing {KANJI_CSV}")
    yomi = load_yomi_kanji()
    seiji = load_seiji_candidates()
    matched, unmatched, methods = match_all(yomi, seiji)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    staging = OUT_DIR / f"{stamp}_seiji_candidate_name_map.jsonl"
    with staging.open("w", encoding="utf-8", newline="\n") as f:
        for row in matched:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (OUT_DIR / "seiji_candidate_name_map.jsonl").write_text(staging.read_text(encoding="utf-8"), encoding="utf-8")

    WAREHOUSE_OUT.parent.mkdir(parents=True, exist_ok=True)
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    if matched:
        con = duckdb.connect()
        con.execute(
            f"""
            COPY (
              SELECT * FROM read_json_auto('{staging.as_posix()}')
              ORDER BY election_kaiji, prefecture, district_number, vote DESC, kana
            ) TO '{WAREHOUSE_OUT.as_posix()}' (FORMAT PARQUET)
            """
        )
        WEB_OUT.write_bytes(WAREHOUSE_OUT.read_bytes())
    else:
        raise SystemExit("no matches")

    report_lines = [
        "# seiji kana → yomi kanji match report",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        f"yomi_rows_usable={len(yomi)}",
        f"seiji_candidate_rows={len(seiji)}",
        f"matched={len(matched)}",
        f"unmatched={len(unmatched)}",
        f"match_rate={len(matched) / max(len(seiji), 1):.4f}",
        f"web_out={WEB_OUT}",
        "",
        "## methods",
        *[f"- {k}: {v}" for k, v in sorted(methods.items())],
        "",
        "## unmatched sample (up to 30)",
    ]
    for u in unmatched[:30]:
        report_lines.append(
            f"- th={u['election_kaiji']} {u['prefecture']}{u['district_number']}区 "
            f"{u['kana']} vote={u['vote']} party={u['party']}"
        )
    report = OUT_DIR / f"{stamp}_kanji_match_report.txt"
    report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    (OUT_DIR / "kanji_match_report.txt").write_text(report.read_text(encoding="utf-8"), encoding="utf-8")
    print(report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
