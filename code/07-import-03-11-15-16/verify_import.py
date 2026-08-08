import duckdb
c = duckdb.connect()
facts = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
print(c.sql(f"""
SELECT election_kaiji, source_code, metric, count(*) n
FROM read_parquet('{facts}')
WHERE source_code IN ('03-11','03-15','03-16')
GROUP BY 1,2,3
ORDER BY 1,2,3
"""))
print(c.sql(f"""
SELECT election_kaiji, prefecture, age_band, metric, gender, value
FROM read_parquet('{facts}')
WHERE source_code='03-15' AND prefecture='北海道'
ORDER BY age_band, metric, gender
LIMIT 20
"""))
print(c.sql(f"""
SELECT election_kaiji, age_band, metric, gender, value
FROM read_parquet('{facts}')
WHERE source_code='03-16' AND age_band IN ('20','20-24') AND gender='total'
ORDER BY election_kaiji, age_band, metric
LIMIT 30
"""))
