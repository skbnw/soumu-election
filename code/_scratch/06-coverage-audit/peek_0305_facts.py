import duckdb
c = duckdb.connect()
f = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
print(c.sql(f"""
SELECT election_kaiji, contest, metric, party, value, unit
FROM read_parquet('{f}')
WHERE election_kaiji=50 AND source_code='03-05' AND party='立憲民主党'
"""))
