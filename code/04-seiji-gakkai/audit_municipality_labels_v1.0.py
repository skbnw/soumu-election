# -*- coding: utf-8 -*-
"""
audit_municipality_labels_v1.0.py
- 政治学会／MIC の市区町村表示名ゆれを監査し、レポートを output に残す
- v1.0: 開票区接尾（市-N / 市N区 / 市（N区））と 市×市連結残骸を点検

使い方:
  python code/04-seiji-gakkai/audit_municipality_labels_v1.0.py

出力:
  output/04-seiji-gakkai/yyyymmdd_HHMM_muni_label_audit.txt
  output/04-seiji-gakkai/muni_label_audit.txt（最新コピー）
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web" / "data"
OUT_DIR = REPO / "output" / "04-seiji-gakkai"

SOURCES = [
    ("seiji_smd", WEB / "seiji_gakkai_smd_municipality_votes.parquet"),
    ("seiji_pr", WEB / "seiji_gakkai_pr_municipality_votes.parquet"),
    ("seiji_turnout", WEB / "seiji_gakkai_turnout.parquet"),
    ("mic", WEB / "municipality_facts.parquet"),
]

NORM_CASE = """
CASE
  WHEN regexp_matches(municipality, '^.+-\\d+$')
    THEN regexp_replace(municipality, '^(.+)-(\\d+)$', '\\1（\\2区）')
  WHEN regexp_matches(municipality, '^.+[市町村]\\d+区$')
    THEN regexp_replace(municipality, '^(.+[市町村])(\\d+)区$', '\\1（\\2区）')
  ELSE municipality
END
"""


def section_pattern_counts(con: duckdb.DuckDBPyConnection, label: str, path: Path) -> list[str]:
    lines = [f"## {label}", f"path={path}"]
    if not path.is_file():
        lines.append("MISSING")
        lines.append("")
        return lines
    p = path.as_posix()
    row = con.execute(
        f"""
        SELECT
          count(*) AS n,
          sum(CASE WHEN municipality IS NOT NULL AND regexp_matches(municipality, '^.+-\\d+$') THEN 1 ELSE 0 END) AS dash_n,
          sum(CASE WHEN municipality IS NOT NULL AND regexp_matches(municipality, '^.+[市町村]\\d+区$') THEN 1 ELSE 0 END) AS city_n_ku,
          sum(CASE WHEN municipality IS NOT NULL AND regexp_matches(municipality, '^.+（\\d+区）$') THEN 1 ELSE 0 END) AS paren_ku,
          count(DISTINCT CASE WHEN municipality IS NOT NULL AND regexp_matches(municipality, '^.+-\\d+$') THEN municipality END) AS dash_names,
          count(DISTINCT CASE WHEN municipality IS NOT NULL AND regexp_matches(municipality, '^.+[市町村]\\d+区$') THEN municipality END) AS nku_names,
          count(DISTINCT CASE WHEN municipality IS NOT NULL AND regexp_matches(municipality, '^.+（\\d+区）$') THEN municipality END) AS paren_names
        FROM read_parquet('{p}')
        """
    ).fetchone()
    lines.append(
        "rows={0} dash={1} cityNku={2} paren={3} | distinct dash={4} cityNku={5} paren={6}".format(*row)
    )
    samples = con.execute(
        f"""
        SELECT municipality, count(*) AS n
        FROM read_parquet('{p}')
        WHERE municipality IS NOT NULL
          AND (
            regexp_matches(municipality, '^.+-\\d+$')
            OR regexp_matches(municipality, '^.+[市町村]\\d+区$')
          )
        GROUP BY 1
        ORDER BY 1
        LIMIT 30
        """
    ).fetchall()
    if samples:
        lines.append("samples (dash / cityNku):")
        for s in samples:
            lines.append(f"  {s[0]}\t{s[1]}")
    else:
        lines.append("samples (dash / cityNku): (none)")
    lines.append("")
    return lines


def section_shi_shi(con: duckdb.DuckDBPyConnection) -> list[str]:
    lines = ["## shi×shi concat remnants (seiji_smd)", "rule: municipality looks like X市Y市 and city_raw<>ward_raw"]
    p = (WEB / "seiji_gakkai_smd_municipality_votes.parquet").as_posix()
    if not (WEB / "seiji_gakkai_smd_municipality_votes.parquet").is_file():
        lines.append("MISSING seiji_smd")
        lines.append("")
        return lines
    rows = con.execute(
        f"""
        SELECT DISTINCT election_kaiji, prefecture, district_number,
               city_raw, ward_raw, municipality, name_flags
        FROM read_parquet('{p}')
        WHERE city_raw IS NOT NULL AND ward_raw IS NOT NULL
          AND trim(city_raw) <> trim(ward_raw)
          AND ends_with(trim(city_raw), '市')
          AND ends_with(trim(ward_raw), '市')
          AND municipality = concat(
                coalesce(nullif(city, ''), trim(city_raw)),
                coalesce(nullif(ward, ''), trim(ward_raw))
              )
        ORDER BY election_kaiji, prefecture, municipality
        """
    ).fetchall()
    lines.append(f"concat_remnants={len(rows)} (expect 0 after v1.0.2 compose)")
    for r in rows[:40]:
        lines.append("  " + "\t".join("" if v is None else str(v) for v in r))
    # flags evidence
    flagged = con.execute(
        f"""
        SELECT name_flags, count(DISTINCT municipality) AS n_muni, count(*) AS n_rows
        FROM read_parquet('{p}')
        WHERE name_flags IS NOT NULL
          AND name_flags LIKE '%skip_shi_shi_concat%'
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    lines.append("skip_shi_shi_concat flags:")
    if not flagged:
        lines.append("  (none)")
    for r in flagged:
        lines.append(f"  {r[0]}\tmuni={r[1]}\trows={r[2]}")
    lines.append("")
    return lines


