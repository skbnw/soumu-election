#!/usr/bin/env python3
# Verify sangiin26 ingest: counts, Hokkaido smoke, shugiin regression
from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    con = duckdb.connect()
    errors: list[str] = []

    manifest = json.loads((ROOT / "data" / "sangiin26" / "manifest.json").read_text(encoding="utf-8"))
    print("manifest sources", manifest["counts"]["sources"])
    raw = ROOT / "data" / "sangiin26" / "raw"
    dist = len(list(raw.glob("03-14-district-*.xlsx")))
    party = len(list(raw.glob("03-14-pr_party-*.xlsx")))
    cand = len(list(raw.glob("03-14-pr_cand-*.xlsx")))
    print("muni files district/party/cand", dist, party, cand)
    if dist != 47 or party != 47 or cand != 47:
        errors.append(f"expected 47 each muni types, got {dist}/{party}/{cand}")

    facts = ROOT / "web" / "data" / "facts.parquet"
    rows = con.execute(
        "SELECT election_id, count(*) FROM read_parquet(?) GROUP BY 1 ORDER BY 1",
        [str(facts)],
    ).fetchall()
    print("facts by election_id:")
    for row in rows:
        print(" ", row)
    by_id = {r[0]: r[1] for r in rows}
    if by_id.get("sangiin-26", 0) < 10000:
        errors.append("sangiin-26 facts too few")
    if by_id.get("sangiin-27", 0) < 10000:
        errors.append("sangiin-27 facts too few")
    if by_id.get("shugiin-51", 0) < 10000:
        errors.append("shugiin-51 regression: facts missing")

    muni = ROOT / "web" / "data" / "municipality_facts.parquet"
    mrows = con.execute(
        """
        SELECT chamber, election_kaiji, category, count(*)
        FROM read_parquet(?)
        GROUP BY 1, 2, 3
        ORDER BY 1, 2, 3
        """,
        [str(muni)],
    ).fetchall()
    print("municipality summary:")
    for row in mrows:
        print(" ", row)

    smoke = con.execute(
        """
        SELECT candidate, party, value
        FROM read_parquet(?)
        WHERE chamber = 'sangiin' AND election_kaiji = 26
          AND prefecture = '北海道' AND municipality = '札幌市中央区'
          AND category = '選挙区' AND candidate = '大村小太郎'
        """,
        [str(muni)],
    ).fetchall()
    print("Hokkaido smoke 大村小太郎:", smoke)
    if not smoke or smoke[0][2] != 5302:
        errors.append(f"Hokkaido smoke failed: {smoke}")

    party_smoke = con.execute(
        """
        SELECT party, value
        FROM read_parquet(?)
        WHERE chamber = 'sangiin' AND election_kaiji = 26
          AND prefecture = '北海道' AND municipality = '札幌市中央区'
          AND category = '比例代表' AND metric = 'party_votes' AND party = '幸福実現党'
        """,
        [str(muni)],
    ).fetchall()
    print("Hokkaido PR party smoke:", party_smoke)
    if not party_smoke or party_smoke[0][1] != 262:
        errors.append(f"PR party smoke failed: {party_smoke}")

    shugiin_muni = con.execute(
        """
        SELECT count(*) FROM read_parquet(?)
        WHERE (chamber IS NULL OR chamber = 'shugiin') AND election_kaiji = 51
        """,
        [str(muni)],
    ).fetchone()[0]
    print("shugiin-51 municipality rows", shugiin_muni)
    if shugiin_muni < 10000:
        errors.append("shugiin municipality regression")

    meta = json.loads((ROOT / "web" / "data" / "meta.json").read_text(encoding="utf-8"))
    print("meta election_ids", meta.get("election_ids"))
    if "sangiin-26" not in meta.get("election_ids", []):
        errors.append("meta missing sangiin-26")

    if errors:
        print("FAIL")
        for err in errors:
            print(" -", err)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
