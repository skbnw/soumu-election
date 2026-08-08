#!/usr/bin/env python3
from pathlib import Path
import shutil
import duckdb

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    src = ROOT / "data" / "warehouse" / "parquet" / "facts.parquet"
    dst = ROOT / "web" / "data" / "facts.parquet"
    print("warehouse", src.exists(), src.stat().st_size if src.exists() else 0)
    print("web before", dst.exists(), dst.stat().st_size if dst.exists() else 0)
    shutil.copy2(src, dst)
    print("copied", dst.stat().st_size)
    con = duckdb.connect()
    rows = con.execute(
        "SELECT election_id, count(*) AS c FROM read_parquet(?) GROUP BY 1 ORDER BY 1",
        [str(dst)],
    ).fetchall()
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
