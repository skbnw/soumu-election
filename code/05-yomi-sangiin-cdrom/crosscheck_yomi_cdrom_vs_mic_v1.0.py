# -*- coding: utf-8 -*-
"""
読売参院 CD-ROM × MIC 突合（サンプル）
v1.0
- 外部 CD-ROM（PoliData）の snk_tokuhyo を読み、MIC と比較
- A: 県計 vs facts（参25 / 03-13）
- B: 市区町村 vs municipality_facts（参25 / 03-14-district-*）
- C: 参考として参23 の県計を kansai-district-pref-23 とも比較

使い方:
  python code/05-yomi-sangiin-cdrom/crosscheck_yomi_cdrom_vs_mic_v1.0.py
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
YEAR_TO_KAIJI = {
    2004: 20,
    2007: 21,
    2010: 22,
    2013: 23,
    2016: 24,
    2019: 25,
    2022: 26,
}
FACTS = ROOT / "web" / "data" / "facts.parquet"
MUNI = ROOT / "web" / "data" / "municipality_facts.parquet"
OUT_DIR = ROOT / "output" / "05-yomi-sangiin-cdrom"


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", (s or "").strip())


def compact_name(s: str) -> str:
    s = nfkc(s)
    s = s.replace(" ", "").replace("\u3000", "")
    s = re.sub(r"[　\s]", "", s)
    return s


def read_snk_tokuhyo(year: int) -> list[dict]:
    path = CDROM / str(year) / "snk_tokuhyo.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict] = []
    with path.open(encoding="cp932", newline="") as f:
        for item in csv.DictReader(f):
            pref = nfkc(item.get("都道府県名", ""))
            muni = nfkc(item.get("市区町村名", ""))
            muni_cd = (item.get("市区町村CD") or "").strip()
            cand = compact_name(item.get("候補者名", ""))
            raw_votes = (item.get("得票数") or "").strip().replace(",", "")
            if not pref or not cand or not raw_votes:
                continue
            try:
                votes = int(float(raw_votes))
            except ValueError:
                continue
            rows.append(
                {
                    "year": year,
                    "kaiji": YEAR_TO_KAIJI[year],
                    "prefecture": pref,
                    "municipality": muni,
                    "municipality_cd": muni_cd,
                    "candidate": cand,
                    "candidate_raw": nfkc(item.get("候補者名", "")),
                    "votes": votes,
                    "todoke": (item.get("届出番号") or "").strip(),
                }
            )
    return rows


def is_pref_total(row: dict) -> bool:
    return row["municipality_cd"] == "000" or row["municipality"] in ("", " ")


def load_mic_pref(
    con: duckdb.DuckDBPyConnection, kaiji: int
) -> tuple[dict[tuple[str, str], int], list[str]]:
    df = con.execute(
        f"""
        SELECT prefecture, candidate, candidate_raw, value, source_code
        FROM read_parquet('{FACTS.as_posix()}')
        WHERE election_id LIKE 'sangiin-%'
          AND election_kaiji = {kaiji}
          AND contest = 'district'
          AND metric = 'candidate_votes'
          AND value IS NOT NULL
        """
    ).fetchdf()
    out: dict[tuple[str, str], int] = {}
    sources: set[str] = set()
    for item in df.to_dict("records"):
        sources.add(str(item["source_code"]))
        key = (
            nfkc(str(item["prefecture"])),
            compact_name(str(item.get("candidate") or item.get("candidate_raw") or "")),
        )
        if not key[0] or not key[1]:
            continue
        out[key] = int(item["value"])
    return out, sorted(sources)


def load_mic_muni(
    con: duckdb.DuckDBPyConnection, kaiji: int, prefecture: str
) -> tuple[dict[tuple[str, str], int], list[str]]:
    esc = prefecture.replace("'", "''")
    df = con.execute(
        f"""
        SELECT municipality, candidate, value, source_code
        FROM read_parquet('{MUNI.as_posix()}')
        WHERE election_id LIKE 'sangiin-%'
          AND election_kaiji = {kaiji}
          AND contest = 'district'
          AND metric = 'candidate_votes'
          AND prefecture = '{esc}'
          AND value IS NOT NULL
          AND municipality IS NOT NULL
          AND municipality <> ''
        """
    ).fetchdf()
    out: dict[tuple[str, str], int] = {}
    sources: set[str] = set()
    for item in df.to_dict("records"):
        sources.add(str(item["source_code"]))
        muni = nfkc(str(item["municipality"]))
        cand = compact_name(str(item.get("candidate") or ""))
        if not muni or not cand:
            continue
        out[(muni, cand)] = int(item["value"])
    return out, sorted(sources)


def compare_maps(
    left: dict[tuple, int],
    right: dict[tuple, int],
    *,
    left_label: str,
    right_label: str,
) -> dict:
    keys_l = set(left)
    keys_r = set(right)
    both = keys_l & keys_r
    only_l = sorted(keys_l - keys_r)
    only_r = sorted(keys_r - keys_l)
    matched = 0
    mismatched = []
    for key in sorted(both):
        if left[key] == right[key]:
            matched += 1
        else:
            mismatched.append(
                {
                    "key": list(key),
                    left_label: left[key],
                    right_label: right[key],
                    "diff": left[key] - right[key],
                }
            )
    return {
        "left": left_label,
        "right": right_label,
        "left_n": len(left),
        "right_n": len(right),
        "both_n": len(both),
        "exact_match_n": matched,
        "mismatch_n": len(mismatched),
        "only_left_n": len(only_l),
        "only_right_n": len(only_r),
        "exact_match_rate_both": (matched / len(both)) if both else None,
        "mismatch_samples": mismatched[:20],
        "only_left_samples": [list(k) for k in only_l[:15]],
        "only_right_samples": [list(k) for k in only_r[:15]],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    con = duckdb.connect()
    report: dict = {
        "generated_at": stamp,
        "cdrom_root": str(CDROM),
        "checks": [],
    }

    # A: 参25 県計 vs MIC 03-13
    yomi25 = read_snk_tokuhyo(2019)
    yomi25_pref = {
        (r["prefecture"], r["candidate"]): r["votes"] for r in yomi25 if is_pref_total(r)
    }
    mic25, mic25_src = load_mic_pref(con, 25)
    check_a = compare_maps(yomi25_pref, mic25, left_label="yomi_cdrom", right_label="mic_facts")
    check_a["title"] = "A: 参25 県計 snk_tokuhyo vs facts district"
    check_a["mic_sources"] = mic25_src
    check_a["yomi_year"] = 2019
    report["checks"].append(check_a)

    # B: 参25 山口県 市区町村 vs MIC 03-14
    pref = "山口県"
    yomi25_muni = {
        (r["municipality"], r["candidate"]): r["votes"]
        for r in yomi25
        if r["prefecture"] == pref and not is_pref_total(r)
    }
    mic25_muni, mic25_muni_src = load_mic_muni(con, 25, pref)
    check_b = compare_maps(
        yomi25_muni, mic25_muni, left_label="yomi_cdrom", right_label="mic_muni"
    )
    check_b["title"] = f"B: 参25 {pref} 市区町村 snk_tokuhyo vs municipality_facts"
    check_b["mic_sources"] = mic25_muni_src
    check_b["prefecture"] = pref
    report["checks"].append(check_b)

    # C: 参23 県計 vs kansai-district-pref-23（MIC 03-13 が無い回）
    yomi23 = read_snk_tokuhyo(2013)
    yomi23_pref = {
        (r["prefecture"], r["candidate"]): r["votes"] for r in yomi23 if is_pref_total(r)
    }
    kansai23, kansai23_src = load_mic_pref(con, 23)
    check_c = compare_maps(
        yomi23_pref, kansai23, left_label="yomi_cdrom", right_label="warehouse_pref"
    )
    check_c["title"] = "C: 参23 県計 snk_tokuhyo vs facts（kansai-district-pref-23）"
    check_c["mic_sources"] = kansai23_src
    check_c["yomi_year"] = 2013
    report["checks"].append(check_c)

    # D: 参24/26 の CD-ROM 側カバレッジ（MIC facts 県区が無いことの確認付き）
    for year, kaiji in ((2016, 24), (2022, 26)):
        rows = read_snk_tokuhyo(year)
        pref_rows = [r for r in rows if is_pref_total(r)]
        muni_rows = [r for r in rows if not is_pref_total(r)]
        mic, mic_src = load_mic_pref(con, kaiji)
        report["checks"].append(
            {
                "title": f"D: 参{kaiji} CD-ROM coverage（facts 県区との有無）",
                "yomi_year": year,
                "kaiji": kaiji,
                "yomi_pref_candidate_rows": len(pref_rows),
                "yomi_muni_candidate_rows": len(muni_rows),
                "yomi_prefs": sorted({r["prefecture"] for r in pref_rows}),
                "facts_district_rows": len(mic),
                "facts_sources": mic_src,
            }
        )

    out_json = OUT_DIR / f"{stamp}_yomi_cdrom_vs_mic_crosscheck.json"
    out_txt = OUT_DIR / f"{stamp}_yomi_cdrom_vs_mic_crosscheck.txt"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"読売参院 CD-ROM × MIC 突合レポート ({stamp})",
        f"CD-ROM: {CDROM}",
        "",
    ]
    for check in report["checks"]:
        lines.append(f"## {check['title']}")
        for key, val in check.items():
            if key in ("title", "mismatch_samples", "only_left_samples", "only_right_samples", "yomi_prefs"):
                continue
            lines.append(f"- {key}: {val}")
        if check.get("yomi_prefs"):
            lines.append(f"- yomi_prefs ({len(check['yomi_prefs'])}): {', '.join(check['yomi_prefs'][:10])} ...")
        if check.get("mismatch_samples"):
            lines.append("- mismatch_samples:")
            for sample in check["mismatch_samples"][:10]:
                lines.append(f"  - {sample}")
        if check.get("only_left_samples"):
            lines.append(f"- only_left_samples: {check['only_left_samples'][:8]}")
        if check.get("only_right_samples"):
            lines.append(f"- only_right_samples: {check['only_right_samples'][:8]}")
        lines.append("")

    out_txt.write_text("\n".join(lines), encoding="utf-8")
    print(out_txt.read_text(encoding="utf-8"))
    print(f"wrote {out_json}")
    print(f"wrote {out_txt}")


if __name__ == "__main__":
    main()
