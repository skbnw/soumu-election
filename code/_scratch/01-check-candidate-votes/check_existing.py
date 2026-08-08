# v1.0: warehouse内のcandidate_votes件数を選挙回別に確認
from pathlib import Path
import duckdb

root = Path(__file__).resolve().parents[2]
path = root / "data" / "warehouse" / "parquet" / "facts.parquet"
con = duckdb.connect()
rows = con.execute(
    """
    SELECT election_kaiji, count(*) AS n,
           count(DISTINCT prefecture) AS prefs,
           count(DISTINCT district_number) AS districts
    FROM read_parquet(?)
    WHERE metric = 'candidate_votes'
    GROUP BY 1
    ORDER BY 1
    """,
    [str(path)],
).fetchall()
for row in rows:
    print(row)
print("total_facts", con.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0])
