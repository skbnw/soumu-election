# v1.0: 03-10のブロック表記重複有無を確認
from pathlib import Path
import duckdb
p = Path("data/warehouse/parquet/facts.parquet")
con = duckdb.connect()
print(con.execute("""
SELECT election_kaiji, pr_block, count(*) n
FROM read_parquet(?)
WHERE metric='party_votes' AND contest='pr' AND source_code='03-10' AND election_kaiji=51
GROUP BY 1,2 ORDER BY 2
""", [str(p)]).fetchall())
