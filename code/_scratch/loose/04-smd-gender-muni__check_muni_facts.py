# v1.0: municipality_facts の都道府県欠損と千代田区サンプルを確認
from pathlib import Path
import duckdb
p = Path("web/data/municipality_facts.parquet")
con = duckdb.connect()
print("categories", con.execute("SELECT category, count(*), count(prefecture) FROM read_parquet(?) GROUP BY 1", [str(p)]).fetchall())
print("pr null pref", con.execute("SELECT count(*) FROM read_parquet(?) WHERE category='比例代表' AND prefecture IS NULL", [str(p)]).fetchone())
print("chiyoda", con.execute("""
SELECT category, prefecture, municipality, subject, value
FROM read_parquet(?)
WHERE municipality='千代田区' AND election_kaiji=51
ORDER BY category, value DESC LIMIT 20
""", [str(p)]).fetchall())
