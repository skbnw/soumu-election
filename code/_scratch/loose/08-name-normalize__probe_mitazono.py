import duckdb
c = duckdb.connect()
facts = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
muni = r"C:/Users/SKBNW/Documents/Github/soumu-election/web/data/municipality_facts.parquet"

print("=== all mitazono-ish in muni 51 ===")
print(c.sql(f"""
SELECT category, prefecture, municipality, subject, party, value
FROM read_parquet('{muni}')
WHERE election_kaiji=51
  AND (subject LIKE '%みたぞ%' OR subject LIKE '%三反園%' OR party LIKE '%みたぞ%' OR party LIKE '%三反園%')
ORDER BY category, municipality
LIMIT 30
"""))

print("\n=== spaced party/candidate counts ===")
print(c.sql(f"""
SELECT 'facts.candidate' AS col, count(*) FILTER (WHERE candidate LIKE '% %' OR candidate LIKE '%'||chr(12288)||'%') AS spaced
FROM read_parquet('{facts}')
UNION ALL
SELECT 'facts.party', count(*) FILTER (WHERE party LIKE '% %' OR party LIKE '%'||chr(12288)||'%')
FROM read_parquet('{facts}')
UNION ALL
SELECT 'muni.subject', count(*) FILTER (WHERE subject LIKE '% %' OR subject LIKE '%'||chr(12288)||'%')
FROM read_parquet('{muni}')
UNION ALL
SELECT 'muni.party', count(*) FILTER (WHERE party LIKE '% %' OR party LIKE '%'||chr(12288)||'%')
FROM read_parquet('{muni}')
"""))

print("\n=== sample spaced parties in facts ===")
print(c.sql(f"""
SELECT DISTINCT party FROM read_parquet('{facts}')
WHERE party LIKE '% %' OR party LIKE '%'||chr(12288)||'%'
ORDER BY 1 LIMIT 40
"""))
