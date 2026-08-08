#!/usr/bin/env python3
"""Probe edge-case municipality labels before normalize."""
import duckdb

con = duckdb.connect()
rows = con.execute(
    """
    SELECT election_kaiji, municipality, count(*) c
    FROM read_parquet('web/data/municipality_facts.parquet')
    WHERE (chamber IS NULL OR chamber = 'shugiin')
      AND (
        municipality LIKE '%第（%'
        OR municipality LIKE '%第(%'
        OR municipality LIKE '%(%）%'
        OR municipality LIKE '%（%)%'
      )
    GROUP BY 1,2 ORDER BY 2,1
    """
).fetchall()
for r in rows:
    print(r)
