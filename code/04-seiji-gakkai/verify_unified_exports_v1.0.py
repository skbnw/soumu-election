# -*- coding: utf-8 -*-
"""verify_unified_exports_v1.0.py — SH-HD / turnout grain / kanji map / source_code 分布"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "output" / "04-seiji-gakkai"
WEB = REPO / "web" / "data"


def main() -> None:
    con = duckdb.connect()
    lines = [
        "# unified export verification",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "",
    ]

    pr_muni = WEB / "seiji_gakkai_pr_municipality_votes.parquet"
    turnout = WEB / "seiji_gakkai_turnout.parquet"
    name_map = WEB / "seiji_candidate_name_map.parquet"
    district = WEB / "seiji_gakkai_smd_district_votes.parquet"

    for label, path, sql in [
        (
            "SH-HD pr municipality",
            pr_muni,
            f"""
            SELECT count(*) AS rows,
                   count(DISTINCT election_kaiji) AS kaiji,
                   count(DISTINCT source_code) AS sources
            FROM read_parquet('{pr_muni.as_posix()}')
            """,
        ),
        (
            "turnout grains",
            turnout,
            f"""
            SELECT grain, contest, count(*) AS n
            FROM read_parquet('{turnout.as_posix()}')
            GROUP BY 1, 2 ORDER BY 2, 1
            """,
        ),
        (
            "kanji map",
            name_map,
            f"""
            SELECT count(*) AS matched_rows,
                   count(DISTINCT election_kaiji) AS kaiji,
                   count(DISTINCT match_method) AS methods
            FROM read_parquet('{name_map.as_posix()}')
            """,
        ),
    ]:
        lines.append(f"## {label}")
        if not path.is_file():
            lines.append(f"MISSING {path}")
            lines.append("")
            continue
        df = con.execute(sql).fetchdf()
        lines.append(df.to_string(index=False))
        lines.append("")

    if pr_muni.is_file():
        src = con.execute(
            f"""
            SELECT source_code, count(*) n
            FROM read_parquet('{pr_muni.as_posix()}')
            GROUP BY 1 ORDER BY 1
            """
        ).fetchdf()
        lines.append("## SH-HD source_code")
        lines.append(src.to_string(index=False))
        lines.append("")

    if district.is_file() and name_map.is_file():
        rate = con.execute(
            f"""
            WITH seiji AS (
              SELECT count(*) AS n
              FROM read_parquet('{district.as_posix()}')
              WHERE metric='candidate_votes'
            ),
            mapped AS (
              SELECT count(*) AS n FROM read_parquet('{name_map.as_posix()}')
            )
            SELECT seiji.n AS seiji_candidates, mapped.n AS mapped,
                   round(mapped.n::DOUBLE / seiji.n, 4) AS match_rate
            FROM seiji, mapped
            """
        ).fetchdf()
        lines.append("## kana→kanji match rate vs seiji district")
        lines.append(rate.to_string(index=False))
        lines.append("")

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT / f"{stamp}_unified_verify_report.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "unified_verify_report.txt").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
