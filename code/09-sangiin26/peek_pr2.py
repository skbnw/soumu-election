#!/usr/bin/env python3
import duckdb

con = duckdb.connect()
print('sample party_votes', con.execute(
    """
    SELECT prefecture, municipality, party, value
    FROM read_parquet('web/data/municipality_facts.parquet')
    WHERE chamber='sangiin' AND election_kaiji=26 AND metric='party_votes'
    LIMIT 10
    """
).fetchall())
print('hokkaido munis', con.execute(
    """
    SELECT DISTINCT municipality
    FROM read_parquet('web/data/municipality_facts.parquet')
    WHERE chamber='sangiin' AND election_kaiji=26 AND prefecture='北海道' AND metric='party_votes'
    ORDER BY 1 LIMIT 15
    """
).fetchall())
print('district chuo', con.execute(
    """
    SELECT count(*) FROM read_parquet('web/data/municipality_facts.parquet')
    WHERE chamber='sangiin' AND election_kaiji=26 AND municipality='札幌市中央区'
    """
).fetchone())
