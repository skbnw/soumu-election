#!/usr/bin/env python3
import duckdb

con = duckdb.connect()
rows = con.execute(
    """
    SELECT party, metric, value
    FROM read_parquet('web/data/municipality_facts.parquet')
    WHERE chamber='sangiin' AND election_kaiji=26
      AND prefecture='北海道' AND municipality='札幌市中央区'
      AND category='比例代表'
    ORDER BY metric, value DESC NULLS LAST
    LIMIT 25
    """
).fetchall()
for row in rows:
    print(row)

print('party null count', con.execute(
    """
    SELECT count(*), count(party)
    FROM read_parquet('web/data/municipality_facts.parquet')
    WHERE chamber='sangiin' AND election_kaiji=26 AND metric='party_votes'
    """
).fetchone())
