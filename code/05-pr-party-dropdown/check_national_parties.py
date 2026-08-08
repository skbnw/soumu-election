# v1.0: 政党プルダウン用ランキングSQLの結果確認
from pathlib import Path
import duckdb
p = Path("data/warehouse/parquet/facts.parquet")
con = duckdb.connect()
rows = con.execute("""
WITH national_direct AS (
  SELECT election_kaiji, party, max(value) AS votes
  FROM read_parquet(?)
  WHERE metric = 'party_votes' AND contest = 'pr' AND source_code = '03-07'
    AND pr_block = '全国'
    AND coalesce(party, '') NOT IN ('', '合計')
  GROUP BY election_kaiji, party
),
from_blocks AS (
  SELECT election_kaiji, party, sum(value) AS votes
  FROM read_parquet(?)
  WHERE metric = 'party_votes' AND contest = 'pr' AND source_code = '03-10'
    AND coalesce(party, '') NOT IN ('', '合計')
    AND election_kaiji NOT IN (SELECT DISTINCT election_kaiji FROM national_direct)
  GROUP BY election_kaiji, party
),
ranked AS (
  SELECT * FROM national_direct
  UNION ALL
  SELECT * FROM from_blocks
)
SELECT election_kaiji, party, votes
FROM ranked
WHERE election_kaiji = 51
ORDER BY votes DESC NULLS LAST, party
""", [str(p), str(p)]).fetchall()
for r in rows:
    print(r)
