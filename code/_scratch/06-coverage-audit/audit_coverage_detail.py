# v1.1: 原本取得 vs 正規化カバレッジの詳細差分
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
WAREHOUSE = DATA / "warehouse"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def source_code_base(code: str | None) -> str:
    if not code:
        return "?"
    code = str(code)
    if code.startswith("03-14"):
        return "03-14"
    return code


def main() -> None:
    con = duckdb.connect()
    print("=== downloaded sources vs coverage ===")
    for kaiji in range(44, 52):
        d = DATA / f"shugiin{kaiji}"
        m = load_json(d / "manifest.json")
        nm = load_json(d / "normalized" / "manifest.json")
        sources = m.get("sources") or []
        cov = nm.get("coverage") or []
        unavailable = m.get("unavailable_sources") or []

        dl_codes = Counter()
        dl_by_fmt = Counter()
        dl_detail = []
        for s in sources:
            code = s.get("source_code") or "?"
            path = s.get("file") or s.get("filename") or ""
            fmt = Path(str(path)).suffix.lower() or s.get("format") or "?"
            base = source_code_base(code)
            dl_codes[base] += 1
            dl_by_fmt[f"{base}:{fmt}"] += 1
            dl_detail.append((code, fmt, s.get("title") or s.get("name") or ""))

        cov_codes = {}
        for c in cov:
            code = c.get("source_code") or "?"
            cov_codes[code] = c

        print(f"\n## shugiin{kaiji}")
        print(f"  downloaded_sources={len(sources)} coverage_entries={len(cov)} unavailable={len(unavailable)}")
        print(f"  download_by_base={dict(sorted(dl_codes.items()))}")

        # coverage detail
        for code, c in sorted(cov_codes.items()):
            print(
                f"  cov {code}: status={c.get('status')} records={c.get('records') or c.get('fact_count') or c.get('count')} "
                f"title={c.get('title') or c.get('dataset') or ''}"
            )

        # bases in download but not in coverage (except 03-14 many files map to one coverage?)
        cov_bases = {source_code_base(c) for c in cov_codes}
        missing_in_cov = sorted(set(dl_codes) - cov_bases)
        only_in_cov = sorted(cov_bases - set(dl_codes))
        print(f"  in_download_not_coverage_base={missing_in_cov}")
        print(f"  in_coverage_not_download_base={only_in_cov}")

        # PDFs among downloads
        pdfs = [x for x in dl_detail if x[1] == ".pdf"]
        print(f"  pdf_files={len(pdfs)}")
        for code, fmt, title in pdfs[:15]:
            in_cov = source_code_base(code) in cov_bases
            print(f"    pdf {code} in_cov_base={in_cov} {title[:60]}")

        # 03-14 municipal
        muni = [x for x in dl_detail if str(x[0]).startswith("03-14") or "市区町村" in str(x[2])]
        print(f"  municipal_like_files={len(muni)}")

        # domain records
        dom = nm.get("domain_records") or {}
        print(f"  domain_records={dom}")
        print(f"  normalized_sources={nm.get('normalized_sources')}")
        print(f"  records={nm.get('records')}")
        note = nm.get("note")
        if note:
            print(f"  note={note}")

    # warehouse
    cov_path = WAREHOUSE / "parquet" / "normalization_coverage.parquet"
    print("\n=== warehouse coverage status ===")
    print(con.sql(f"DESCRIBE SELECT * FROM read_parquet('{cov_path.as_posix()}')"))
    print(con.sql(f"""
        SELECT election_kaiji, status, count(*) AS docs, coalesce(sum(fact_count),0) AS facts
        FROM read_parquet('{cov_path.as_posix()}')
        GROUP BY 1,2 ORDER BY 1,2
    """))
    print("\n=== warehouse raw_only rows (if any) ===")
    print(con.sql(f"""
        SELECT election_kaiji, source_code, status, fact_count,
               coalesce(title, '') AS title
        FROM read_parquet('{cov_path.as_posix()}')
        WHERE status != 'normalized'
        ORDER BY election_kaiji, source_code
    """))

    facts = WAREHOUSE / "parquet" / "facts.parquet"
    print("\n=== facts by election/source_code ===")
    print(con.sql(f"""
        SELECT election_kaiji, source_code, count(*) AS n
        FROM read_parquet('{facts.as_posix()}')
        GROUP BY 1,2 ORDER BY 1,2
    """))

    # which standard codes missing per election in facts
    print("\n=== standard aggregate codes present in facts ===")
    print(con.sql(f"""
        WITH codes AS (
          SELECT election_kaiji, source_code
          FROM read_parquet('{facts.as_posix()}')
          GROUP BY 1,2
        )
        SELECT election_kaiji,
          list_sort(list(source_code)) AS present_codes,
          count(*) AS n_codes
        FROM codes
        GROUP BY 1 ORDER BY 1
    """))

    muni_p = WAREHOUSE / "parquet" / "municipality_facts.parquet"
    print("\n=== municipality_facts coverage ===")
    print(con.sql(f"""
        SELECT election_kaiji, contest, count(*) AS n,
               count(DISTINCT prefecture) AS prefs,
               count(DISTINCT municipality) AS munis
        FROM read_parquet('{muni_p.as_posix()}')
        GROUP BY 1,2 ORDER BY 1,2
    """))

    # source_documents
    srcd = WAREHOUSE / "parquet" / "source_documents.parquet"
    if srcd.exists():
        print("\n=== source_documents by election/format ===")
        print(con.sql(f"DESCRIBE SELECT * FROM read_parquet('{srcd.as_posix()}')"))
        print(con.sql(f"""
            SELECT * FROM read_parquet('{srcd.as_posix()}') LIMIT 3
        """))


if __name__ == "__main__":
    main()
