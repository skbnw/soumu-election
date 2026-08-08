#!/usr/bin/env python3
# Verify sangiin25 facts/muni after ingest
from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    errors = []
    meta = json.loads((ROOT / "web" / "data" / "meta.json").read_text(encoding="utf-8"))
    print("election_ids", meta.get("election_ids"))
    if "sangiin-25" not in meta.get("election_ids", []):
        errors.append("meta missing sangiin-25")

    con = duckdb.connect()
    facts = ROOT / "web" / "data" / "facts.parquet"
    rows = con.execute(
        "SELECT election_id, count(*) FROM read_parquet(?) GROUP BY 1 ORDER BY 1",
        [str(facts)],
    ).fetchall()
    print("facts:")
    for r in rows:
        print(" ", r)
    by = {r[0]: r[1] for r in rows}
    if by.get("sangiin-25", 0) < 5000:
        errors.append(f"sangiin-25 facts too few: {by.get('sangiin-25')}")

    muni = ROOT / "web" / "data" / "municipality_facts.parquet"
    mrows = con.execute(
        """
        SELECT chamber, election_kaiji, category, count(*)
        FROM read_parquet(?)
        WHERE chamber = 'sangiin'
        GROUP BY 1,2,3 ORDER BY 2,3
        """,
        [str(muni)],
    ).fetchall()
    print("sangiin municipality:")
    for r in mrows:
        print(" ", r)
    s25 = sum(r[3] for r in mrows if r[1] == 25)
    if s25 < 100000:
        errors.append(f"sangiin-25 muni too few: {s25}")

    # Hokkaido district smoke if available
    smoke = con.execute(
        """
        SELECT municipality, candidate, value
        FROM read_parquet(?)
        WHERE chamber='sangiin' AND election_kaiji=25 AND prefecture='北海道'
          AND category='選挙区' AND municipality='札幌市中央区'
        ORDER BY value DESC NULLS LAST LIMIT 3
        """,
        [str(muni)],
    ).fetchall()
    print("Hokkaido top3:", smoke)
    if not smoke:
        errors.append("Hokkaido smoke empty")

    raw = ROOT / "data" / "sangiin25" / "raw"
    dist = len(list(raw.glob("03-14-district-*")))
    party = len(list(raw.glob("03-14-pr-party-*"))) + len(list(raw.glob("03-14-pr_party-*")))
    cand = len(list(raw.glob("03-14-pr-cand-*"))) + len(list(raw.glob("03-14-pr_cand-*")))
    print("raw muni counts", dist, party, cand)
    if dist != 47 or party != 47 or cand != 47:
        errors.append(f"raw muni counts {dist}/{party}/{cand}")

    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
