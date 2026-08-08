# v1.0: 原本取得 vs 正規化カバレッジの監査
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
WAREHOUSE = DATA / "warehouse"


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    print("=== per-election download / normalized manifests ===")
    summary_rows = []
    for kaiji in range(44, 52):
        d = DATA / f"shugiin{kaiji}"
        man = d / "manifest.json"
        nman = d / "normalized" / "manifest.json"
        raw_dir = d / "raw"
        print(f"\n## shugiin{kaiji}")
        print(
            f"  exists={d.exists()} raw={raw_dir.exists()} "
            f"download_manifest={man.exists()} normalized_manifest={nman.exists()}"
        )
        fmt = Counter()
        unavailable = []
        if man.exists():
            m = load_json(man)
            sources = m.get("sources") or m.get("downloaded") or m.get("items") or []
            unavailable = m.get("unavailable_sources") or []
            if isinstance(sources, list) and sources:
                for s in sources:
                    if not isinstance(s, dict):
                        continue
                    name = s.get("file") or s.get("filename") or s.get("path") or ""
                    ext = Path(str(name)).suffix.lower()
                    if not ext:
                        ext = str(s.get("format") or "?")
                    fmt[ext] += 1
            elif raw_dir.exists():
                for p in raw_dir.rglob("*"):
                    if p.is_file():
                        fmt[p.suffix.lower() or "(none)"] += 1
            print(f"  download_top_keys={sorted(m.keys())[:25]}")
            print(f"  formats={dict(fmt)} unavailable={len(unavailable)}")
            for u in unavailable[:10]:
                if isinstance(u, dict):
                    print(
                        "    unavailable:",
                        u.get("source_code") or u.get("title") or u.get("name") or u,
                    )
                else:
                    print("    unavailable:", u)
            policy = m.get("normalization_policy")
            if policy:
                print(f"  normalization_policy={policy}")
        elif raw_dir.exists():
            for p in raw_dir.rglob("*"):
                if p.is_file():
                    fmt[p.suffix.lower() or "(none)"] += 1
            print(f"  formats_from_raw={dict(fmt)}")

        status = Counter()
        raw_only_items = []
        fact_count = None
        if nman.exists():
            nm = load_json(nman)
            cov = nm.get("coverage") or []
            for c in cov:
                st = c.get("status") or c.get("state") or "?"
                status[st] += 1
                if st == "raw_only":
                    raw_only_items.append(
                        f"{c.get('source_code')}:{c.get('title') or c.get('dataset') or c.get('file') or ''}"
                    )
            fact_count = nm.get("fact_count") or nm.get("facts") or nm.get("counts")
            print(f"  coverage_status={dict(status)} coverage_n={len(cov)}")
            print(f"  normalized_keys={list(nm.keys())[:20]}")
            print(f"  facts_meta={fact_count}")
            for item in raw_only_items:
                print(f"    raw_only {item}")
        summary_rows.append(
            {
                "kaiji": kaiji,
                "raw_files": sum(fmt.values()),
                "formats": dict(fmt),
                "unavailable": len(unavailable),
                "normalized": status.get("normalized", 0),
                "raw_only": status.get("raw_only", 0),
                "other_status": {k: v for k, v in status.items() if k not in {"normalized", "raw_only"}},
                "has_nman": nman.exists(),
            }
        )

    print("\n=== SUMMARY TABLE ===")
    for r in summary_rows:
        print(r)

    cov_path = WAREHOUSE / "parquet" / "normalization_coverage.parquet"
    print("\n=== warehouse normalization_coverage ===")
    con = duckdb.connect()
    if cov_path.exists():
        df = con.sql(f"SELECT * FROM read_parquet('{cov_path.as_posix()}') ORDER BY 1,2").df()
        print("columns:", list(df.columns))
        print(df.to_string())
        print("\nstatus counts:")
        print(con.sql(f"""
            SELECT election_kaiji, status, count(*) AS n, sum(fact_count) AS facts
            FROM read_parquet('{cov_path.as_posix()}')
            GROUP BY 1,2 ORDER BY 1,2
        """))
        print("\nraw_only documents:")
        print(con.sql(f"""
            SELECT election_kaiji, source_code, title, status, fact_count, note
            FROM read_parquet('{cov_path.as_posix()}')
            WHERE status = 'raw_only'
            ORDER BY election_kaiji, source_code
        """))
    else:
        print("missing", cov_path)

    facts_path = WAREHOUSE / "parquet" / "facts.parquet"
    print("\n=== warehouse facts by election ===")
    if facts_path.exists():
        cols = con.sql(f"DESCRIBE SELECT * FROM read_parquet('{facts_path.as_posix()}')").df()
        print(cols)
        print(con.sql(f"""
            SELECT election_kaiji, count(*) AS n
            FROM read_parquet('{facts_path.as_posix()}')
            GROUP BY 1 ORDER BY 1
        """))
        colset = set(cols["column_name"].tolist())
        if "source_code" in colset:
            print(con.sql(f"""
                SELECT election_kaiji, source_code, count(*) AS n
                FROM read_parquet('{facts_path.as_posix()}')
                GROUP BY 1,2 ORDER BY 1,2
            """))
        if "contest" in colset:
            print(con.sql(f"""
                SELECT election_kaiji, contest, count(*) AS n
                FROM read_parquet('{facts_path.as_posix()}')
                GROUP BY 1,2 ORDER BY 1,2
            """))

    muni = WAREHOUSE / "parquet" / "municipality_facts.parquet"
    if muni.exists():
        print("\n=== municipality_facts ===")
        print(con.sql(f"""
            SELECT election_kaiji, contest, count(*) AS n
            FROM read_parquet('{muni.as_posix()}')
            GROUP BY 1,2 ORDER BY 1,2
        """))


if __name__ == "__main__":
    main()
