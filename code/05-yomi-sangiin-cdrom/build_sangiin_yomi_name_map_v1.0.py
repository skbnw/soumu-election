# -*- coding: utf-8 -*-
"""
参院・読売候補者名マップ
v1.1
- 読売選挙DB立候補者リスト（yomi-senkyoDB-list）で CD-ROM 欠落回を穴埋め
  （facts の得票キーに DB 漢字名を載せる。数値は触らない）
- 突合優先: 得票一致の CD-ROM → 同一県内の氏名一致 / 白書一意名
v1.0
- CD-ROM snk_tokuhyo から表示用漢字名を抽出
- キー: (election_kaiji, prefecture, [municipality], vote)
- UI で MIC/関西大のかな混じり名を読売表記に置換（数値は触らない）

出力:
  web/data/sangiin_yomi_name_map.parquet
  data/warehouse/parquet/sangiin_yomi_name_map.parquet
  output/05-yomi-sangiin-cdrom/*_sangiin_yomi_name_map_report.txt
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
CDROM = Path(
    r"C:\Users\SKBNW\Documents\PoliData_Development\PoliData_election"
    r"\01-sources\yomi\00-original\cd-rom\02_sangiin"
)
YEAR_TO_KAIJI = {2007: 21, 2010: 22, 2013: 23, 2016: 24, 2019: 25, 2022: 26}
GOKU_MAP = {
    "鳥取・島根": "鳥取県・島根県",
    "鳥取県・島根県": "鳥取県・島根県",
    "徳島・高知": "徳島県・高知県",
    "徳島県・高知県": "徳島県・高知県",
}
WEB_OUT = ROOT / "web" / "data" / "sangiin_yomi_name_map.parquet"
WARE_OUT = ROOT / "data" / "warehouse" / "parquet" / "sangiin_yomi_name_map.parquet"
OUT_DIR = ROOT / "output" / "05-yomi-sangiin-cdrom"
SENKYODB_PARQUET = ROOT / "web" / "data" / "yomi_senkyodb_candidates.parquet"
KOKKAI_ROOT = ROOT / "references" / "kokkai.sugawarataku.net"

HREF_RE = re.compile(r"/giin/(r\d+)\.html", re.I)
IVS_RE = re.compile(r"[\uFE00-\uFE0F\U000E0100-\U000E01EF]")
PUA_RE = re.compile(r"[\uE000-\uF8FF]")
SPACE_RE = re.compile(r"[\s\u3000]+")


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", (s or "").strip())


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    s = IVS_RE.sub("", str(value))
    s = unicodedata.normalize("NFKC", s)
    s = SPACE_RE.sub("", s)
    return s


def normalize_name_soft(value: str | None) -> str:
    s = PUA_RE.sub("", normalize_name(value))
    # よくある異体字を照合用に寄せる（表示名自体は DB 側の表記を採用）
    return (
        s.replace("髙", "高")
        .replace("﨑", "崎")
        .replace("濵", "浜")
        .replace("邉", "辺")
        .replace("𠮷", "吉")
    )


def normalize_pref(raw: str) -> str | None:
    name = nfkc(raw)
    if not name:
        return None
    return GOKU_MAP.get(name, name)


def is_pref_total(muni_cd: str, muni: str) -> bool:
    return muni_cd == "000" or muni in ("", " ")


def is_aggregate_muni(muni: str) -> bool:
    return bool(muni) and (muni.endswith("計") or muni.endswith("合計"))


def read_cdrom_rows() -> list[dict]:
    rows: list[dict] = []
    for year, kaiji in YEAR_TO_KAIJI.items():
        path = CDROM / str(year) / "snk_tokuhyo.csv"
        if not path.exists():
            continue
        with path.open(encoding="cp932", newline="") as f:
            for item in csv.DictReader(f):
                pref = normalize_pref(item.get("都道府県名", ""))
                muni = nfkc(item.get("市区町村名", ""))
                muni_cd = (item.get("市区町村CD") or "").strip()
                name = nfkc(item.get("候補者名", ""))
                raw_votes = (item.get("得票数") or "").strip().replace(",", "")
                if not pref or not name or not raw_votes:
                    continue
                try:
                    votes = int(float(raw_votes))
                except ValueError:
                    continue
                if is_pref_total(muni_cd, muni):
                    rows.append(
                        {
                            "election_kaiji": kaiji,
                            "election_year": year,
                            "grain": "prefecture",
                            "prefecture": pref,
                            "municipality": None,
                            "vote": votes,
                            "yomi_name": name,
                            "source_file": path.name,
                        }
                    )
                else:
                    if is_aggregate_muni(muni):
                        continue
                    rows.append(
                        {
                            "election_kaiji": kaiji,
                            "election_year": year,
                            "grain": "municipality",
                            "prefecture": pref,
                            "municipality": muni,
                            "vote": votes,
                            "yomi_name": name,
                            "source_file": path.name,
                        }
                    )
    return rows


def load_kokkai_unique_names() -> dict[str, str]:
    """normalize_name → person_id（一意のときのみ）."""
    buckets: dict[str, set[str]] = defaultdict(set)
    for folder in (KOKKAI_ROOT / "shugiin", KOKKAI_ROOT / "sangiin"):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.csv")):
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    href = row.get("zt5 href") or row.get("href") or ""
                    m = HREF_RE.search(href)
                    if not m:
                        continue
                    pid = m.group(1).lower()
                    kanji = (row.get("zt5") or row.get("name") or "").strip()
                    n = normalize_name(kanji)
                    if n:
                        buckets[n].add(pid)
    return {name: next(iter(ids)) for name, ids in buckets.items() if len(ids) == 1}


def load_senkyodb_district_by_pref() -> dict[tuple[int, str], list[str]]:
    if not SENKYODB_PARQUET.is_file():
        return {}
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT election_kaiji, prefecture, candidate_name
        FROM read_parquet('{SENKYODB_PARQUET.as_posix().replace("'", "''")}')
        WHERE chamber = 'sangiin'
          AND contest = 'district'
          AND prefecture IS NOT NULL
          AND candidate_name IS NOT NULL
        """
    ).fetchall()
    con.close()
    out: dict[tuple[int, str], list[str]] = defaultdict(list)
    for kaiji, pref, name in rows:
        out[(int(kaiji), str(pref))].append(nfkc(name))
    return out


