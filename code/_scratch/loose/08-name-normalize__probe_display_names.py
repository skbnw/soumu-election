# v1.0: displayPersonName 相当の誤表示サンプルを確認
from pathlib import Path
import duckdb

ROOT = Path(r"C:\Users\SKBNW\Documents\Github\soumu-election")
f = ROOT / "data/warehouse/parquet/facts.parquet"
con = duckdb.connect()

print("=== samples with paren in candidate_raw ===")
print(con.sql(f"""
SELECT candidate, candidate_raw, party, election_kaiji, prefecture
FROM read_parquet('{f.as_posix()}')
WHERE metric = 'candidate_votes' AND contest = 'smd'
  AND candidate_raw IS NOT NULL
  AND (candidate_raw LIKE '%円子%' OR candidate_raw LIKE '%(%' OR candidate_raw LIKE '%（%')
ORDER BY length(candidate_raw) ASC
LIMIT 30
"""))

print("=== 円子 ===")
print(con.sql(f"""
SELECT DISTINCT candidate, candidate_raw
FROM read_parquet('{f.as_posix()}')
WHERE coalesce(candidate,'') LIKE '%円子%'
   OR coalesce(candidate_raw,'') LIKE '%円子%'
"""))

print("=== short candidate names (1-2 chars) ===")
print(con.sql(f"""
SELECT DISTINCT candidate, candidate_raw
FROM read_parquet('{f.as_posix()}')
WHERE metric = 'candidate_votes' AND contest = 'smd'
  AND length(replace(replace(coalesce(candidate,''), ' ', ''), chr(12288), '')) <= 2
  AND candidate_raw IS NOT NULL
LIMIT 40
"""))
