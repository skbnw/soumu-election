import duckdb
c = duckdb.connect()
f = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
print(c.sql(f"""
SELECT source_code, metric, candidate, candidate_raw, party
FROM read_parquet('{f}')
WHERE election_kaiji IN (49,50,51)
  AND (coalesce(candidate,'') LIKE '%みたぞ%' OR coalesce(candidate_raw,'') LIKE '%みたぞ%'
       OR coalesce(candidate,'') LIKE '%三反園%' OR coalesce(candidate_raw,'') LIKE '%三反園%')
"""))
