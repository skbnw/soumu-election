# v1.0: 市区町村parquetの都道府県別件数を確認
from pathlib import Path
import duckdb

p = Path("web/data/smd_municipality_votes.parquet")
con = duckdb.connect()
print("total", con.execute("SELECT count(*) FROM read_parquet(?)", [str(p)]).fetchone())
print("by kaiji", con.execute(
    "SELECT election_kaiji, count(*), count(DISTINCT prefecture), count(DISTINCT municipality) FROM read_parquet(?) GROUP BY 1 ORDER BY 1",
    [str(p)],
).fetchall())
print("tokyo 51 sample", con.execute(
    """
    SELECT district_number, municipality, candidate, value
    FROM read_parquet(?)
    WHERE election_kaiji=51 AND prefecture='東京都'
    ORDER BY district_number, municipality, value DESC
    LIMIT 12
    """,
    [str(p)],
).fetchall())
print("hokkaido 51 munis", con.execute(
    "SELECT count(DISTINCT municipality) FROM read_parquet(?) WHERE election_kaiji=51 AND prefecture='北海道'",
    [str(p)],
).fetchone())
