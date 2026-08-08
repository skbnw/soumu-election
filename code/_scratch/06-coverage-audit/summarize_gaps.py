# v1.0: 未構造化残量の要約集計
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent / "output_summary.txt"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def base(code: str) -> str:
    code = str(code or "?")
    if code.startswith("03-14"):
        return "03-14"
    if code.startswith("00-00"):
        return "00-00"
    return code


# 表紙・全体版など、構造化対象外とみなす資料
NON_TABLE = {"00-00", "99-00"}


def main() -> None:
    lines = []
    con = duckdb.connect()

    # facts source codes
    facts = DATA / "warehouse/parquet/facts.parquet"
    facts_codes = con.sql(
        f"""
        SELECT election_kaiji, source_code, count(*) AS n
        FROM read_parquet('{facts.as_posix()}')
        GROUP BY 1,2
        """
    ).fetchall()
    facts_map = defaultdict(set)
    for kaiji, code, n in facts_codes:
        facts_map[int(kaiji)].add(str(code))

    muni = DATA / "warehouse/parquet/municipality_facts.parquet"
    muni_rows = con.sql(
        f"""
        SELECT election_kaiji, contest, count(*) AS n
        FROM read_parquet('{muni.as_posix()}')
        GROUP BY 1,2 ORDER BY 1,2
        """
    ).fetchall()
    muni_map = defaultdict(set)
    for kaiji, contest, n in muni_rows:
        muni_map[int(kaiji)].add(str(contest))

    # warehouse coverage
    covp = DATA / "warehouse/parquet/normalization_coverage.parquet"
    cov_status = con.sql(
        f"""
        SELECT election_kaiji, status, count(*) 
        FROM read_parquet('{covp.as_posix()}')
        GROUP BY 1,2 ORDER BY 1,2
        """
    ).fetchall()

    lines.append("=== warehouse coverage status ===")
    for row in cov_status:
        lines.append(str(row))

    lines.append("\n=== municipality_facts ===")
    for row in muni_rows:
        lines.append(str(row))

    # per election gap analysis focusing on data tables
    lines.append("\n=== gap: downloaded data tables not in facts/muni structure ===")
    totals = Counter()
    detail = defaultdict(list)

    for kaiji in range(44, 52):
        m = load_json(DATA / f"shugiin{kaiji}/manifest.json")
        sources = m.get("sources") or []
        unavailable = m.get("unavailable_sources") or []

        by_base = defaultdict(list)
        for s in sources:
            code = s.get("source_code") or "?"
            path = s.get("file") or ""
            fmt = Path(str(path)).suffix.lower()
            title = s.get("title") or s.get("name") or ""
            by_base[base(code)].append({"code": code, "fmt": fmt, "title": title})

        lines.append(f"\n## shugiin{kaiji}")
        # data table bases
        for b, items in sorted(by_base.items()):
            if b in NON_TABLE:
                continue
            n = len(items)
            fmts = Counter(i["fmt"] for i in items)
            in_facts = b in facts_map[kaiji] or any(
                c.startswith(b) for c in facts_map[kaiji]
            )
            # 03-14 special: municipality_facts
            if b == "03-14":
                structured = kaiji in muni_map and len(muni_map[kaiji]) > 0
                where = "municipality_facts" if structured else "NOT_STRUCTURED"
            elif in_facts:
                structured = True
                where = "facts"
            else:
                structured = False
                where = "NOT_STRUCTURED"

            status = "OK" if structured else "GAP"
            lines.append(f"  {status} {b}: files={n} fmts={dict(fmts)} -> {where}")
            totals["data_table_bases"] += 1
            totals["data_table_files"] += n
            if structured:
                totals["structured_bases"] += 1
                totals["structured_files"] += n
            else:
                totals["gap_bases"] += 1
                totals["gap_files"] += n
                detail[b].append(kaiji)

        # unavailable
        for u in unavailable:
            code = u.get("source_code") if isinstance(u, dict) else str(u)
            lines.append(f"  UNAVAILABLE {code}")
            totals["unavailable"] += 1

    lines.append("\n=== TOTALS (data tables only; excludes 00-00/99-00 cover PDFs) ===")
    for k, v in totals.items():
        lines.append(f"  {k}={v}")
    lines.append("\n=== GAP bases by election ===")
    for b, elections in sorted(detail.items()):
        lines.append(f"  {b}: elections={elections} (n={len(elections)})")

    # file-level share
    lines.append("\n=== file-level share of downloaded sources ===")
    all_files = 0
    structured_files = 0
    non_table_files = 0
    gap_files = 0
    for kaiji in range(44, 52):
        m = load_json(DATA / f"shugiin{kaiji}/manifest.json")
        for s in m.get("sources") or []:
            b = base(s.get("source_code"))
            all_files += 1
            if b in NON_TABLE:
                non_table_files += 1
                continue
            if b == "03-14":
                ok = kaiji in muni_map
            else:
                ok = b in facts_map[kaiji] or any(c.startswith(b) for c in facts_map[kaiji])
            if ok:
                structured_files += 1
            else:
                gap_files += 1
    lines.append(f"  all_downloaded_files={all_files}")
    lines.append(f"  non_table_cover_files={non_table_files}")
    lines.append(f"  structured_data_files={structured_files}")
    lines.append(f"  gap_data_files={gap_files}")
    data_files = structured_files + gap_files
    if data_files:
        lines.append(f"  gap_share_of_data_files={gap_files}/{data_files} = {100*gap_files/data_files:.1f}%")
        lines.append(f"  structured_share_of_data_files={100*structured_files/data_files:.1f}%")

    # 03-14 file counts vs muni presence
    lines.append("\n=== 03-14 municipal specifically ===")
    for kaiji in range(44, 52):
        m = load_json(DATA / f"shugiin{kaiji}/manifest.json")
        n14 = sum(1 for s in m.get("sources") or [] if str(s.get("source_code","")).startswith("03-14"))
        unavail = any(
            (u.get("source_code") if isinstance(u, dict) else str(u)) == "03-14"
            for u in (m.get("unavailable_sources") or [])
        )
        lines.append(
            f"  {kaiji}: raw_files={n14} unavailable={unavail} muni_contests={sorted(muni_map.get(kaiji, []))}"
        )

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
