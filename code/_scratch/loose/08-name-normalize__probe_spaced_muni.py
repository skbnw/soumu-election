import duckdb
c = duckdb.connect()
muni = r"C:/Users/SKBNW/Documents/Github/soumu-election/web/data/municipality_facts.parquet"
print(c.sql(f"""
SELECT election_kaiji, category, subject, party, count(*) n
FROM read_parquet('{muni}')
WHERE (subject LIKE '% %' OR subject LIKE '%'||chr(12288)||'%'
    OR party LIKE '% %' OR party LIKE '%'||chr(12288)||'%')
GROUP BY 1,2,3,4
ORDER BY n DESC
LIMIT 50
"""))
