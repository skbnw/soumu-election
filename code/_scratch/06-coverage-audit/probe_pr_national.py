# v1.0: 比例全国得票の異常値調査
import duckdb

facts = "C:/Users/SKBNW/Documents/Github/soumu-election/data/warehouse/parquet/facts.parquet"
c = duckdb.connect()

print("=== columns ===")
print(c.sql(f"DESCRIBE SELECT * FROM read_parquet('{facts}')"))

print("\n=== sample party_votes PR rows kaiji 50 ===")
print(c.sql(f"""
SELECT source_code, contest, metric, unit, prefecture, pr_block, party,
       value, gender, age_band
FROM read_parquet('{facts}')
WHERE election_kaiji = 50
  AND (metric ILIKE '%vote%' OR metric ILIKE '%party%')
  AND (contest ILIKE '%pr%' OR contest ILIKE '%比例%' OR source_code IN ('03-05','03-07','03-10'))
LIMIT 30
"""))

print("\n=== distinct metric/source for PR parties kaiji 49-50 ===")
print(c.sql(f"""
SELECT election_kaiji, source_code, contest, metric, unit, count(*) n,
       count(DISTINCT party) parties,
       sum(value) sum_val
FROM read_parquet('{facts}')
WHERE election_kaiji IN (49,50)
  AND party IS NOT NULL AND party != ''
  AND (source_code LIKE '03-0%' OR contest ILIKE '%pr%' OR contest ILIKE '%比例%')
GROUP BY 1,2,3,4,5
ORDER BY 1,2,4
"""))