def section_cross_norm(con: duckdb.DuckDBPyConnection) -> list[str]:
    lines = ["## cross-source collisions under UI norm key"]
    smd = WEB / "seiji_gakkai_smd_municipality_votes.parquet"
    mic = WEB / "municipality_facts.parquet"
    if not smd.is_file() or not mic.is_file():
        lines.append("MISSING source")
        lines.append("")
        return lines
    rows = con.execute(
        f"""
        WITH u AS (
          SELECT 'seiji_smd' AS src, municipality
          FROM read_parquet('{smd.as_posix()}')
          WHERE municipality IS NOT NULL
          UNION ALL
          SELECT 'mic', municipality
          FROM read_parquet('{mic.as_posix()}')
          WHERE municipality IS NOT NULL
        ),
        n AS (
          SELECT src, municipality AS raw, {NORM_CASE} AS norm
          FROM u
          WHERE regexp_matches(municipality, '^.+-\\d+$')
             OR regexp_matches(municipality, '^.+[市町村]\\d+区$')
             OR regexp_matches(municipality, '^.+（\\d+区）$')
        )
        SELECT norm,
               count(DISTINCT raw) AS raw_variants,
               string_agg(DISTINCT raw, ' | ') AS raws,
               string_agg(DISTINCT src, ',') AS srcs
        FROM n
        GROUP BY 1
        HAVING count(DISTINCT raw) > 1
        ORDER BY raw_variants DESC, norm
        LIMIT 50
        """
    ).fetchall()
    lines.append(f"norm_keys_with_multiple_raw={len(rows)}")
    for r in rows:
        lines.append(f"  {r[0]}\tvariants={r[1]}\t{r[2]}\t[{r[3]}]")
    lines.append("")
    return lines


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"{stamp}_muni_label_audit.txt"
    latest = OUT_DIR / "muni_label_audit.txt"

    con = duckdb.connect()
    lines = [
        "# municipality label audit",
        f"generated_at={datetime.now().isoformat(timespec='seconds')}",
        "process=code/04-seiji-gakkai/process_display_qa_v1.0.txt",
        "",
    ]
    for label, path in SOURCES:
        lines.extend(section_pattern_counts(con, label, path))
    lines.extend(section_shi_shi(con))
    lines.extend(section_cross_norm(con))
    lines.extend(
        [
            "## pass criteria (display QA)",
            "- seiji_* dash/cityNku row counts == 0",
            "- shi×shi concat_remnants == 0",
            "- MIC cityNku may remain (e.g. 青森市1区); UI norm must collapse to 市（N区）",
            "",
        ]
    )
    text = "\n".join(lines) + "\n"
    out.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {out}")
    print(f"wrote {latest}")


if __name__ == "__main__":
    main()
