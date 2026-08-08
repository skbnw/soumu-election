# v1.0: 候補者名の空白ゆれ調査
import duckdb

c = duckdb.connect()
facts = r"C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
muni = r"C:/Users/SKBNW/Documents/Github/soumu-election/web/data/municipality_facts.parquet"

print("=== facts candidates with spaces ===")
print(c.sql(f"""
SELECT election_kaiji, prefecture, district_number, candidate, candidate_raw, count(*) n
FROM read_parquet('{facts}')
WHERE candidate IS NOT NULL
  AND (candidate LIKE '% %' OR candidate LIKE '%' || chr(12288) || '%'
       OR candidate_raw LIKE '% %' OR candidate_raw LIKE '%' || chr(12288) || '%')
  AND (candidate ILIKE '%みたぞ%' OR candidate ILIKE '%みたぞの%'
       OR candidate_raw ILIKE '%みたぞ%' OR candidate LIKE '%道下%'
       OR candidate LIKE '%　%')
GROUP BY 1,2,3,4,5
ORDER BY 1 DESC, 4
LIMIT 40
"""))

print("\n=== sample spaced candidates kaiji 51 ===")
print(c.sql(f"""
SELECT candidate, candidate_raw, count(*) n
FROM read_parquet('{facts}')
WHERE election_kaiji=51 AND candidate IS NOT NULL
  AND (candidate LIKE '% %' OR candidate LIKE '%' || chr(12288) || '%'
       OR regexp_matches(candidate, '[ぁ-んァ-ン一-龥]\\s+[ぁ-んァ-ン一-龥]'))
GROUP BY 1,2
ORDER BY n DESC
LIMIT 30
"""))

print("\n=== muni subject spaced ===")
print(c.sql(f"""
SELECT election_kaiji, subject, count(*) n
FROM read_parquet('{muni}')
WHERE subject IS NOT NULL
  AND (subject LIKE '% %' OR subject LIKE '%' || chr(12288) || '%')
  AND (subject ILIKE '%みたぞ%' OR subject LIKE '%道下%' OR true)
GROUP BY 1,2
HAVING subject ILIKE '%みた%' OR subject LIKE '%　%' OR subject LIKE '% %'
ORDER BY 1 DESC, 2
LIMIT 40
"""))

print("\n=== mitazono variants ===")
print(c.sql(f"""
SELECT 'facts' AS src, election_kaiji, candidate AS name, count(*) n
FROM read_parquet('{facts}')
WHERE coalesce(candidate,'') LIKE '%みたぞ%' OR coalesce(candidate_raw,'') LIKE '%みたぞ%'
   OR coalesce(candidate,'') LIKE '%道下%'
GROUP BY 1,2,3
UNION ALL
SELECT 'muni', election_kaiji, subject, count(*)
FROM read_parquet('{muni}')
WHERE coalesce(subject,'') LIKE '%みたぞ%' OR coalesce(subject,'') LIKE '%道下%'
GROUP BY 1,2,3
ORDER BY 2 DESC, 3
"""))
