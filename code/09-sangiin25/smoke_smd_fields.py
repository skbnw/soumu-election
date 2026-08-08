#!/usr/bin/env python3
"""Smoke: shugiin SMD fields for UI enrichment."""
import duckdb

con = duckdb.connect()
print(con.execute(
    """
    SELECT election_kaiji,
           count(*) AS n,
           count(elected) AS elected_n,
           count(party) AS party_n,
           count(sekihairitsu) AS sekihai_n
    FROM read_parquet('web/data/facts.parquet')
    WHERE election_id LIKE 'shugiin-%'
      AND contest='smd' AND metric='candidate_votes'
    GROUP BY 1 ORDER BY 1
    """
).fetchall())
print("sample", con.execute(
    """
    SELECT election_kaiji, prefecture, district_number, candidate, party, elected, value, sekihairitsu
    FROM read_parquet('web/data/facts.parquet')
    WHERE election_id LIKE 'shugiin-%' AND contest='smd' AND metric='candidate_votes'
      AND prefecture='北海道' AND district_number=1 AND election_kaiji=51
    ORDER BY value DESC NULLS LAST LIMIT 5
    """
).fetchall())