def load_facts_district() -> list[dict]:
    facts = ROOT / "web" / "data" / "facts.parquet"
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT election_kaiji, prefecture, candidate, value::BIGINT AS vote
        FROM read_parquet('{facts.as_posix().replace("'", "''")}')
        WHERE election_id LIKE 'sangiin-%'
          AND contest = 'district'
          AND metric = 'candidate_votes'
          AND prefecture IS NOT NULL
          AND candidate IS NOT NULL
          AND value IS NOT NULL
        """
    ).fetchall()
    con.close()
    return [
        {
            "election_kaiji": int(kaiji),
            "prefecture": str(pref),
            "candidate": nfkc(cand),
            "vote": int(vote),
        }
        for kaiji, pref, cand, vote in rows
    ]


def resolve_db_name(
    fact_name: str,
    db_names: list[str],
    kokkai_unique: dict[str, str],
) -> tuple[str | None, str]:
    fact_n = normalize_name(fact_name)
    fact_s = normalize_name_soft(fact_name)
    exact = [n for n in db_names if normalize_name(n) == fact_n]
    if len(set(normalize_name(n) for n in exact)) == 1:
        return exact[0], "senkyodb_exact"
    soft = [n for n in db_names if normalize_name_soft(n) == fact_s]
    if len(set(normalize_name_soft(n) for n in soft)) == 1:
        return soft[0], "senkyodb_soft"

    pid = kokkai_unique.get(fact_n)
    if pid:
        matched = [n for n in db_names if kokkai_unique.get(normalize_name(n)) == pid]
        uniq = sorted(set(matched))
        if len(uniq) == 1:
            return uniq[0], "senkyodb_kokkai"

    # かな混じり→漢字: 白書一意の DB 名が県内に1人だけ、かつ姓（先頭漢字連続）が一致
    fact_kana = sum(1 for ch in fact_name if "ぁ" <= ch <= "ん" or "ァ" <= ch <= "ン")
    if fact_kana >= 2:
        # 姓候補: 先頭の漢字1〜3文字
        m = re.match(r"^([\u4E00-\u9FFF々〆ヵヶ]{1,3})", fact_name)
        family = m.group(1) if m else ""
        if family:
            cands = [n for n in db_names if n.startswith(family)]
            uniq = sorted(set(cands))
            if len(uniq) == 1 and normalize_name(uniq[0]) in kokkai_unique:
                return uniq[0], "senkyodb_family_unique"
    return None, "none"


def gap_fill_from_senkyodb(cdrom_rows: list[dict]) -> tuple[list[dict], dict]:
    covered = {
        (r["election_kaiji"], r["prefecture"], r["vote"])
        for r in cdrom_rows
        if r["grain"] == "prefecture"
    }
    db_by_pref = load_senkyodb_district_by_pref()
    if not db_by_pref:
        return [], {"added": 0, "by_reason": {}, "note": "senkyodb parquet missing"}
    db_by_kaiji: dict[int, list[str]] = defaultdict(list)
    for (kaiji, _pref), names in db_by_pref.items():
        db_by_kaiji[kaiji].extend(names)
    kokkai_unique = load_kokkai_unique_names()
    facts = load_facts_district()
    year_by_kaiji = {v: k for k, v in YEAR_TO_KAIJI.items()}
    year_by_kaiji.update({20: 2004, 27: 2025})

    added: list[dict] = []
    by_reason: dict[str, int] = defaultdict(int)
    seen: set[tuple] = set()
    for fact in facts:
        key = (fact["election_kaiji"], fact["prefecture"], fact["vote"])
        if key in covered or key in seen:
            continue
        pref_names = db_by_pref.get((fact["election_kaiji"], fact["prefecture"])) or []
        yomi_name, reason = resolve_db_name(fact["candidate"], pref_names, kokkai_unique)
        if not yomi_name:
            # facts 側の県名ズレ等: 同一回で氏名が一意なら採用
            kaiji_names = db_by_kaiji.get(fact["election_kaiji"]) or []
            yomi_name, reason = resolve_db_name(fact["candidate"], kaiji_names, kokkai_unique)
            if yomi_name:
                reason = f"{reason}_kaiji"
        if not yomi_name:
            continue
        seen.add(key)
        by_reason[reason] += 1
        added.append(
            {
                "election_kaiji": fact["election_kaiji"],
                "election_year": year_by_kaiji.get(fact["election_kaiji"]),
                "grain": "prefecture",
                "prefecture": fact["prefecture"],
                "municipality": None,
                "vote": fact["vote"],
                "yomi_name": yomi_name,
                "source_file": "sangiin-can-list-2004-2025.xlsx",
                "match_reason": reason,
            }
        )
    return added, {"added": len(added), "by_reason": dict(by_reason)}


def dedupe(rows: list[dict]) -> list[dict]:
    """同一キーで複数ある場合は CD-ROM を優先し、名前は安定選択。"""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            row["election_kaiji"],
            row["grain"],
            row["prefecture"],
            row["municipality"],
            row["vote"],
        )
        buckets[key].append(row)
    out = []
    for key, items in buckets.items():
        # CD-ROM (snk_tokuhyo) 優先
        preferred = [x for x in items if str(x.get("source_file", "")).startswith("snk_")]
        pool = preferred or items
        names = sorted({x["yomi_name"] for x in pool})
        base = dict(pool[0])
        base["yomi_name"] = names[0]
        base["name_variants"] = len(names)
        out.append(base)
    return out


def write_parquet(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ndjson = path.with_suffix(".ndjson")
    with ndjson.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    con = duckdb.connect()
    src = ndjson.as_posix().replace("'", "''")
    dst = path.as_posix().replace("'", "''")
    con.execute(
        f"""
        COPY (
          SELECT election_kaiji::BIGINT AS election_kaiji,
                 election_year::BIGINT AS election_year,
                 grain, prefecture, municipality,
                 vote::BIGINT AS vote,
                 yomi_name,
                 source_file,
                 name_variants::BIGINT AS name_variants
          FROM read_json_auto('{src}', format='newline_delimited', union_by_name=true)
        ) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    con.close()
    ndjson.unlink(missing_ok=True)


def coverage_report(rows: list[dict]) -> dict:
    con = duckdb.connect()
    facts = (ROOT / "web" / "data" / "facts.parquet").as_posix()
    muni = (ROOT / "web" / "data" / "municipality_facts.parquet").as_posix()
    tmp = OUT_DIR / "_tmp_name_map.parquet"
    write_parquet(rows, tmp)

    pref_rows = con.execute(
        f"""
        WITH y AS (
          SELECT * FROM read_parquet('{tmp.as_posix()}') WHERE grain='prefecture'
        ),
        f AS (
          SELECT election_kaiji, prefecture, candidate, value::BIGINT AS vote
          FROM read_parquet('{facts}')
          WHERE election_id LIKE 'sangiin-%'
            AND contest='district' AND metric='candidate_votes'
            AND value IS NOT NULL
        )
        SELECT f.election_kaiji,
               count(*) AS fact_n,
               count(y.yomi_name) AS mapped_n,
               count(*) FILTER (WHERE y.yomi_name IS NOT NULL AND y.yomi_name <> f.candidate) AS renamed_n
        FROM f
        LEFT JOIN y
          ON y.election_kaiji = f.election_kaiji
         AND y.prefecture = f.prefecture
         AND y.vote = f.vote
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    pref = [
        {"election_kaiji": int(a), "fact_n": int(b), "mapped_n": int(c), "renamed_n": int(d)}
        for a, b, c, d in pref_rows
    ]

    mun_rows = con.execute(
        f"""
        WITH y AS (
          SELECT * FROM read_parquet('{tmp.as_posix()}') WHERE grain='municipality'
        ),
        m AS (
          SELECT election_kaiji, prefecture, municipality, candidate, value::BIGINT AS vote
          FROM read_parquet('{muni}')
          WHERE election_id LIKE 'sangiin-%'
            AND contest='district' AND metric='candidate_votes'
            AND municipality IS NOT NULL AND municipality <> ''
            AND value IS NOT NULL
        )
        SELECT m.election_kaiji,
               count(*) AS muni_n,
               count(y.yomi_name) AS mapped_n,
               count(*) FILTER (WHERE y.yomi_name IS NOT NULL AND y.yomi_name <> m.candidate) AS renamed_n
        FROM m
        LEFT JOIN y
          ON y.election_kaiji = m.election_kaiji
         AND y.prefecture = m.prefecture
         AND y.municipality = m.municipality
         AND y.vote = m.vote
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()
    mun = [
        {"election_kaiji": int(a), "muni_n": int(b), "mapped_n": int(c), "renamed_n": int(d)}
        for a, b, c, d in mun_rows
    ]
    con.close()
    tmp.unlink(missing_ok=True)
    return {
        "pref_coverage": pref,
        "muni_coverage": mun,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    raw = read_cdrom_rows()
    gap_rows, gap_stats = gap_fill_from_senkyodb(raw)
    rows = dedupe(raw + gap_rows)
    write_parquet(rows, WEB_OUT)
    WARE_OUT.parent.mkdir(parents=True, exist_ok=True)
    WARE_OUT.write_bytes(WEB_OUT.read_bytes())
    cov = coverage_report(rows)

    report = {
        "generated_at": stamp,
        "rows": len(rows),
        "pref_rows": sum(1 for r in rows if r["grain"] == "prefecture"),
        "muni_rows": sum(1 for r in rows if r["grain"] == "municipality"),
        "cdrom_rows": len(raw),
        "senkyodb_gap_fill": gap_stats,
        "web_out": str(WEB_OUT),
        "coverage": cov,
    }
    out_json = OUT_DIR / f"{stamp}_sangiin_yomi_name_map_report.json"
    out_txt = OUT_DIR / f"{stamp}_sangiin_yomi_name_map_report.txt"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"参院読売名マップ ({stamp})",
        f"rows={report['rows']} pref={report['pref_rows']} muni={report['muni_rows']}",
        f"cdrom_raw={len(raw)} senkyodb_gap={gap_stats}",
        "",
        "## pref coverage vs facts",
    ]
    for item in cov["pref_coverage"]:
        lines.append(str(item))
    lines.append("")
    lines.append("## muni coverage vs municipality_facts")
    for item in cov["muni_coverage"]:
        lines.append(str(item))
    out_txt.write_text("\n".join(lines), encoding="utf-8")
    print(out_txt.read_text(encoding="utf-8"))
    print(f"wrote {WEB_OUT}")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
