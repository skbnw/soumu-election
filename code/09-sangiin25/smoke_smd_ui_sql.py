#!/usr/bin/env python3
"""Verify shugiin SMD enriched select SQL shape."""
import duckdb

con = duckdb.connect()
rows = con.execute(
    """
    SELECT election_kaiji, prefecture, district_number, candidate, party, elected, value,
      CASE
        WHEN sum(value) OVER (PARTITION BY election_kaiji, prefecture, district_number) > 0
        THEN 100.0 * value / sum(value) OVER (PARTITION BY election_kaiji, prefecture, district_number)
        ELSE NULL
      END AS relative_share,
      coalesce(
        sekihairitsu,
        CASE
          WHEN max(CASE WHEN elected THEN value END) OVER (
            PARTITION BY election_kaiji, prefecture, district_number
          ) > 0
          THEN 100.0 * value / max(CASE WHEN elected THEN value END) OVER (
            PARTITION BY election_kaiji, prefecture, district_number
          )
          ELSE NULL
        END
      ) AS sekihai_rate
    FROM read_parquet('web/data/facts.parquet')
    WHERE election_id LIKE 'shugiin-%'
      AND contest='smd' AND metric='candidate_votes'
      AND election_kaiji=51 AND prefecture='北海道' AND district_number=1
    ORDER BY value DESC NULLS LAST
    """
).fetchall()
for r in rows:
    print(r)
