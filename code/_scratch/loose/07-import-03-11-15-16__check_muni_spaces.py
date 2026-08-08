import duckdb
c = duckdb.connect()
p = r"C:/Users/SKBNW/Documents/Github/soumu-election/web/data/municipality_facts.parquet"
print(c.sql(f"""
SELECT count(*) AS spaced
FROM read_parquet('{p}')
WHERE municipality LIKE '% %' OR municipality LIKE '%' || chr(12288) || '%'
"""))
print(c.sql(f"""
SELECT municipality FROM read_parquet('{p}')
WHERE municipality LIKE '堺市%'
GROUP BY 1 ORDER BY 1 LIMIT 10
"""))
