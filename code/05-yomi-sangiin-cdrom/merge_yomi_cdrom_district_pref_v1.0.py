# -*- coding: utf-8 -*-
"""
読売参院 CD-ROM 県区（都道府県計）→ facts 穴埋め
v1.0
- 対象: 参24（2016）・参26（2022）。MIC 03-13 未接続の県区 candidate_votes を二次補充
- 原本: PoliData yomi CD-ROM snk_tokuhyo.csv（県計=市区町村CD 000）
- source_code: yomi-cdrom-district-pref-{NN}
- 合区名を MIC 03-13 形式へ正規化（鳥取・島根→鳥取県・島根県 等）
- 党派は MIC municipality_facts の集計から得票一致で付与（付かない場合は空）
- 当落は改選定数（district_number）上位で判定
- MIC 行は落とさない。同一 source_code のみ置換

使い方:
  python code/05-yomi-sangiin-cdrom/merge_yomi_cdrom_district_pref_v1.0.py
  python code/05-yomi-sangiin-cdrom/merge_yomi_cdrom_district_pref_v1.0.py --kaiji 24
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from soumu_election.municipality import write_parquet  # noqa: E402
from soumu_election.warehouse import FACT_COLUMNS, fact_row  # noqa: E402

CDROM = Path(
    r"C:\Users\SKBNW\Documents\PoliData_Development\PoliData_election"
    r"\01-sources\yomi\00-original\cd-rom\02_sangiin"
)
YEAR_TO_KAIJI = {2016: 24, 2022: 26}
KAIJI_TO_YEAR = {v: k for k, v in YEAR_TO_KAIJI.items()}
SOURCE_PREFIX = "yomi-cdrom-district-pref"
OUT_DIR = ROOT / "output" / "05-yomi-sangiin-cdrom"

# 改選数（Wikipedia 等。district_number に格納）
SEATS_24: dict[str, int] = {
    "北海道": 3, "青森県": 1, "岩手県": 1, "宮城県": 1, "秋田県": 1, "山形県": 1, "福島県": 1,
    "茨城県": 2, "栃木県": 1, "群馬県": 1, "埼玉県": 3, "千葉県": 3, "東京都": 6, "神奈川県": 4,
    "新潟県": 1, "富山県": 1, "石川県": 1, "福井県": 1, "山梨県": 1, "長野県": 1, "岐阜県": 1,
    "静岡県": 2, "愛知県": 4, "三重県": 1, "滋賀県": 1, "京都府": 2, "大阪府": 4, "兵庫県": 3,
    "奈良県": 1, "和歌山県": 1, "鳥取県・島根県": 1, "岡山県": 1, "広島県": 2, "山口県": 1,
    "徳島県・高知県": 1, "香川県": 1, "愛媛県": 1, "福岡県": 3, "佐賀県": 1, "長崎県": 1,
    "熊本県": 1, "大分県": 1, "宮崎県": 1, "鹿児島県": 1, "沖縄県": 1,
}
# 2022: 埼玉+1、神奈川は欠員補充込みで改選5
SEATS_26: dict[str, int] = {**SEATS_24, "埼玉県": 4, "神奈川県": 5}
SEATS_BY_KAIJI = {24: SEATS_24, 26: SEATS_26}

GOKU_MAP = {
    "鳥取・島根": "鳥取県・島根県",
    "鳥取県・島根県": "鳥取県・島根県",
    "徳島・高知": "徳島県・高知県",
    "徳島県・高知県": "徳島県・高知県",
}
GOKU_MEMBERS = {
    "鳥取県・島根県": ("鳥取県", "島根県"),
    "徳島県・高知県": ("徳島県", "高知県"),
}


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", (s or "").strip())


def compact_name(s: str) -> str:
    return re.sub(r"[\s\u3000]", "", nfkc(s))


def normalize_pref(raw: str) -> str | None:
    name = nfkc(raw)
    if not name:
        return None
    if name in GOKU_MAP:
        return GOKU_MAP[name]
    if name.endswith(("都", "道", "府", "県")):
        return name
    # 東京 → 東京都 等は稀だが念のため
    for suffix in ("都", "道", "府", "県"):
        cand = name + suffix
        if cand in SEATS_24:
            return cand
    return name


def read_yomi_pref_rows(kaiji: int) -> list[dict[str, Any]]:
    year = KAIJI_TO_YEAR[kaiji]
    path = CDROM / str(year) / "snk_tokuhyo.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    with path.open(encoding="cp932", newline="") as f:
        for item in csv.DictReader(f):
            if (item.get("市区町村CD") or "").strip() != "000":
                continue
            pref = normalize_pref(item.get("都道府県名", ""))
            raw_name = nfkc(item.get("候補者名", ""))
            cand = compact_name(raw_name)
            raw_votes = (item.get("得票数") or "").strip().replace(",", "")
            if not pref or not cand or not raw_votes:
                continue
            try:
                votes = int(float(raw_votes))
            except ValueError:
                continue
            rows.append(
                {
                    "election_kaiji": kaiji,
                    "prefecture": pref,
                    "candidate": cand,
                    "candidate_raw": raw_name,
                    "value": float(votes),
                    "todoke": (item.get("届出番号") or "").strip(),
                    "source_file": path.name,
                    "year": year,
                }
            )
    return rows


def load_mic_party_index(con: duckdb.DuckDBPyConnection, kaiji: int) -> dict[str, Any]:
    """MIC 市区町村集計から党派付与用インデックスを作る。"""
    muni = (ROOT / "web" / "data" / "municipality_facts.parquet").as_posix()
    df = con.execute(
        f"""
        SELECT prefecture, candidate, any_value(party) AS party, sum(value)::BIGINT AS votes
        FROM read_parquet('{muni}')
        WHERE election_id LIKE 'sangiin-%'
          AND election_kaiji = {int(kaiji)}
          AND contest = 'district'
          AND metric = 'candidate_votes'
          AND municipality IS NOT NULL AND municipality <> ''
          AND value IS NOT NULL
        GROUP BY 1, 2
        """
    ).fetchdf()

    by_pref_votes: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    name_idx: dict[str, dict[str, str]] = defaultdict(dict)
    goku_cand: dict[str, dict[str, tuple[int, str]]] = {
        "鳥取県・島根県": {},
        "徳島県・高知県": {},
    }

    for item in df.to_dict("records"):
        pref = nfkc(str(item["prefecture"]))
        party = nfkc(str(item["party"] or "")) or ""
        votes = int(item["votes"])
        cand = compact_name(str(item["candidate"] or ""))
        if cand and party:
            name_idx[pref][cand] = party
        if pref in ("鳥取県", "島根県"):
            g = "鳥取県・島根県"
            prev = goku_cand[g].get(cand)
            if prev is None or votes > prev[0]:
                goku_cand[g][cand] = (votes, party)
            if cand and party:
                name_idx[g][cand] = party
        elif pref in ("徳島県", "高知県"):
            g = "徳島県・高知県"
            prev = goku_cand[g].get(cand)
            if prev is None or votes > prev[0]:
                goku_cand[g][cand] = (votes, party)
            if cand and party:
                name_idx[g][cand] = party
        else:
            if party:
                by_pref_votes[pref][votes].append(party)

    for g, cmap in goku_cand.items():
        for _cand, (votes, party) in cmap.items():
            if party:
                by_pref_votes[g][votes].append(party)

    return {"votes": by_pref_votes, "name": name_idx}


def attach_party(row: dict[str, Any], party_index: dict) -> str | None:
    pref = row["prefecture"]
    votes = int(row["value"])
    cand = row["candidate"]
    vote_map = party_index["votes"].get(pref) or {}
    parties = vote_map.get(votes) or []
    uniq = sorted({p for p in parties if p})
    if len(uniq) == 1:
        return uniq[0]
    # 名前完全一致（かな同士は稀。漢字読売 vs かなMIC は一致しにくい）
    name_map = party_index["name"].get(pref) or {}
    if cand in name_map:
        return name_map[cand]
    # 部分一致（MIC が「林よしまさ」、読売が「林芳正」などは別途 aliases が必要 → 先頭2文字+得票で再試行はしない）
    for mic_name, party in name_map.items():
        if cand and mic_name and (cand in mic_name or mic_name in cand):
            return party
    return uniq[0] if uniq else None


def build_fact_items(kaiji: int, party_index: dict) -> list[dict[str, Any]]:
    seats_map = SEATS_BY_KAIJI[kaiji]
    source_code = f"{SOURCE_PREFIX}-{kaiji:02d}"
    raw_rows = read_yomi_pref_rows(kaiji)
    items: list[dict[str, Any]] = []
    for row in raw_rows:
        party = attach_party(row, party_index)
        seats = seats_map.get(row["prefecture"])
        items.append(
            {
                "election_kaiji": kaiji,
                "chamber": "sangiin",
                "election_type": "sangiin",
                "contest": "district",
                "prefecture": row["prefecture"],
                "district_number": seats,
                "candidate": row["candidate"],
                "candidate_raw": row["candidate_raw"],
                "party": party,
                "elected": None,
                "metric": "candidate_votes",
                "value": row["value"],
                "unit": "votes",
                "source_code": source_code,
                "dataset": f"読売新聞CD-ROM 参院選挙区（都道府県計） 第{kaiji}回",
                "source_url": None,
                "source_file": row["source_file"],
                "source_sheet": "pref_total",
                "source_cell": f"{row['prefecture']}:{row['candidate_raw']}",
            }
        )

    # 当落
    by_pref: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_pref[item["prefecture"]].append(item)
    for pref, pref_rows in by_pref.items():
        seats = seats_map.get(pref) or 1
        ordered = sorted(pref_rows, key=lambda r: (-(r["value"] or 0), r["candidate"] or ""))
        winners = {id(r) for r in ordered[: int(seats)]}
        for row in pref_rows:
            row["elected"] = id(row) in winners
            row["district_number"] = seats
    return items


def merge_into_facts(kaiji_list: list[int]) -> dict[str, Any]:
    warehouse = ROOT / "data" / "warehouse" / "parquet" / "facts.parquet"
    web = ROOT / "web" / "data" / "facts.parquet"
    if not warehouse.exists() and not web.exists():
        raise FileNotFoundError("facts.parquet が見つかりません")
    src = warehouse if warehouse.exists() else web

    con = duckdb.connect()
    new_items: list[dict[str, Any]] = []
    for kaiji in kaiji_list:
        party_index = load_mic_party_index(con, kaiji)
        part = build_fact_items(kaiji, party_index)
        print(f"yomi-cdrom district-pref sangiin {kaiji}: {len(part)} rows", flush=True)
        new_items.extend(part)
    con.close()
    if not new_items:
        return {"added": 0}

    drop_codes = sorted({item["source_code"] for item in new_items})
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    tmp_new = warehouse.parent / "_yomi_cdrom_district_pref.parquet"
    new_fact_dicts = [dict(zip(FACT_COLUMNS, fact_row(item))) for item in new_items]
    write_parquet(new_fact_dicts, tmp_new)

    con = duckdb.connect()
    code_list = ", ".join("'" + c.replace("'", "''") + "'" for c in drop_codes)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE merged AS
        SELECT * FROM read_parquet(?)
        WHERE source_code IS NULL OR cast(source_code AS VARCHAR) NOT IN ({code_list})
        """,
        [str(src)],
    )
    kept = con.execute("SELECT count(*) FROM merged").fetchone()[0]
    con.execute("INSERT INTO merged BY NAME SELECT * FROM read_parquet(?)", [str(tmp_new)])
    total = con.execute("SELECT count(*) FROM merged").fetchone()[0]
    by_kaiji = con.execute(
        f"""
        SELECT election_kaiji, count(*) AS n,
               count(DISTINCT prefecture) AS prefs,
               count(*) FILTER (WHERE party IS NOT NULL AND cast(party AS VARCHAR) <> '') AS with_party
        FROM merged
        WHERE cast(source_code AS VARCHAR) LIKE '{SOURCE_PREFIX}-%'
          AND contest='district' AND metric='candidate_votes'
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    con.execute("COPY merged TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(warehouse)])
    con.close()
    tmp_new.unlink(missing_ok=True)

    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_bytes(warehouse.read_bytes())
    return {
        "added": len(new_fact_dicts),
        "kept": int(kept),
        "total": int(total),
        "by_kaiji": by_kaiji,
        "warehouse": str(warehouse),
        "web": str(web),
        "drop_codes": drop_codes,
    }


def verify(kaiji_list: list[int]) -> dict[str, Any]:
    facts = (ROOT / "web" / "data" / "facts.parquet").as_posix()
    con = duckdb.connect()
    out: dict[str, Any] = {}
    for kaiji in kaiji_list:
        year = KAIJI_TO_YEAR[kaiji]
        yomi = read_yomi_pref_rows(kaiji)
        yomi_map = {(r["prefecture"], r["candidate"]): int(r["value"]) for r in yomi}
        df = con.execute(
            f"""
            SELECT prefecture, candidate, value, party, elected, source_code
            FROM read_parquet('{facts}')
            WHERE election_id LIKE 'sangiin-%'
              AND election_kaiji = {kaiji}
              AND contest = 'district'
              AND metric = 'candidate_votes'
            """
        ).fetchdf()
        fact_map = {
            (nfkc(str(r.prefecture)), compact_name(str(r.candidate))): int(r.value)
            for r in df.itertuples()
        }
        both = set(yomi_map) & set(fact_map)
        exact = sum(1 for k in both if yomi_map[k] == fact_map[k])
        out[kaiji] = {
            "year": year,
            "yomi_n": len(yomi_map),
            "facts_n": len(fact_map),
            "both_n": len(both),
            "exact_match_n": exact,
            "source_codes": sorted({str(x) for x in df["source_code"].dropna().unique()}),
            "prefs": int(df["prefecture"].nunique()) if len(df) else 0,
            "with_party": int(df["party"].notna().sum()) if len(df) else 0,
            "elected_true": int((df["elected"] == True).sum()) if len(df) else 0,  # noqa: E712
            "sample": df.sort_values("value", ascending=False).head(5).to_dict("records"),
        }
    con.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kaiji", type=int, nargs="*", default=[24, 26])
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    kaiji_list = list(args.kaiji)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")

    result: dict[str, Any] = {"generated_at": stamp, "kaiji": kaiji_list}
    if not args.verify_only:
        result["merge"] = merge_into_facts(kaiji_list)
        print(result["merge"], flush=True)
    result["verify"] = verify(kaiji_list)

    out_json = OUT_DIR / f"{stamp}_yomi_cdrom_district_pref_merge.json"
    out_txt = OUT_DIR / f"{stamp}_yomi_cdrom_district_pref_merge.txt"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = [f"読売CD-ROM 県区 facts 接続 ({stamp})", f"kaiji={kaiji_list}", ""]
    if "merge" in result:
        lines.append(f"merge: {result['merge']}")
        lines.append("")
    for kaiji, info in result["verify"].items():
        lines.append(f"## 参{kaiji}")
        for k, v in info.items():
            if k == "sample":
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")
    out_txt.write_text("\n".join(lines), encoding="utf-8")
    print(out_txt.read_text(encoding="utf-8"))
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
